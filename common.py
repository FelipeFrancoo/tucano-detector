"""
common.py
Configurações e utilitários compartilhados pelos três scripts de geração
(ChatGPT, Claude, Gemini) usados para construir a parcela sintética do
corpus do TCC.

Coloque este arquivo na mesma pasta dos três scripts (gerar_chatgpt.py,
gerar_claude.py, gerar_gemini.py) -- eles importam funções daqui.
"""

import json
import os
import random
import re
import unicodedata

# ---------------------------------------------------------------
# Distribuição fixa de temas e quantidade de textos por tema.
# Os MESMOS 7 temas e as MESMAS quotas são usados para os três
# modelos (ChatGPT, Claude, Gemini), garantindo que os três grupos
# sintéticos sejam gerados sobre exatamente os mesmos temas do
# corpus humano.
#
#   Tema                         | Por modelo | Humano
#   ------------------------------|------------|--------
#   Inteligência Artificial       |      8     |   22
#   Aprendizado de Máquina        |      8     |   22
#   PLN                           |      7     |   22
#   Visão Computacional           |      7     |   22
#   Banco de Dados                |      7     |   22
#   Redes de Computadores         |      7     |   22
#   Engenharia de Software        |      6     |   18
#   Total                         |     50     |  150
#
# A quota menor de Engenharia de Software acompanha o corpus humano:
# os eventos brasileiros da área (SBES, SBQS) migraram para o inglês
# antes dos demais, e não há artigos técnicos em português suficientes
# nas edições anteriores a 2022. É restrição da fonte, não escolha.
# ---------------------------------------------------------------
TEMAS_DISTRIBUICAO = {
    "Inteligência Artificial": 8,
    "Aprendizado de Máquina": 8,
    "Processamento de Linguagem Natural": 7,
    "Visão Computacional": 7,
    "Banco de Dados": 7,
    "Redes de Computadores": 7,
    "Engenharia de Software": 6,
}

TOTAL_TEXTOS = sum(TEMAS_DISTRIBUICAO.values())  # 50

# ---------------------------------------------------------------
# Prompt fixo, idêntico para os três modelos (reproduzido no
# Apêndice do TCC). O trecho {aviso} é preenchido dinamicamente
# com um resumo das últimas abordagens já geradas naquele tema --
# isso é necessário porque cada chamada de API é isolada e não tem
# memória de chamadas anteriores, então "evitar repetição" só
# funciona se o próprio script reinjetar esse contexto no prompt.
# ---------------------------------------------------------------
PROMPT_TEMPLATE = (
    "Você é um pesquisador da área de Ciência da Computação.\n"
    "Escreva a seção de Introdução de um artigo científico, em português "
    "formal, sobre o seguinte tema:\n"
    '"{tema}"\n'
    "O texto deve simular a introdução de um artigo técnico submetido a um "
    "congresso ou simpósio científico brasileiro da área de Computação, "
    "seguindo a estrutura típica desse gênero acadêmico.\n"
    "A introdução deve apresentar, de forma natural e coerente:\n\n"
    "* contextualização da área e de sua relevância;\n"
    "* apresentação de um problema ou desafio em aberto;\n"
    "* a lacuna que o trabalho pretende preencher;\n"
    "* o objetivo do trabalho e a abordagem proposta.\n\n"
    "Não escreva resumo, conclusão nem resultados obtidos: a introdução "
    "antecede o restante do artigo.\n"
    "Não descreva a organização do artigo (nada como \"este trabalho está "
    "organizado como segue\").\n"
    "Não inclua citações, referências bibliográficas, nomes de autores nem "
    "anos, em nenhum formato ([1], (Autor, 2020), Autor et al.).\n"
    "Não use títulos, subtítulos, listas ou qualquer marcação; escreva em "
    "parágrafos corridos.\n"
    "Produza um texto original e independente. Não copie, reproduza ou "
    "parafraseie textos publicados. Não faça referência a artigos, "
    "autores ou trabalhos específicos.\n"
    "Para cada geração, desenvolva uma abordagem diferente dentro do "
    "mesmo tema, variando o problema investigado, o objetivo, a "
    "metodologia, a aplicação e a contribuição esperada. Evite repetir "
    "ideias, exemplos, aplicações ou estruturas argumentativas "
    "utilizadas em outras gerações.{aviso}\n"
    "O texto deve conter entre 300 e 380 palavras.\n"
    "Escreva somente a introdução, sem título, comentários, "
    "explicações ou observações adicionais."
)

