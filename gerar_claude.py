"""
gerar_claude.py
Gera textos sintéticos via API da Anthropic (Claude) para a parcela
sintética do corpus do TCC, usando os temas e o prompt de common.py.
Um arquivo .txt por texto.

Instalação:
    pip install anthropic

Configuração:
    export ANTHROPIC_API_KEY="sua-chave-aqui"

Uso:
    python gerar_claude.py --saida corpus
    python gerar_claude.py --saida corpus --quantidade 5
    python gerar_claude.py --saida corpus --limite-usd 3
"""

import argparse
import glob
import os
import random
import time

import anthropic

from common import (
    MAX_TENTATIVAS,
    TEMAS_DISTRIBUICAO,
    conferir_tamanho,
    montar_prompt,
    registrar_historico,
    salvar_texto,
)

MODELO = "claude-opus-5"
# Mesma temperatura nos três provedores (valor padrão da API). Manter
# idêntico é o que permite comparar a variabilidade dos textos entre os
# modelos sem que o parâmetro vire uma variável solta. top_p fica no
# padrão: a Anthropic desaconselha ajustar os dois ao mesmo tempo.
TEMPERATURA = 1.0
MAX_TOKENS = 2048  # 350-400 palavras em português ~ 700-900 tokens
PROVEDOR = "claude"

QUANTIDADE_PADRAO = 5

# Preços por token. CONFIRA os valores vigentes na página de preços da
# Anthropic antes de rodar em lote — o limite de gasto depende deles.
PRECO_ENTRADA_USD = 5.00 / 1_000_000
PRECO_SAIDA_USD = 25.00 / 1_000_000
LIMITE_USD_PADRAO = 4.00


def uso_da_resposta(resposta) -> tuple:
    uso = getattr(resposta, "usage", None)
    if uso is None:
        return 0, 0
    return getattr(uso, "input_tokens", 0) or 0, getattr(uso, "output_tokens", 0) or 0


def custo_da_resposta(resposta) -> float:
    entrada, saida = uso_da_resposta(resposta)
    return entrada * PRECO_ENTRADA_USD + saida * PRECO_SAIDA_USD


def montar_fila(quantidade: int) -> list:
    """Monta a fila com exatamente `quantidade` temas. Os temas são
    distribuídos em rodadas embaralhadas: só se repete um tema depois que
    todos os outros já foram usados."""
    restantes = {tema: qtd for tema, qtd in TEMAS_DISTRIBUICAO.items()}
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
    """Próximo índice livre para o tema, olhando os arquivos já salvos.
    Sem isso, uma nova execução recomeçaria no 001 e sobrescreveria os
    textos gerados antes."""
    tema_slug = tema.lower().replace(" ", "_")
    padrao = os.path.join(pasta_saida, PROVEDOR, f"{PROVEDOR}_{tema_slug}_*.txt")
    maior = 0
    for caminho in glob.glob(padrao):
        sufixo = os.path.splitext(os.path.basename(caminho))[0].rsplit("_", 1)[-1]
        if sufixo.isdigit():
            maior = max(maior, int(sufixo))
    return maior + 1


def gerar(pasta_saida: str, limite_usd: float, quantidade: int) -> None:
    client = anthropic.Anthropic()  # lê ANTHROPIC_API_KEY do ambiente
    fila_temas = montar_fila(quantidade)
    historico = {}
    contador_por_tema = {}
    total = len(fila_temas)
    gasto = 0.0

    for i, tema in enumerate(fila_temas, start=1):
        prompt = montar_prompt(tema, historico)
        texto = None
        detalhes = ""

        for tentativa in range(1, MAX_TENTATIVAS + 1):
            if gasto >= limite_usd:
                print(f"Limite de gasto atingido (US$ {gasto:.2f} de US$ {limite_usd:.2f}). Parando.")
                return

            try:
                resposta = client.messages.create(
                    model=MODELO,
                    max_tokens=MAX_TOKENS,
                    temperature=TEMPERATURA,
                    messages=[{"role": "user", "content": prompt}],
                )
            except Exception as erro:
                print(f"[{i}/{total}] Tentativa {tentativa}: erro ao gerar texto para tema '{tema}': {erro}")
                time.sleep(5)
                continue

            gasto += custo_da_resposta(resposta)
            candidato = resposta.content[0].text if resposta.content else ""
            _, tokens_saida = uso_da_resposta(resposta)
            detalhes = f"{len(candidato.split())} palavras, {tokens_saida} tokens"

            problema = conferir_tamanho(candidato)
            if resposta.stop_reason == "max_tokens":
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
        print(f"[{i}/{total}] Salvo: {caminho} ({detalhes}; gasto acumulado US$ {gasto:.3f})")

        time.sleep(1)

    print(f"Concluído. Gasto estimado: US$ {gasto:.3f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=f"Gera textos sintéticos via Claude ({MODELO}), um arquivo .txt por texto."
    )
    parser.add_argument("--saida", type=str, default="corpus", help="Pasta raiz de saída do corpus.")
    parser.add_argument("--quantidade", type=int, default=QUANTIDADE_PADRAO,
                        help="Quantos textos gerar (cada um em um arquivo separado).")
    parser.add_argument("--limite-usd", type=float, default=LIMITE_USD_PADRAO,
                        help="Para a geração quando o gasto estimado atingir este valor (US$).")
    args = parser.parse_args()

    gerar(args.saida, args.limite_usd, args.quantidade)
