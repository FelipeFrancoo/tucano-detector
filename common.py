"""
common.py
Configurações e utilitários compartilhados pelos três scripts de geração
(ChatGPT, Claude, Gemini) usados para construir a parcela sintética do
corpus do TCC.

Coloque este arquivo na mesma pasta dos três scripts (gerar_chatgpt.py,
gerar_claude.py, gerar_gemini.py) -- eles importam funções daqui.
"""

import os
import random

# ---------------------------------------------------------------
# Distribuição fixa de temas e quantidade de textos por tema.
# Os MESMOS 6 temas e as MESMAS quotas são usados para os três
# modelos (ChatGPT, Claude, Gemini), garantindo que os três grupos
# sintéticos sejam gerados sobre exatamente os mesmos temas.
#
#   Tema                        | Textos por modelo
#   -----------------------------|-------------------
#   Inteligência Artificial      | 9
#   Aprendizado de Máquina       | 9
#   PLN                          | 8
#   Visão Computacional          | 8
#   Banco de Dados               | 8
#   Engenharia de Software       | 8
#   Total                        | 50
# ---------------------------------------------------------------
TEMAS_DISTRIBUICAO = {
    "Inteligência Artificial": 9,
    "Aprendizado de Máquina": 9,
    "Processamento de Linguagem Natural": 8,
    "Visão Computacional": 8,
    "Banco de Dados": 8,
    "Engenharia de Software": 8,
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
    "O texto deve conter entre 350 e 400 palavras.\n"
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

HISTORY_SIZE = 3  # quantas gerações anteriores citar como "já usadas" por tema

# ---------------------------------------------------------------
# Controle de tamanho dos textos gerados.
#
# O prompt pede entre 350 e 400 palavras, mas os modelos não
# respeitam essa faixa com exatidão. Aceita-se uma tolerância de 50
# palavras para cada lado; fora disso o texto é descartado e gerado
# de novo. Isso vale para os TRÊS modelos, de modo que o tamanho não
# vire uma variável descontrolada na comparação entre os grupos
# sintéticos (um texto muito mais longo que os outros distorce a
# perplexidade e o burstiness medidos depois).
# ---------------------------------------------------------------
PALAVRAS_ALVO_MIN = 350
PALAVRAS_ALVO_MAX = 400
TOLERANCIA_PALAVRAS = 50

MIN_PALAVRAS = PALAVRAS_ALVO_MIN - TOLERANCIA_PALAVRAS  # 300
MAX_PALAVRAS = PALAVRAS_ALVO_MAX + TOLERANCIA_PALAVRAS  # 450

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


def registrar_historico(historico: dict, tema: str, texto: str, n_palavras: int = 20) -> None:
    """Guarda as primeiras palavras do texto gerado como um resumo do
    que já foi abordado, para uso na próxima chamada sobre o mesmo tema."""
    resumo = " ".join(texto.split()[:n_palavras])
    historico.setdefault(tema, []).append(resumo)


def salvar_texto(texto: str, provedor: str, tema: str, indice: int, pasta_saida: str) -> str:
    """Salva o texto gerado em pasta_saida/provedor/*.txt, pronto para
    ser processado pelo batch_analyze.py."""
    pasta_provedor = os.path.join(pasta_saida, provedor)
    os.makedirs(pasta_provedor, exist_ok=True)
    tema_slug = tema.lower().replace(" ", "_")
    nome_arquivo = f"{provedor}_{tema_slug}_{indice:03d}.txt"
    caminho = os.path.join(pasta_provedor, nome_arquivo)
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(texto.strip())
    return caminho
