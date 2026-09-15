"""
gerar_claude.py
Gera textos sintéticos via API oficial da Anthropic (Claude)
para a parcela sintética do corpus do TCC, seguindo a distribuição
fixa de temas definida em common.py (9/9/8/8/8/8 = 50 textos).

Instalação necessária:
    pip install anthropic

Configuração necessária (defina sua chave de API como variável de
ambiente antes de rodar):
    export ANTHROPIC_API_KEY="sua-chave-aqui"

Uso:
    python gerar_claude.py --saida corpus

Observação: a API da Anthropic não expõe o parâmetro frequency_penalty,
por isso ele não é usado aqui -- ver justificativa na seção de
Implementação do TCC (paridade experimental entre as três APIs).
"""

import argparse
import time

import anthropic

from common import gerar_fila_temas, montar_prompt, registrar_historico, salvar_texto

MODELO = "claude-opus-5"
TEMPERATURA = 0.7
TOP_P = 1.0
MAX_TOKENS = 500
PROVEDOR = "claude"


def gerar(pasta_saida: str) -> None:
    client = anthropic.Anthropic()  # lê ANTHROPIC_API_KEY do ambiente automaticamente
    fila_temas = gerar_fila_temas()
    historico = {}
    contador_por_tema = {}
    total = len(fila_temas)

    for i, tema in enumerate(fila_temas, start=1):
        prompt = montar_prompt(tema, historico)

        try:
            resposta = client.messages.create(
                model=MODELO,
                max_tokens=MAX_TOKENS,
                temperature=TEMPERATURA,
                top_p=TOP_P,
                messages=[{"role": "user", "content": prompt}],
            )
            texto = resposta.content[0].text
        except Exception as erro:
            print(f"[{i}/{total}] Erro ao gerar texto para tema '{tema}': {erro}")
            time.sleep(5)
            continue

        indice = contador_por_tema.get(tema, 0) + 1
        contador_por_tema[tema] = indice
        registrar_historico(historico, tema, texto)

        caminho = salvar_texto(texto, PROVEDOR, tema, indice, pasta_saida)
        print(f"[{i}/{total}] Salvo: {caminho}")

        time.sleep(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Gera textos sintéticos via Claude (claude-3-5-sonnet), respeitando a distribuição fixa de temas."
    )
    parser.add_argument("--saida", type=str, default="corpus", help="Pasta raiz de saída do corpus.")
    args = parser.parse_args()

    gerar(args.saida)
