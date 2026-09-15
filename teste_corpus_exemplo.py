"""
teste_corpus_exemplo.py
------------------------
Teste mais significativo que o demo.py: usa dois textos no MESMO
formato e extensão do seu corpus real (resumo acadêmico de ~350-400
palavras, seguindo contextualização -> problema -> objetivo ->
metodologia -> contribuição), um "humano" e um "IA", sobre o mesmo
tema, para você comparar perplexidade e burstiness com uma amostra
mais realista do que os textos curtos do demo.py.

ATENÇÃO: os dois textos em exemplos/ são FICTÍCIOS, escritos/simulados
especificamente para testar o pipeline — não são dados reais do seu
corpus. Sirvam apenas de teste de fumaça antes da coleta de verdade.

Rodar:
    python teste_corpus_exemplo.py
"""

from pathlib import Path
from metrics import TucanoMetrics

EXEMPLOS_DIR = Path(__file__).parent / "exemplos"


def main():
    tm = TucanoMetrics()

    for path in sorted(EXEMPLOS_DIR.glob("*.txt")):
        texto = path.read_text(encoding="utf-8")
        resultado = tm.analyze_text(texto)

        print(f"\n=== {path.name} ===")
        print(f"Perplexidade do texto : {resultado.text_perplexity:.2f}")
        print(f"Burstiness            : {resultado.burstiness:.2f}")
        print(f"Nº de sentenças        : {resultado.n_sentences}")
        print(f"Nº de tokens           : {resultado.n_tokens}")
        print("Perplexidade por sentença:")
        for i, p in enumerate(resultado.sentence_perplexities, 1):
            print(f"   sentença {i:2d}: {p:8.2f}")


if __name__ == "__main__":
    main()
