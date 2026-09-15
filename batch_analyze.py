"""
batch_analyze.py
-----------------
Camada de "interface" mínima (linha de comando) descrita no TCC:
recebe uma pasta com textos .txt e devolve uma tabela CSV com
perplexidade e burstiness de cada um.

Estrutura esperada da pasta de entrada:

    corpus/
        humano_001.txt
        humano_002.txt
        chatgpt_001.txt
        claude_001.txt
        gemini_001.txt
        ...

A origem de cada texto é inferida do PREFIXO do nome do arquivo
(antes do primeiro "_"). Ajuste `infer_label()` se preferir outra
convenção (ex.: subpastas por origem, ou uma planilha de mapeamento).

Uso:
    python batch_analyze.py --input corpus/ --output resultados.csv
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from metrics import TucanoMetrics


def infer_label(filename: str) -> str:
    """humano_001.txt -> 'humano' | chatgpt_003.txt -> 'chatgpt' """
    return filename.split("_")[0].lower()


def main():
    parser = argparse.ArgumentParser(description="Extrai perplexidade e burstiness de um corpus.")
    parser.add_argument("--input", required=True, help="Pasta com arquivos .txt do corpus")
    parser.add_argument("--output", default="resultados.csv", help="Caminho do CSV de saída")
    args = parser.parse_args()

    input_dir = Path(args.input)
    files = sorted(input_dir.glob("*.txt"))
    if not files:
        raise SystemExit(f"Nenhum .txt encontrado em {input_dir}")

    print(f"[batch_analyze] {len(files)} arquivos encontrados. Carregando modelo...")
    tm = TucanoMetrics()

    rows = []
    for i, path in enumerate(files, 1):
        texto = path.read_text(encoding="utf-8", errors="ignore")
        try:
            resultado = tm.analyze_text(texto)
        except ValueError as e:
            print(f"  [{i}/{len(files)}] AVISO: pulei '{path.name}' ({e})")
            continue

        rows.append({
            "arquivo": path.name,
            "origem": infer_label(path.name),
            "perplexidade": round(resultado.text_perplexity, 4),
            "burstiness": round(resultado.burstiness, 4),
            "n_sentencas": resultado.n_sentences,
            "n_tokens": resultado.n_tokens,
        })
        print(f"  [{i}/{len(files)}] {path.name}: "
              f"PPL={resultado.text_perplexity:.2f}  Burst={resultado.burstiness:.2f}")

    with open(args.output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n[batch_analyze] Concluído. Resultados salvos em: {args.output}")


if __name__ == "__main__":
    main()
