"""
split_corpus.py
----------------
Você cola vários textos em UM ÚNICO arquivo .txt, separando cada texto
por uma linha marcadora (por padrão: ###FIM###). Este script lê esse
arquivo e gera um arquivo .txt individual para cada texto, já com o
nome no formato que o batch_analyze.py e o app.py esperam
(prefixo_001.txt, prefixo_002.txt, ...).

Como colar os textos (em um editor de texto simples, ex. VS Code,
criando um arquivo novo chamado por exemplo `bruto_chatgpt.txt`):

    Primeiro texto aqui, pode ter várias linhas
    e parágrafos normalmente.
    ###FIM###
    Segundo texto aqui.
    ###FIM###
    Terceiro texto aqui.
    ###FIM###

(a linha ###FIM### fica sozinha, sem mais nada nela, entre um texto e
o próximo — inclusive depois do último texto, se quiser, tanto faz)

Uso:
    python split_corpus.py bruto_chatgpt.txt --prefix chatgpt --output corpus/chatgpt_lote1/
"""

from __future__ import annotations

import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="Divide um arquivo com vários textos colados em arquivos individuais."
    )
    parser.add_argument("arquivo_bruto", help="Arquivo .txt com todos os textos colados")
    parser.add_argument("--prefix", required=True,
                         help="Prefixo de origem para os arquivos gerados (ex.: chatgpt, claude, gemini, humano)")
    parser.add_argument("--output", required=True,
                         help="Pasta onde salvar os arquivos individuais (criada se não existir)")
    parser.add_argument("--delimitador", default="###FIM###",
                         help="Linha usada para separar um texto do próximo (padrão: ###FIM###)")
    parser.add_argument("--start", type=int, default=1,
                         help="Número inicial da numeração (útil se estiver fazendo em vários lotes, "
                              "ex.: --start 251 para o segundo lote de 250)")
    args = parser.parse_args()

    conteudo = Path(args.arquivo_bruto).read_text(encoding="utf-8")

    blocos = [b.strip() for b in conteudo.split(args.delimitador)]
    blocos = [b for b in blocos if b]  # descarta blocos vazios (ex. delimitador no final do arquivo)

    saida = Path(args.output)
    saida.mkdir(parents=True, exist_ok=True)

    for i, texto in enumerate(blocos, start=args.start):
        nome = f"{args.prefix}_{i:03d}.txt"
        (saida / nome).write_text(texto, encoding="utf-8")

    print(f"{len(blocos)} textos encontrados em '{args.arquivo_bruto}'.")
    print(f"Arquivos salvos em: {saida}/")
    print(f"  primeiro: {args.prefix}_{args.start:03d}.txt")
    print(f"  último  : {args.prefix}_{args.start + len(blocos) - 1:03d}.txt")


if __name__ == "__main__":
    main()