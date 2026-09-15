"""
gerar_gemini.py
Gera textos sintéticos via API oficial do Google (Gemini)
para a parcela sintética do corpus do TCC, seguindo a distribuição
fixa de temas definida em common.py (9/9/8/8/8/8 = 50 textos).

Instalação necessária:
    pip install google-genai

Configuração necessária (defina sua chave de API como variável de
ambiente antes de rodar):
    export GEMINI_API_KEY="sua-chave-aqui"

Uso:
    python gerar_gemini.py --saida corpus
    python gerar_gemini.py --saida corpus --limite-usd 3
"""

import argparse
import time

from google import genai
from google.genai import types

from common import gerar_fila_temas, montar_prompt, registrar_historico, salvar_texto

MODELO = "gemini-3.1-pro-preview"
TEMPERATURA = 1.0
TOP_P = 1.0
# No Gemini 3, os tokens de "raciocínio" (thinking) contam dentro do
# max_output_tokens. Com 2000, o raciocínio consumia boa parte do limite
# e o texto final saía cortado. 350-400 palavras em português ficam em
# ~700-900 tokens; 4096 deixa folga para o raciocínio sem gastar demais.
MAX_OUTPUT_TOKENS = 8192
PROVEDOR = "gemini"

MIN_PALAVRAS = 300  # abaixo disso o texto é considerado curto/cortado e é gerado de novo
MAX_TENTATIVAS = 3  # tentativas por texto antes de desistir daquele item da fila

# Preços do gemini-3.1-pro-preview (prompts <= 200k tokens), em US$ por token.
# Tokens de raciocínio são cobrados como saída.
PRECO_ENTRADA_USD = 2.00 / 1_000_000
PRECO_SAIDA_USD = 12.00 / 1_000_000
LIMITE_USD_PADRAO = 4.00  # ~R$ 22, deixa margem dentro dos R$ 30 de saldo


def uso_da_resposta(resposta) -> tuple:
    """Retorna (tokens de entrada, tokens do texto, tokens de raciocínio)."""
    uso = resposta.usage_metadata
    if uso is None:
        return 0, 0, 0
    return (
        uso.prompt_token_count or 0,
        uso.candidates_token_count or 0,
        uso.thoughts_token_count or 0,
    )


def custo_da_resposta(resposta) -> float:
    entrada, texto, raciocinio = uso_da_resposta(resposta)
    return entrada * PRECO_ENTRADA_USD + (texto + raciocinio) * PRECO_SAIDA_USD


def gerar(pasta_saida: str, limite_usd: float) -> None:
    client = genai.Client()  # lê GEMINI_API_KEY do ambiente automaticamente
    fila_temas = gerar_fila_temas()
    historico = {}
    contador_por_tema = {}
    total = len(fila_temas)
    gasto = 0.0

    for i, tema in enumerate(fila_temas, start=1):
        prompt = montar_prompt(tema, historico)
        texto = None

        for tentativa in range(1, MAX_TENTATIVAS + 1):
            if gasto >= limite_usd:
                print(f"Limite de gasto atingido (US$ {gasto:.2f} de US$ {limite_usd:.2f}). Parando.")
                return

            try:
                resposta = client.models.generate_content(
                    model=MODELO,
                    contents=prompt,
                    config={
                        "temperature": TEMPERATURA,
                        "top_p": TOP_P,
                        "max_output_tokens": MAX_OUTPUT_TOKENS,
                        "thinking_config": {"thinking_level": "low"},
                    },
                )
            except Exception as erro:
                print(f"[{i}/{total}] Tentativa {tentativa}: erro ao gerar texto para tema '{tema}': {erro}")
                time.sleep(5)
                continue

            gasto += custo_da_resposta(resposta)
            candidato = resposta.text or ""
            n_palavras = len(candidato.split())
            _, tokens_texto, tokens_raciocinio = uso_da_resposta(resposta)
            motivo = resposta.candidates[0].finish_reason if resposta.candidates else None
            detalhes = f"{n_palavras} palavras, {tokens_texto} tokens de texto + {tokens_raciocinio} de raciocínio"

            if motivo == types.FinishReason.MAX_TOKENS:
                print(f"[{i}/{total}] Tentativa {tentativa}: texto cortado pelo limite de tokens ({detalhes}).")
            elif n_palavras < MIN_PALAVRAS:
                print(f"[{i}/{total}] Tentativa {tentativa}: texto curto demais ({detalhes}).")
            else:
                texto = candidato
                break

            time.sleep(1)

        if texto is None:
            print(f"[{i}/{total}] Desistindo do tema '{tema}' após {MAX_TENTATIVAS} tentativas.")
            continue

        indice = contador_por_tema.get(tema, 0) + 1
        contador_por_tema[tema] = indice
        registrar_historico(historico, tema, texto)

        caminho = salvar_texto(texto, PROVEDOR, tema, indice, pasta_saida)
        print(f"[{i}/{total}] Salvo: {caminho} ({detalhes}; gasto acumulado US$ {gasto:.3f})")

        time.sleep(1)

    print(f"Concluído. Gasto estimado: US$ {gasto:.3f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Gera textos sintéticos via Gemini (gemini-3.1-pro-preview), respeitando a distribuição fixa de temas."
    )
    parser.add_argument("--saida", type=str, default="corpus", help="Pasta raiz de saída do corpus.")
    parser.add_argument(
        "--limite-usd",
        type=float,
        default=LIMITE_USD_PADRAO,
        help="Para a geração quando o gasto estimado atingir este valor (US$).",
    )
    args = parser.parse_args()

    gerar(args.saida, args.limite_usd)
