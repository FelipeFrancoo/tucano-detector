"""
gerar_gemini.py
Gera textos sintéticos via API oficial do Google (Gemini)
para a parcela sintética do corpus do TCC, usando os temas definidos
em common.py. Por padrão gera apenas 5 textos (um por tema, em temas
diferentes), cada um salvo em seu próprio arquivo .txt.

Instalação necessária:
    pip install google-genai

Configuração necessária (defina sua chave de API como variável de
ambiente antes de rodar):
    export GEMINI_API_KEY="sua-chave-aqui"

Uso:
    python gerar_gemini.py --saida corpus
    python gerar_gemini.py --saida corpus --quantidade 5
    python gerar_gemini.py --saida corpus --quantidade 5 --limite-brl 2
"""

import argparse
import glob
import os
import random
import time

from google import genai
from google.genai import types

from common import (
    MAX_TENTATIVAS,
    TEMAS_DISTRIBUICAO,
    conferir_tamanho,
    montar_prompt,
    registrar_historico,
    arquivos_do_tema,
    carregar_historico,
    salvar_texto,
    COTACAO_USD_BRL,
    gasto_registrado,
    registrar_gasto,
)

MODELO = "gemini-3.1-pro-preview"
# Mesma temperatura nos três provedores (valor padrão da API).
TEMPERATURA = 1.0
# No Gemini 3, os tokens de "raciocínio" (thinking) contam dentro do
# max_output_tokens. Com 2000, o raciocínio consumia boa parte do limite
# e o texto final saía cortado. 300-380 palavras em português ficam em
# ~700-900 tokens; 4096 deixa folga para o raciocínio sem gastar demais.
MAX_OUTPUT_TOKENS = 8192
PROVEDOR = "gemini"

QUANTIDADE_PADRAO = 5  # quantos textos gerar nesta execução (1 arquivo .txt por texto)
# A faixa aceita de palavras e o número de tentativas vêm de common.py,
# para que os três modelos usem exatamente o mesmo critério.

# Preços do gemini-3.1-pro-preview (prompts <= 200k tokens), em US$ por token.
# Tokens de raciocínio são cobrados como saída.
PRECO_ENTRADA_USD = 2.00 / 1_000_000
PRECO_SAIDA_USD = 12.00 / 1_000_000
# Orçamento em REAIS. O saldo da conta é R$ 25,96; o teto de R$ 20,00 deixa
# margem para impostos, variação do câmbio e a imprecisão da estimativa.
ORCAMENTO_TOTAL_BRL = 20.00      # teto somado de TODAS as execuções
LIMITE_BRL_POR_EXECUCAO = 2.00   # teto de uma única execução
CUSTO_INICIAL_ESTIMADO_USD = 0.05  # margem de segurança antes da 1ª chamada


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


def montar_fila(quantidade: int, pasta_saida: str) -> list:
    """Monta a fila com até `quantidade` temas, descontando o que já foi gerado
    em execuções anteriores, para que o total por tema nunca passe da quota de
    common.py. Os temas saem em rodadas embaralhadas: só se repete um tema
    depois que todos os outros com quota restante já foram usados."""
    restantes = {tema: max(0, qtd - len(arquivos_do_tema(pasta_saida, PROVEDOR, tema)))
                 for tema, qtd in TEMAS_DISTRIBUICAO.items()}
    print("Faltam por tema:", ", ".join(f"{t} {q}" for t, q in restantes.items()),
          f"(total {sum(restantes.values())})")
    fila = []
    while len(fila) < quantidade and any(restantes.values()):
        rodada = [tema for tema, qtd in restantes.items() if qtd > 0]
        random.shuffle(rodada)
        for tema in rodada:
            if len(fila) >= quantidade:
                break
            fila.append(tema)
            restantes[tema] -= 1
    return fila


def proximo_indice(pasta_saida: str, tema: str) -> int:
    """Descobre o próximo índice livre para o tema, olhando os arquivos já
    salvos em execuções anteriores. Sem isso, uma nova execução começaria
    de novo no 001 e sobrescreveria os textos já gerados."""
    tema_slug = tema.lower().replace(" ", "_")
    padrao = os.path.join(pasta_saida, PROVEDOR, f"{PROVEDOR}_{tema_slug}_*.txt")
    maior = 0
    for caminho in glob.glob(padrao):
        sufixo = os.path.splitext(os.path.basename(caminho))[0].rsplit("_", 1)[-1]
        if sufixo.isdigit():
            maior = max(maior, int(sufixo))
    return maior + 1


def brl(usd: float) -> str:
    return f"R$ {usd * COTACAO_USD_BRL:.2f}"


