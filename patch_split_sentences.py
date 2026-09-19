# -*- coding: utf-8 -*-
"""
patch_split_sentences.py
------------------------
Substitui a função `split_sentences` do metrics.py.

PROBLEMA
O spaCy quebra sentença depois de "et al." e, às vezes, depois de dois-pontos.
Isso produz fragmentos que não são sentenças e que recebem perplexidade
altíssima por não terem contexto:

    128.05  "Neste sentido, Araújo et al."
    125.73  "Araújo et al."
    189.21  "o ramo de apostas."

Os três vieram de frases inteiras e corretas no arquivo .txt — o corte foi do
segmentador, não da extração. Como burstiness é o desvio-padrão das
perplexidades por sentença, esses cortes inflam a métrica sem que haja
nada de errado com o texto.

O `MIN_TOKENS_SENTENCA = 5` não pega: "o ramo de apostas ." tem exatamente 5
tokens, e "Araújo et al ." tem 4 mas "Neste sentido , Araújo et al ." tem 6.

SOLUÇÃO
Um componente que roda ANTES do parser e proíbe início de sentença logo depois
de abreviação conhecida e de dois-pontos. O parser continua decidindo todo o
resto; só esses pontos ficam bloqueados.

COMO APLICAR
Substitua a função `split_sentences` do metrics.py por esta. O resto do
arquivo não muda.
"""

import re
from typing import List

# Tokens depois dos quais o spaCy não deve começar sentença nova.
NAO_TERMINA_SENTENCA = {
    "al.", "al", "etc.", "fig.", "figs.", "tab.", "eq.", "ref.", "cap.",
    "p.", "pp.", "vs.", "cf.", "ed.", "eds.", "vol.", "no.", "núm.",
    "dr.", "dra.", "sr.", "sra.", "prof.", "profa.", "aprox.",
    "e.g.", "i.e.", "ca.", "séc.",
    ":",  # "…de uma grande área: o ramo de apostas." é uma sentença só
}


def _registrar_componente():
    """Registra o componente no spaCy uma única vez."""
    import spacy

    if "nao_quebrar_apos_abreviacao" in spacy.registry.factories:
        return

    @spacy.Language.component("nao_quebrar_apos_abreviacao")
    def nao_quebrar_apos_abreviacao(doc):
        for i in range(len(doc) - 1):
            if doc[i].text.lower() in NAO_TERMINA_SENTENCA:
                doc[i + 1].is_sent_start = False
        return doc


def split_sentences(text: str) -> List[str]:
    """
    Segmenta o texto em sentenças.

    Usa spaCy (mais robusto para português) com um componente extra que impede
    quebra depois de abreviação e de dois-pontos. Sem o modelo do spaCy,
    cai para uma divisão por regex.
    """
    try:
        import spacy

        if not hasattr(split_sentences, "_nlp"):
            _registrar_componente()
            nlp = spacy.load(
                "pt_core_news_sm", disable=["ner", "lemmatizer", "tagger"]
            )
            # precisa rodar antes de quem define os limites de sentença
            antes = "parser" if "parser" in nlp.pipe_names else None
            if antes:
                nlp.add_pipe("nao_quebrar_apos_abreviacao", before=antes)
            else:
                nlp.add_pipe("nao_quebrar_apos_abreviacao", first=True)
            split_sentences._nlp = nlp

        doc = split_sentences._nlp(text)
        return [s.text.strip() for s in doc.sents if s.text.strip()]
    except Exception:
        raw = re.split(r"(?<=[.!?])\s+(?=[A-ZÀ-Ú0-9])", text.strip())
        return [s.strip() for s in raw if s.strip()]


# ----------------------------------------------------------------------
# Conferência rápida: rode este arquivo direto para ver o efeito.
# ----------------------------------------------------------------------
if __name__ == "__main__":
    CASOS = [
        "Neste sentido, Araújo et al. propuseram modelos alternativos para "
        "estimativa de probabilidade de bloqueio com base em treinamento.",
        "O futebol é um esporte popular no mundo todo e, por isso, desperta "
        "interesse de uma grande área: o ramo de apostas.",
        "A primeira etapa foi descrita por Silva et al. em trabalho anterior. "
        "A segunda etapa é apresentada aqui.",
    ]
    for texto in CASOS:
        partes = split_sentences(texto)
        print(f"\n{len(partes)} sentença(s):")
        for p in partes:
            print("   -", p)
