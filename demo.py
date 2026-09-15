"""
demo.py
-------
Exemplo mínimo para levar pronto pra reunião com o orientador:
carrega o Tucano e calcula perplexidade/burstiness em dois textos
de teste (um "estilo humano", outro "estilo IA"), só pra confirmar
que o pipeline está funcionando de ponta a ponta.

Rodar:
    python demo.py
"""

from metrics import TucanoMetrics

# Texto 1: escrito manualmente, com variação proposital de ritmo
# (frases curtas e longas alternadas) — simula estilo humano.
TEXTO_HUMANO = """
A pesquisa sobre detecção de texto gerado por IA ainda é recente no Brasil.
Poucos trabalhos avaliam isso em português. É um problema real. Professores
enfrentam esse dilema toda semana, sem ferramentas confiáveis para o nosso
idioma, e frequentemente recorrem a critérios subjetivos, como a "sensação"
de que um texto não soa como o aluno escreveria. Falta rigor.
"""

# Texto 2: gerado por um LLM (ChatGPT), com estrutura mais uniforme.
TEXTO_IA = """
A inteligência artificial tem se tornado uma ferramenta cada vez mais
presente no cotidiano acadêmico. Sua aplicação abrange diversas áreas,
incluindo a geração automática de textos. Esse avanço traz benefícios
significativos, mas também levanta questões importantes sobre autenticidade
e originalidade. É fundamental que pesquisadores desenvolvam métodos
eficazes para identificar esse tipo de conteúdo.
"""


def main():
    tm = TucanoMetrics()  # carrega o modelo uma única vez

    for nome, texto in [("HUMANO (exemplo)", TEXTO_HUMANO), ("IA (exemplo)", TEXTO_IA)]:
        resultado = tm.analyze_text(texto)
        print(f"\n=== {nome} ===")
        print(f"Perplexidade do texto : {resultado.text_perplexity:.2f}")
        print(f"Burstiness            : {resultado.burstiness:.2f}")
        print(f"Nº de sentenças        : {resultado.n_sentences}")
        print(f"Perplexidade por sentença: "
              f"{[round(p, 1) for p in resultado.sentence_perplexities]}")


if __name__ == "__main__":
    main()
