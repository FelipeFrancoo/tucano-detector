"""
metrics.py
----------
Módulo de cálculo de perplexidade e burstiness usando o Tucano
(TucanoBR/Tucano-1b1) como modelo de linguagem autorregressivo.

Este é o núcleo da "camada de modelo" + "camada de cálculo" descritas
no capítulo de Implementação do TCC II. A ideia é manter este arquivo
sem nenhuma lógica de interface (CLI, Streamlit etc.) — só o que
transforma texto em números. A interface visual/CLI usa estas funções.

Uso rápido:

    from metrics import TucanoMetrics

    tm = TucanoMetrics()  # carrega o modelo uma vez
    result = tm.analyze_text("Seu texto aqui.")
    print(result)  # {"perplexity": ..., "burstiness": ..., "n_sentences": ...}
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field
from typing import List

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL_ID = "TucanoBR/Tucano-1b1"

# Número mínimo de tokens para uma sentença entrar no cálculo.
#
# Textos extraídos de PDF (caso dos anais) costumam produzir fragmentos
# órfãos como "(não frequentes)." ou 'Saber "', separados do período
# original por quebras de linha do layout. Fora de contexto, o modelo
# atribui a esses cacos uma perplexidade altíssima (3790 contra uma
# mediana de 37 no mesmo texto), o que domina o desvio-padrão e faz o
# burstiness explodir. Como eles são ruído de extração e não escrita
# real, ficam de fora — seguindo a mesma lógica que já descartava
# sentenças de 1 token por falta de contexto.
MIN_TOKENS_SENTENCA = 5


# ----------------------------------------------------------------------
# Segmentação de sentenças
# ----------------------------------------------------------------------
# O spaCy quebra sentença depois de "et al." e, às vezes, depois de
# dois-pontos. Isso gera fragmentos ("Araújo et al.", "o ramo de
# apostas.") que não são sentenças e recebem perplexidade altíssima por
# falta de contexto, inflando o burstiness de textos sem defeito algum.
# O MIN_TOKENS_SENTENCA não pega esses casos porque eles têm 5 ou 6
# tokens. O componente abaixo roda antes do parser e proíbe início de
# sentença logo depois dessas abreviações e de dois-pontos.
NAO_TERMINA_SENTENCA = {
    # o tokenizador do spaCy separa o ponto da abreviação ("al" + "."),
    # por isso as duas formas entram no conjunto
    "al.", "al", "etc.", "etc", "fig.", "fig", "figs.", "tab.", "tab",
    "eq.", "eq", "ref.", "ref", "cap.", "cap", "p.", "p", "pp.", "pp",
    "vs.", "vs", "cf.", "cf", "ed.", "ed", "eds.", "vol.", "vol",
    "no.", "núm.", "num.", "dr.", "dra.", "sr.", "sra.", "prof.",
    "profa.", "aprox.", "e.g.", "i.e.", "ca.", "séc.",
    ":",
}


def _registrar_componente() -> None:
    """Registra o componente no spaCy uma única vez."""
    import spacy

    if "nao_quebrar_apos_abreviacao" in spacy.registry.factories:
        return

    @spacy.Language.component("nao_quebrar_apos_abreviacao")
    def nao_quebrar_apos_abreviacao(doc):
        n = len(doc)
        for i in range(n - 1):
            if doc[i].text.lower() not in NAO_TERMINA_SENTENCA:
                continue
            # pula a pontuação que o tokenizador separou da abreviação
            j = i + 1
            while j < n and doc[j].text in {".", ":"}:
                j += 1
            if 0 < j < n:
                doc[j].is_sent_start = False
        return doc


def _juntar_fragmentos(sentencas: List[str]) -> List[str]:
    """Junta trechos que não terminam em pontuação final.

    Mesmo antes do parser, o spaCy às vezes abre sentença no meio de uma
    frase, sem pontuação alguma ("O Problema p-hub" | "Centro (pHCP) é um
    problema..."). Um trecho que não termina em . ! ? não é uma sentença:
    é a primeira metade da seguinte.
    """
    saida: List[str] = []
    for s in sentencas:
        if saida and not saida[-1].rstrip().endswith((".", "!", "?")):
            saida[-1] = saida[-1].rstrip() + " " + s
        else:
            saida.append(s)
    return saida


def split_sentences(text: str) -> List[str]:
    """
    Segmenta o texto em sentenças.

    Usa spaCy (mais robusto para português) com um componente extra que
    impede quebra depois de abreviação e de dois-pontos, mais uma junção
    final dos fragmentos sem pontuação. Se o modelo do spaCy não estiver
    instalado, cai para uma divisão simples por regex.
    """
    try:
        import spacy

        if not hasattr(split_sentences, "_nlp"):
            _registrar_componente()
            nlp = spacy.load(
                "pt_core_news_sm", disable=["ner", "lemmatizer", "tagger"]
            )
            # precisa rodar antes de quem define os limites de sentença
            if "parser" in nlp.pipe_names:
                nlp.add_pipe("nao_quebrar_apos_abreviacao", before="parser")
            else:
                nlp.add_pipe("nao_quebrar_apos_abreviacao", first=True)
            split_sentences._nlp = nlp

        doc = split_sentences._nlp(text)
        sentences = [s.text.strip() for s in doc.sents if s.text.strip()]
        return _juntar_fragmentos(sentences)
    except Exception:
        # Fallback simples: divide em ., !, ? seguidos de espaço/maiúscula.
        raw = re.split(r"(?<=[.!?])\s+(?=[A-ZÀ-Ú0-9])", text.strip())
        return [s.strip() for s in raw if s.strip()]


# ----------------------------------------------------------------------
# Resultado estruturado
# ----------------------------------------------------------------------
@dataclass
class TextMetrics:
    text_perplexity: float
    burstiness: float
    n_sentences: int
    n_tokens: int
    n_descartadas: int = 0  # fragmentos curtos ignorados no cálculo
    sentence_perplexities: List[float] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "perplexity": self.text_perplexity,
            "burstiness": self.burstiness,
            "n_sentences": self.n_sentences,
            "n_tokens": self.n_tokens,
            "n_descartadas": self.n_descartadas,
        }


# ----------------------------------------------------------------------
# Classe principal
# ----------------------------------------------------------------------
class TucanoMetrics:
    """
    Encapsula o carregamento do Tucano e o cálculo de perplexidade
    e burstiness por texto, seguindo a Seção "Arquitetura da Interface
    de Cálculo de Métricas" do TCC.
    """

    def __init__(self, model_id: str = MODEL_ID, device: str | None = None):
        self.device = device or (
            "cuda" if torch.cuda.is_available()
            else "mps" if torch.backends.mps.is_available()
            else "cpu"
        )
        print(f"[TucanoMetrics] Carregando {model_id} em '{self.device}'...")

        self.tokenizer = AutoTokenizer.from_pretrained(model_id)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_id,
            torch_dtype=torch.float32,
        ).to(self.device)
        self.model.eval()

        print("[TucanoMetrics] Modelo carregado com sucesso.")

    # --------------------------------------------------------------
    @torch.no_grad()
    def sentence_perplexity(self, sentence: str) -> tuple[float, int]:
        """
        Calcula a perplexidade de UMA sentença, seguindo a definição
        clássica: exp(-1/n * soma(log p(token_i | token_<i)))

        Retorna (perplexidade, número_de_tokens).
        Sentenças com 1 token (ou vazias) são ignoradas pelo chamador,
        pois não há contexto suficiente para calcular log-probabilidade.
        """
        inputs = self.tokenizer(sentence, return_tensors="pt").to(self.device)
        input_ids = inputs["input_ids"]

        if input_ids.shape[1] < 2:
            return float("nan"), input_ids.shape[1]

        # Em um modelo causal, usar os mesmos input_ids como labels faz o
        # HuggingFace calcular a cross-entropy média de prever o token
        # seguinte a partir do anterior — exatamente a definição de
        # log-verossimilhança negativa média que a perplexidade usa.
        outputs = self.model(input_ids, labels=input_ids)
        neg_log_likelihood = outputs.loss.item()  # já é a média por token
        n_tokens = input_ids.shape[1]

        perplexity = float(torch.exp(torch.tensor(neg_log_likelihood)))
        return perplexity, n_tokens

    # --------------------------------------------------------------
    def analyze_text(self, text: str) -> TextMetrics:
        """
        Pipeline completo para um texto:
          1. segmentação em sentenças
          1b. descarte de fragmentos curtos (< MIN_TOKENS_SENTENCA)
          2. perplexidade por sentença
          3. perplexidade do texto = média ponderada pelo nº de tokens
          4. burstiness = desvio-padrão das perplexidades por sentença
        """
        sentences = split_sentences(text)

        sent_ppls: List[float] = []
        sent_weights: List[int] = []

        n_descartadas = 0
        for sent in sentences:
            ppl, n_tok = self.sentence_perplexity(sent)
            if ppl != ppl:  # NaN: sentença de 1 token, sem contexto
                n_descartadas += 1
                continue
            if n_tok < MIN_TOKENS_SENTENCA:  # fragmento de extração
                n_descartadas += 1
                continue
            sent_ppls.append(ppl)
            sent_weights.append(n_tok)

        if not sent_ppls:
            raise ValueError(
                "Nenhuma sentença válida encontrada (texto muito curto?)."
            )

        # Perplexidade do texto: média ponderada pelo número de tokens
        # de cada sentença (sentenças maiores pesam mais).
        total_tokens = sum(sent_weights)
        text_ppl = sum(p * w for p, w in zip(sent_ppls, sent_weights)) / total_tokens

        # Burstiness: dispersão das perplexidades sentença a sentença.
        # Requer pelo menos 2 sentenças para fazer sentido estatístico.
        burstiness = statistics.pstdev(sent_ppls) if len(sent_ppls) > 1 else 0.0

        return TextMetrics(
            text_perplexity=text_ppl,
            burstiness=burstiness,
            n_sentences=len(sent_ppls),
            n_tokens=total_tokens,
            n_descartadas=n_descartadas,
            sentence_perplexities=sent_ppls,
        )
