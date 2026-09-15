"""
gerar_chatgpt.py
Gera textos sintéticos via API oficial da OpenAI (ChatGPT / gpt-4o)
para a parcela sintética do corpus do TCC, seguindo a distribuição
fixa de temas definida em common.py (9/9/8/8/8/8 = 50 textos).

Instalação necessária:
    pip install openai

Configuração necessária (defina sua chave de API como variável de
ambiente antes de rodar):
    export OPENAI_API_KEY="sua-chave-aqui"

Uso:
    python gerar_chatgpt.py --saida corpus
"""

import argparse
import time

from openai import OpenAI

from common import gerar_fila_temas, montar_prompt, registrar_historico, salvar_texto

MODELO = "gpt-5.6-sol"
TEMPERATURA = 0.7
TOP_P = 1.0
MAX_TOKENS = 500
PROVEDOR = "chatgpt"


def gerar(pasta_saida: str) -> None:
    client = OpenAI()  # lê OPENAI_API_KEY do ambiente automaticamente
    fila_temas = gerar_fila_temas()
    historico = {}
    contador_por_tema = {}
    total = len(fila_temas)

    for i, tema in enumerate(fila_temas, start=1):
        prompt = montar_prompt(tema, historico)

        try:
            resposta = client.chat.completions.create(
                model=MODELO,
                messages=[{"role": "user", "content": prompt}],
                temperature=TEMPERATURA,
                top_p=TOP_P,
                max_tokens=MAX_TOKENS,
            )
            texto = resposta.choices[0].message.content
        except Exception as erro:
            print(f"[{i}/{total}] Erro ao gerar texto para tema '{tema}': {erro}")
            time.sleep(5)
            continue

        indice = contador_por_tema.get(tema, 0) + 1
        contador_por_tema[tema] = indice
        registrar_historico(historico, tema, texto)

        caminho = salvar_texto(texto, PROVEDOR, tema, indice, pasta_saida)
        print(f"[{i}/{total}] Salvo: {caminho}")

        time.sleep(1)  # pequena pausa para respeitar limites de requisição


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Gera textos sintéticos via ChatGPT (gpt-4o), respeitando a distribuição fixa de temas."
    )
    parser.add_argument("--saida", type=str, default="corpus", help="Pasta raiz de saída do corpus.")
    args = parser.parse_args()

    gerar(args.saida)