def gerar(pasta_saida: str, limite_brl: float, quantidade: int) -> None:
    anterior = gasto_registrado(PROVEDOR)
    saldo_brl = ORCAMENTO_TOTAL_BRL - anterior * COTACAO_USD_BRL
    if saldo_brl <= 0:
        print(f"Orçamento total esgotado: {brl(anterior)} de R$ {ORCAMENTO_TOTAL_BRL:.2f}. "
              f"Para continuar, aumente ORCAMENTO_TOTAL_BRL em gerar_gemini.py.")
        return
    limite_usd = min(limite_brl, saldo_brl) / COTACAO_USD_BRL
    print(f"Gasto registrado até agora: {brl(anterior)} de R$ {ORCAMENTO_TOTAL_BRL:.2f} "
          f"(restam R$ {saldo_brl:.2f}). Limite desta execução: {brl(limite_usd)}.")

    fila_temas = montar_fila(quantidade, pasta_saida)
    if not fila_temas:
        print("Todas as quotas já foram atingidas. Nada a gerar.")
        return

    client = genai.Client()  # lê GEMINI_API_KEY do ambiente automaticamente
    historico = carregar_historico(pasta_saida, PROVEDOR)  # inclui os lotes anteriores
    contador_por_tema = {}
    total = len(fila_temas)
    gasto = 0.0
    maior_chamada = CUSTO_INICIAL_ESTIMADO_USD  # usada para não ultrapassar o teto

    for i, tema in enumerate(fila_temas, start=1):
        prompt = montar_prompt(tema, historico)
        texto = None
        detalhes = ""

        for tentativa in range(1, MAX_TENTATIVAS + 1):
            # para ANTES de uma chamada que possa estourar o limite
            if gasto + maior_chamada > limite_usd:
                print(f"Limite desta execução atingido ({brl(gasto)} de {brl(limite_usd)}). Parando.")
                print(f"Total acumulado: {brl(gasto_registrado(PROVEDOR))} de R$ {ORCAMENTO_TOTAL_BRL:.2f}.")
                return

            try:
                resposta = client.models.generate_content(
                    model=MODELO,
                    contents=prompt,
                    config={
                        "temperature": TEMPERATURA,
                        "max_output_tokens": MAX_OUTPUT_TOKENS,
                        "thinking_config": {"thinking_level": "low"},
                        # não usamos ferramentas; desligar evita o aviso de AFC do SDK
                        "automatic_function_calling": {"disable": True},
                    },
                )
            except Exception as erro:
                print(f"[{i}/{total}] Tentativa {tentativa}: erro ao gerar texto para tema '{tema}': {erro}")
                time.sleep(5)
                continue

            custo = custo_da_resposta(resposta)
            gasto += custo
            maior_chamada = max(maior_chamada, custo)
            registrar_gasto(PROVEDOR, custo)

            candidato = resposta.text or ""
            n_palavras = len(candidato.split())
            _, tokens_texto, tokens_raciocinio = uso_da_resposta(resposta)
            motivo = resposta.candidates[0].finish_reason if resposta.candidates else None
            detalhes = (f"{n_palavras} palavras, {tokens_texto} tokens de texto + "
                        f"{tokens_raciocinio} de raciocínio, {brl(custo)}")

            problema = conferir_tamanho(candidato)
            if motivo == types.FinishReason.MAX_TOKENS:
                print(f"[{i}/{total}] Tentativa {tentativa}: texto cortado pelo limite de tokens ({detalhes}).")
            elif problema:
                print(f"[{i}/{total}] Tentativa {tentativa}: texto {problema} ({detalhes}).")
            else:
                texto = candidato
                break

            time.sleep(1)

        if texto is None:
            print(f"[{i}/{total}] Desistindo do tema '{tema}' após {MAX_TENTATIVAS} tentativas.")
            continue

        indice = contador_por_tema.get(tema) or proximo_indice(pasta_saida, tema)
        contador_por_tema[tema] = indice + 1
        registrar_historico(historico, tema, texto)

        caminho = salvar_texto(texto, PROVEDOR, tema, indice, pasta_saida)
        print(f"[{i}/{total}] Salvo: {caminho} ({detalhes}; nesta execução {brl(gasto)})")

        time.sleep(1)

    print(f"Concluído. Nesta execução: {brl(gasto)}. "
          f"Total acumulado: {brl(gasto_registrado(PROVEDOR))} de R$ {ORCAMENTO_TOTAL_BRL:.2f}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Gera textos sintéticos via Gemini (gemini-3.1-pro-preview), um arquivo .txt por texto."
    )
    parser.add_argument("--saida", type=str, default="corpus", help="Pasta raiz de saída do corpus.")
    parser.add_argument(
        "--quantidade",
        type=int,
        default=QUANTIDADE_PADRAO,
        help="Quantos textos gerar (cada um em um arquivo separado).",
    )
    parser.add_argument(
        "--limite-brl",
        type=float,
        default=LIMITE_BRL_POR_EXECUCAO,
        help="Teto de gasto desta execução, em reais. O teto total fica em ORCAMENTO_TOTAL_BRL.",
    )
    args = parser.parse_args()

    gerar(args.saida, args.limite_brl, args.quantidade)
