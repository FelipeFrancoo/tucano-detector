"""
diagnostico_burstiness.py
-------------------------
Verifica se o burstiness de algum texto do corpus está sendo dominado
por UMA sentença fora da curva, em vez de refletir a variação estilística
do texto como um todo.

Motivação: no piloto, um texto deu burstiness 907,78 contra 10-49 dos
demais. O `MIN_TOKENS_SENTENCA` do metrics.py já descarta os fragmentos
de extração que causavam aquilo; este script confirma que não sobrou
nenhum caso parecido e dá os números para reportar no TCC.

Para cada texto imprime:
  ppl        perplexidade do texto (média ponderada por tokens)
  burst      desvio-padrão das perplexidades por sentença
  burst_sem  o mesmo, removendo a sentença de maior perplexidade
  razao      quanto a maior sentença se afasta da mediana
  desc       fragmentos descartados por serem curtos demais

Um texto é sinalizado quando `razao` passa de LIMITE_RAZAO OU quando
tirar a maior sentença derruba o burstiness em mais de QUEDA_ALERTA.
Nesses casos o desvio-padrão está medindo um outlier, não o estilo.

Uso:
    source venv/bin/activate
    python diagnostico_burstiness.py --input corpus/anais-21
    python diagnostico_burstiness.py --input corpus --output diagnostico.csv
"""

from __future__ import annotations

import argparse
import csv
import statistics
from pathlib import Path

from metrics import TucanoMetrics

LIMITE_RAZAO = 5.0    # maior perplexidade / mediana
QUEDA_ALERTA = 0.40   # 40% de queda no burstiness ao tirar a maior sentença


def analisar(tm: TucanoMetrics, caminho: Path) -> dict:
    texto = caminho.read_text(encoding="utf-8").strip()
    m = tm.analyze_text(texto)
    ppls = sorted(m.sentence_perplexities)

    mediana = statistics.median(ppls)
    maior = ppls[-1]
    razao = maior / mediana if mediana else float("inf")

    # burstiness recalculado sem a sentença de maior perplexidade
    burst_sem = statistics.pstdev(ppls[:-1]) if len(ppls) > 2 else 0.0
    queda = (m.burstiness - burst_sem) / m.burstiness if m.burstiness else 0.0

    return {
        "arquivo": caminho.name,
        "ppl": round(m.text_perplexity, 4),
        "burstiness": round(m.burstiness, 4),
        "burst_sem_maior": round(burst_sem, 4),
        "queda_pct": round(queda * 100, 1),
        "ppl_mediana": round(mediana, 2),
        "ppl_maior": round(maior, 2),
        "razao": round(razao, 2),
        "n_sentencas": m.n_sentences,
        "n_descartadas": m.n_descartadas,
        "alerta": "SIM" if (razao > LIMITE_RAZAO or queda > QUEDA_ALERTA) else "",
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Diagnostica burstiness dominado por outlier.")
    ap.add_argument("--input", required=True, help="Pasta com os .txt (busca recursiva).")
    ap.add_argument("--output", default="diagnostico_burstiness.csv")
    ap.add_argument("--detalhe", action="store_true",
                    help="Imprime a perplexidade de cada sentença dos textos sinalizados.")
    args = ap.parse_args()

    arquivos = sorted(Path(args.input).rglob("*.txt"))
    if not arquivos:
        raise SystemExit(f"Nenhum .txt em {args.input}")

    tm = TucanoMetrics()
    linhas = []
    print(f"\n{'arquivo':<52}{'ppl':>9}{'burst':>10}{'razao':>8}{'desc':>6}  alerta")
    print("-" * 92)

    for caminho in arquivos:
        try:
            r = analisar(tm, caminho)
        except ValueError as e:
            print(f"{caminho.name:<52}  ERRO: {e}")
            continue
        linhas.append(r)
        print(f"{r['arquivo']:<52}{r['ppl']:>9.2f}{r['burstiness']:>10.2f}"
              f"{r['razao']:>8.2f}{r['n_descartadas']:>6}  {r['alerta']}")

    if linhas:
        with open(args.output, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(linhas[0].keys()))
            w.writeheader()
            w.writerows(linhas)

    alertas = [r for r in linhas if r["alerta"]]
    bursts = [r["burstiness"] for r in linhas]
    print("-" * 92)
    print(f"{len(linhas)} textos | burstiness: mediana {statistics.median(bursts):.2f}, "
          f"min {min(bursts):.2f}, max {max(bursts):.2f}")
    print(f"sinalizados: {len(alertas)}")
    for r in alertas:
        print(f"   {r['arquivo']}: burst {r['burstiness']:.1f} -> {r['burst_sem_maior']:.1f} "
              f"sem a maior sentença (queda de {r['queda_pct']}%); "
              f"maior ppl {r['ppl_maior']} vs mediana {r['ppl_mediana']}")
    print(f"\nCSV: {args.output}")

    if args.detalhe and alertas:
        nomes = {r["arquivo"] for r in alertas}
        print("\n=== perplexidade por sentença dos textos sinalizados ===")
        for caminho in arquivos:
            if caminho.name not in nomes:
                continue
            texto = caminho.read_text(encoding="utf-8").strip()
            m = tm.analyze_text(texto)
            print(f"\n--- {caminho.name}")
            from metrics import split_sentences
            sents = [s for s in split_sentences(texto)]
            for ppl, s in zip(m.sentence_perplexities, sents):
                print(f"   {ppl:9.2f}  {s[:90]}")


if __name__ == "__main__":
    main()
