"""
app.py
------
Camada de interface (versão visual) descrita no capítulo de
Implementação do TCC. Não contém NENHUMA lógica de cálculo própria —
tudo isso já existe em metrics.py; este arquivo só organiza a tela.

Rodar:
    streamlit run app.py

Duas abas:
  1) "Texto único": cola/envia um texto e vê perplexidade, burstiness
     e o gráfico de perplexidade por sentença.
  2) "Corpus (lote)": envia vários .txt de uma vez (nomeados com o
     prefixo de origem, ex. humano_001.txt, chatgpt_001.txt) e vê uma
     tabela comparativa + box-plot por grupo, além de poder baixar o
     CSV consolidado — a mesma saída que o batch_analyze.py gera.
"""

import io

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from metrics import TucanoMetrics

st.set_page_config(page_title="Tucano — Perplexidade & Burstiness", layout="centered")


@st.cache_resource(show_spinner="Carregando o Tucano (só na primeira vez)...")
def load_model():
    return TucanoMetrics()


def infer_label(filename: str) -> str:
    return filename.split("_")[0].lower()


st.title("Detector de Texto Gerado por IA")
st.caption(
    "Extração de perplexidade e burstiness com o Tucano (TucanoBR/Tucano-1b1) "
    "— TCC II, UFJ."
)

tab_single, tab_batch = st.tabs(["Texto único", "Corpus (lote)"])

# ------------------------------------------------------------------
# ABA 1 — Texto único
# ------------------------------------------------------------------
with tab_single:
    st.subheader("Analisar um texto")

    modo = st.radio("Entrada", ["Colar texto", "Enviar arquivo .txt"], horizontal=True)

    texto = ""
    if modo == "Colar texto":
        texto = st.text_area("Cole o texto aqui", height=220,
                              placeholder="Cole um resumo acadêmico em português...")
    else:
        arquivo = st.file_uploader("Envie um arquivo .txt", type=["txt"])
        if arquivo is not None:
            texto = arquivo.read().decode("utf-8", errors="ignore")
            st.text_area("Prévia do texto", texto, height=180, disabled=True)

    if st.button("Calcular métricas", type="primary", disabled=not texto.strip()):
        tm = load_model()
        try:
            with st.spinner("Rodando o Tucano sobre o texto..."):
                resultado = tm.analyze_text(texto)
        except ValueError as e:
            st.error(f"Não foi possível processar: {e}")
        else:
            col1, col2, col3 = st.columns(3)
            col1.metric("Perplexidade", f"{resultado.text_perplexity:.2f}")
            col2.metric("Burstiness", f"{resultado.burstiness:.2f}")
            col3.metric("Sentenças", resultado.n_sentences)

            st.markdown("**Perplexidade por sentença**")
            fig, ax = plt.subplots(figsize=(6, 3))
            ax.plot(range(1, len(resultado.sentence_perplexities) + 1),
                    resultado.sentence_perplexities, marker="o")
            ax.set_xlabel("Sentença")
            ax.set_ylabel("Perplexidade")
            ax.grid(alpha=0.3)
            st.pyplot(fig)

# ------------------------------------------------------------------
# ABA 2 — Corpus em lote
# ------------------------------------------------------------------
with tab_batch:
    st.subheader("Analisar vários textos de uma vez")
    st.caption(
        "Nomeie os arquivos com o prefixo da origem antes do primeiro `_` "
        "(ex.: `humano_001.txt`, `chatgpt_001.txt`, `claude_001.txt`)."
    )

    arquivos = st.file_uploader(
        "Envie os arquivos .txt do corpus", type=["txt"], accept_multiple_files=True
    )

    if arquivos and st.button("Processar corpus", type="primary"):
        tm = load_model()
        linhas = []
        barra = st.progress(0.0, text="Processando...")

        for i, arq in enumerate(arquivos, 1):
            texto = arq.read().decode("utf-8", errors="ignore")
            try:
                resultado = tm.analyze_text(texto)
            except ValueError:
                st.warning(f"Pulei '{arq.name}' (texto muito curto ou inválido).")
                continue

            linhas.append({
                "arquivo": arq.name,
                "origem": infer_label(arq.name),
                "perplexidade": round(resultado.text_perplexity, 4),
                "burstiness": round(resultado.burstiness, 4),
                "n_sentencas": resultado.n_sentences,
                "n_tokens": resultado.n_tokens,
            })
            barra.progress(i / len(arquivos), text=f"Processando... ({i}/{len(arquivos)})")

        barra.empty()

        if linhas:
            df = pd.DataFrame(linhas)
            st.success(f"{len(df)} textos processados.")
            st.dataframe(df, use_container_width=True)

            st.markdown("**Comparação por origem**")
            fig, axes = plt.subplots(1, 2, figsize=(9, 4))
            df.boxplot(column="perplexidade", by="origem", ax=axes[0])
            axes[0].set_title("Perplexidade")
            axes[0].set_xlabel("")
            df.boxplot(column="burstiness", by="origem", ax=axes[1])
            axes[1].set_title("Burstiness")
            axes[1].set_xlabel("")
            fig.suptitle("")
            plt.tight_layout()
            st.pyplot(fig)

            csv_buffer = io.StringIO()
            df.to_csv(csv_buffer, index=False)
            st.download_button(
                "Baixar CSV",
                data=csv_buffer.getvalue(),
                file_name="resultados.csv",
                mime="text/csv",
            )