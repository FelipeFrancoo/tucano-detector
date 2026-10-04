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
    python gerar_claude.py --saida corpus --quantidade 5 --limite-brl 2
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
    arquivos_do_tema,
    carregar_historico,
    salvar_texto,
    COTACAO_USD_BRL,
    gasto_registrado,
    registrar_gasto,
)

MODELO = "claude-opus-5-5"
# Temperatura: no Claude Opus 5.5 a API não aceita temperature/top_p/top_k
# (devolve erro 400), então o modelo roda com a amostragem padrão — o mesmo
# 1.0 usado como padrão nos outros dois provedores.
# Esforço de raciocínio baixo, equivalente ao thinking_level "low" do Gemini
# e ao reasoning_effort "low" do ChatGPT. No Opus 5.5 o raciocínio não pode
# ser desligado e o padrão é "medium", por isso o valor é fixado aqui.
ESFORCO_RACIOCINIO = "low"
# Os tokens de raciocínio contam dentro do max_tokens. 300-380 palavras em
# português ficam em ~700-900 tokens; 8192 é o mesmo teto dos outros dois.
MAX_TOKENS = 8192
PROVEDOR = "claude"

QUANTIDADE_PADRAO = 5

# Preços do claude-opus-5-5, em US$ por token. Tokens de raciocínio são
# cobrados como saída (já vêm somados em output_tokens).
PRECO_ENTRADA_USD = 4.00 / 1_000_000
PRECO_SAIDA_USD = 20.00 / 1_000_000
# Orçamento em REAIS, somado entre execuções e guardado em gastos_api.json,
# igual ao dos outros dois geradores. Ajuste o teto conforme o saldo da conta.
ORCAMENTO_TOTAL_BRL = 12.00      # teto somado de TODAS as execuções
LIMITE_BRL_POR_EXECUCAO = 2.00   # teto de uma única execução
CUSTO_INICIAL_ESTIMADO_USD = 0.05  # margem de segurança antes da 1ª chamada


def brl(usd: float) -> str:
    return f"R$ {usd * COTACAO_USD_BRL:.2f}"


def uso_da_resposta(resposta) -> tuple:
    uso = getattr(resposta, "usage", None)
    if uso is None:
        return 0, 0
    return getattr(uso, "input_tokens", 0) or 0, getattr(uso, "output_tokens", 0) or 0


def custo_da_resposta(resposta) -> float:
    entrada, saida = uso_da_resposta(resposta)
    return entrada * PRECO_ENTRADA_USD + saida * PRECO_SAIDA_USD


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


def gerar(pasta_saida: str, limite_brl: float, quantidade: int) -> None:
    anterior = gasto_registrado(PROVEDOR)
    saldo_brl = ORCAMENTO_TOTAL_BRL - anterior * COTACAO_USD_BRL
    if saldo_brl <= 0:
        print(f"Orçamento total esgotado: {brl(anterior)} de R$ {ORCAMENTO_TOTAL_BRL:.2f}. "
              f"Para continuar, aumente ORCAMENTO_TOTAL_BRL em gerar_claude.py.")
        return
    limite_usd = min(limite_brl, saldo_brl) / COTACAO_USD_BRL
    print(f"Gasto registrado até agora: {brl(anterior)} de R$ {ORCAMENTO_TOTAL_BRL:.2f} "
          f"(restam R$ {saldo_brl:.2f}). Limite desta execução: {brl(limite_usd)}.")

    client = anthropic.Anthropic()  # lê ANTHROPIC_API_KEY do ambiente
    fila_temas = montar_fila(quantidade, pasta_saida)
    if not fila_temas:
        print("Todas as quotas já foram atingidas. Nada a gerar.")
        return
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
                resposta = client.messages.create(
                    model=MODELO,
                    max_tokens=MAX_TOKENS,
                    output_config={"effort": ESFORCO_RACIOCINIO},
                    messages=[{"role": "user", "content": prompt}],
                )
            except Exception as erro:
                print(f"[{i}/{total}] Tentativa {tentativa}: erro ao gerar texto para tema '{tema}': {erro}")
                time.sleep(5)
                continue

            custo = custo_da_resposta(resposta)
            gasto += custo
            maior_chamada = max(maior_chamada, custo)
            registrar_gasto(PROVEDOR, custo)
            # Com o raciocínio ligado, o primeiro bloco da resposta é o de
            # "thinking"; o texto vem nos blocos do tipo "text".
            candidato = "".join(b.text for b in resposta.content if b.type == "text")
            _, tokens_saida = uso_da_resposta(resposta)
            detalhes = f"{len(candidato.split())} palavras, {tokens_saida} tokens (com raciocínio), {brl(custo)}"

            problema = conferir_tamanho(candidato)
            # Sem fallback para outro modelo: um texto gerado por outro modelo
            # contaminaria o grupo sintético do Claude. A recusa conta como
            # tentativa perdida, como um texto fora da faixa.
            if resposta.stop_reason == "refusal":
                print(f"[{i}/{total}] Tentativa {tentativa}: o modelo recusou a geração ({detalhes}).")
            elif resposta.stop_reason == "max_tokens":
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
        description=f"Gera textos sintéticos via Claude ({MODELO}), um arquivo .txt por texto."
    )
    parser.add_argument("--saida", type=str, default="corpus", help="Pasta raiz de saída do corpus.")
    parser.add_argument("--quantidade", type=int, default=QUANTIDADE_PADRAO,
                        help="Quantos textos gerar (cada um em um arquivo separado).")
    parser.add_argument("--limite-brl", type=float, default=LIMITE_BRL_POR_EXECUCAO,
                        help="Teto de gasto desta execução, em reais. O teto total fica em ORCAMENTO_TOTAL_BRL.")
    args = parser.parse_args()

    gerar(args.saida, args.limite_brl, args.quantidade)