# ---------------------------------------------------------------
# Por que "Introdução" e não "resumo":
# o corpus humano é composto pelas seções de INTRODUÇÃO dos artigos
# dos anais, com citações removidas e sem a frase de organização do
# artigo. Um prompt que pedisse um resumo produziria outro gênero
# textual (com metodologia, resultados e conclusão), e o classificador
# passaria a separar "resumo vs. introdução" em vez de "IA vs. humano".
# As proibições de citação, de marcação e de roadmap existem para que
# o texto gerado tenha exatamente a mesma forma do texto humano depois
# da extração.
# ---------------------------------------------------------------

# Quantas abordagens anteriores do MESMO tema citar no prompt. A maior quota
# por tema é 8, então 8 cobre todas as anteriores do tema.
HISTORY_SIZE = 8

# ---------------------------------------------------------------
# Controle de tamanho dos textos gerados.
#
# O prompt pede entre 300 e 380 palavras, mas os modelos não
# respeitam essa faixa com exatidão. Aceita-se uma tolerância de 50
# palavras para cada lado; fora disso o texto é descartado e gerado
# de novo. Isso vale para os TRÊS modelos, de modo que o tamanho não
# vire uma variável descontrolada na comparação entre os grupos
# sintéticos (um texto muito mais longo que os outros distorce a
# perplexidade e o burstiness medidos depois).
# ---------------------------------------------------------------
# Faixa centrada na mediana do corpus humano final (336 palavras).
# Com a tolerância, aceita 250-430 — cobre 148 dos 150 textos humanos.
PALAVRAS_ALVO_MIN = 300
PALAVRAS_ALVO_MAX = 380
TOLERANCIA_PALAVRAS = 50

MIN_PALAVRAS = PALAVRAS_ALVO_MIN - TOLERANCIA_PALAVRAS  # 250
MAX_PALAVRAS = PALAVRAS_ALVO_MAX + TOLERANCIA_PALAVRAS  # 430

MAX_TENTATIVAS = 3  # tentativas por texto antes de desistir daquele item da fila


def conferir_tamanho(texto: str) -> str:
    """Verifica se o texto está dentro da faixa aceita de palavras.

    Retorna uma string vazia quando o texto é válido, ou uma mensagem
    explicando o motivo da rejeição (curto ou longo demais)."""
    n_palavras = len(texto.split())
    if n_palavras < MIN_PALAVRAS:
        return f"curto demais ({n_palavras} palavras, mínimo {MIN_PALAVRAS})"
    if n_palavras > MAX_PALAVRAS:
        return f"longo demais ({n_palavras} palavras, máximo {MAX_PALAVRAS})"
    return ""


def gerar_fila_temas() -> list:
    """Monta a fila de temas a serem gerados, respeitando exatamente as
    quotas de TEMAS_DISTRIBUICAO, em ordem embaralhada (para não gerar
    todos os textos do mesmo tema em sequência)."""
    fila = []
    for tema, quantidade in TEMAS_DISTRIBUICAO.items():
        fila.extend([tema] * quantidade)
    random.shuffle(fila)
    return fila


def montar_prompt(tema: str, historico: dict) -> str:
    """Monta o prompt final para um tema, injetando um aviso sobre
    abordagens já usadas anteriormente nesse mesmo tema."""
    anteriores = historico.get(tema, [])[-HISTORY_SIZE:]
    if anteriores:
        lista = "; ".join(f'"{a}"' for a in anteriores)
        aviso = (
            f" Evite especificamente abordagens semelhantes às seguintes, "
            f"já usadas neste tema: {lista}."
        )
    else:
        aviso = ""
    return PROMPT_TEMPLATE.format(tema=tema, aviso=aviso)


# Frase em que o texto declara o que o trabalho propõe. É ela que resume a
# ABORDAGEM — as primeiras palavras do texto são só contextualização genérica
# ("A Inteligência Artificial tem se consolidado...") e não servem para isso.
_FRASE_OBJETIVO = re.compile(r"\b(este|presente|nosso) (trabalho|artigo|estudo)|tem como objetivo|"
                             r"\bo objetivo (é|deste|do presente|principal)|\bpropõe\b|\bpropomos\b", re.I)


