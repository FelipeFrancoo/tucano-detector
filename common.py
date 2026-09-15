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
    "Escreva um resumo acadêmico, em português formal, sobre o seguinte tema:\n"
    '"{tema}"\n'
    "O texto deve simular um resumo submetido a um congresso ou simpósio "
    "científico brasileiro da área de Computação, seguindo a estrutura "
    "típica desse gênero acadêmico.\n"
    "O resumo deve apresentar, de forma natural e coerente:\n\n"
    "* contextualização do tema;\n"
    "* apresentação de um problema ou desafio relacionado ao tema;\n"
    "* objetivo do trabalho;\n"
    "* metodologia proposta ou utilizada;\n"
    "* contribuição ou resultado esperado.\n\n"
    "Produza um texto original e independente. Não copie, reproduza ou "
    "parafraseie textos publicados. Não faça referência a artigos, "
    "autores ou trabalhos específicos.\n"
    "Para cada geração, desenvolva uma abordagem diferente dentro do "
    "mesmo tema, variando o problema investigado, o objetivo, a "
    "metodologia, a aplicação e a contribuição esperada. Evite repetir "
    "ideias, exemplos, aplicações ou estruturas argumentativas "
    "utilizadas em outras gerações.{aviso}\n"
    "O texto deve conter entre 350 e 400 palavras.\n"
    "Escreva somente o resumo acadêmico, sem título, comentários, "
    "explicações ou observações adicionais."
)

HISTORY_SIZE = 3  # quantas gerações anteriores citar como "já usadas" por tema


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
