"""Imprime a perplexidade de cada sentença de UM arquivo.

    python ver_sentencas.py corpus/anais-21/anais_inteligência_artificial_017.txt
"""
import sys
from pathlib import Path
from metrics import TucanoMetrics, split_sentences

caminho = Path(sys.argv[1])
texto = caminho.read_text(encoding="utf-8").strip()

tm = TucanoMetrics()
m = tm.analyze_text(texto)
sents = split_sentences(texto)

print(f"\n{caminho.name}  |  ppl {m.text_perplexity:.2f}  burst {m.burstiness:.2f}\n")
for ppl, s in sorted(zip(m.sentence_perplexities, sents), reverse=True):
    print(f"{ppl:9.2f}  {s}\n")