def resumo_da_abordagem(texto: str) -> str:
    """Frase de objetivo do texto (a primeira que declarar o que o trabalho
    propõe); na falta dela, a penúltima sentença."""
    sentencas = [x.strip() for x in re.split(r"(?<=[.!?])\s+(?=[A-ZÀ-Ý])", texto.strip()) if x.strip()]
    frase = next((s for s in sentencas if _FRASE_OBJETIVO.search(s)),
                 sentencas[-2] if len(sentencas) > 1 else sentencas[0])
    # Fica só com o QUE é proposto. O começo da frase ("Para preencher essa
    # lacuna, o presente trabalho tem como objetivo propor...") é fórmula do
    # próprio modelo; devolvê-lo no prompt reforçaria a repetição dessa fórmula.
    m = re.search(r"\b(?:propor|propõe|propomos|desenvolver|apresentar|investigar|avaliar)\s+", frase, re.I)
    return frase[m.end():].rstrip(".") if m else frase.rstrip(".")


def registrar_historico(historico: dict, tema: str, texto: str) -> None:
    """Guarda a abordagem do texto recém-gerado, para a próxima chamada do mesmo tema."""
    historico.setdefault(tema, []).append(resumo_da_abordagem(texto))


def carregar_historico(pasta_saida: str, provedor: str) -> dict:
    """Reconstrói o histórico a partir dos textos JÁ SALVOS em disco.

    Sem isso, cada execução começava com o histórico vazio e um lote não
    sabia o que os lotes anteriores tinham abordado — foi assim que dois
    textos de Engenharia de Software, de lotes diferentes, saíram com a
    mesma proposta."""
    historico = {}
    for tema in TEMAS_DISTRIBUICAO:
        pasta = os.path.join(pasta_saida, provedor)
        for nome in sorted(arquivos_do_tema(pasta_saida, provedor, tema)):
            with open(os.path.join(pasta, nome), encoding="utf-8") as f:
                registrar_historico(historico, tema, f.read())
    return historico


def arquivos_do_tema(pasta_saida: str, provedor: str, tema: str) -> list:
    """Arquivos já gerados para um tema. Compara os nomes em NFC porque o
    macOS pode devolver o nome acentuado decomposto ("ma\u0301quina")."""
    pasta = os.path.join(pasta_saida, provedor)
    if not os.path.isdir(pasta):
        return []
    prefixo = unicodedata.normalize("NFC", f"{provedor}_{tema.lower().replace(' ', '_')}_")
    return [n for n in os.listdir(pasta)
            if n.endswith(".txt") and unicodedata.normalize("NFC", n).startswith(prefixo)]


def normalizar_espacos(texto: str) -> str:
    """Junta os parágrafos num bloco só, como ficam os textos humanos depois da
    extração do PDF. Nenhuma palavra muda: só quebras de linha e espaços."""
    return re.sub(r"\s+", " ", texto).strip()


def salvar_texto(texto: str, provedor: str, tema: str, indice: int, pasta_saida: str) -> str:
    """Salva o texto gerado em pasta_saida/provedor/*.txt, pronto para
    ser processado pelo batch_analyze.py."""
    pasta_provedor = os.path.join(pasta_saida, provedor)
    os.makedirs(pasta_provedor, exist_ok=True)
    tema_slug = tema.lower().replace(" ", "_")
    nome_arquivo = f"{provedor}_{tema_slug}_{indice:03d}.txt"
    caminho = os.path.join(pasta_provedor, nome_arquivo)
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(normalizar_espacos(texto) + "\n")
    return caminho


# ---------------------------------------------------------------
# Controle de gasto ACUMULADO entre execuções.
#
# O limite por execução (--limite-brl) não basta quando a geração é
# feita em vários lotes: cada execução começaria do zero. Por isso o
# gasto estimado de cada chamada é gravado em gastos_api.json, e os
# scripts param quando o total gravado atinge o orçamento do provedor.
#
# O valor é uma ESTIMATA calculada a partir dos tokens informados pela
# API e dos preços de tabela. A fonte oficial é o painel de faturamento
# do provedor — conferir de tempos em tempos.
# ---------------------------------------------------------------
COTACAO_USD_BRL = 5.11  # dólar comercial em 21/09/2026 (atualizar se mudar muito)
ARQUIVO_GASTOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gastos_api.json")


def _ler_gastos() -> dict:
    try:
        with open(ARQUIVO_GASTOS, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def gasto_registrado(provedor: str) -> float:
    """Gasto acumulado do provedor, em US$."""
    return float(_ler_gastos().get(provedor, 0.0))


def registrar_gasto(provedor: str, usd: float) -> None:
    """Soma o custo de UMA chamada ao total gravado. Gravar a cada chamada
    (e não no fim) garante que uma execução interrompida não perca a conta."""
    dados = _ler_gastos()
    dados[provedor] = round(float(dados.get(provedor, 0.0)) + usd, 6)
    with open(ARQUIVO_GASTOS, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=2)
