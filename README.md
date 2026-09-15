# Interface de Extração de Perplexidade e Burstiness — Tucano

Módulo inicial (MVP) da interface computacional descrita no capítulo de
Implementação do TCC II. Calcula perplexidade e burstiness de textos em
português brasileiro usando o modelo **TucanoBR/Tucano-1b1** como modelo
de linguagem autorregressivo.

## Arquivos

| Arquivo             | O que faz |
|----------------------|-----------|
| `metrics.py`         | Núcleo: carrega o Tucano, segmenta sentenças, calcula perplexidade e burstiness. Sem CLI, sem I/O de arquivos — só a lógica. |
| `demo.py`            | Exemplo rápido com dois textos de teste (um "estilo humano", um "estilo IA"), pra validar que tudo está funcionando. |
| `batch_analyze.py`   | Interface de linha de comando: processa uma pasta inteira de `.txt` e gera um CSV com as métricas de cada um. |
| `requirements.txt`   | Dependências Python. |

## Instalação

Recomendo criar um ambiente virtual antes:

```bash
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

pip install -r requirements.txt
python -m spacy download pt_core_news_sm
```

**GPU:** se você tiver uma GPU NVIDIA com CUDA disponível, o `torch` vai
usá-la automaticamente (o código detecta `cuda` sozinho). Sem GPU, roda em
CPU — mais lento, mas funcional para testes com poucos textos. Para o
modelo de 1,1B de parâmetros, uma GPU com pelo menos 6–8 GB de VRAM já é
suficiente em precisão float32; se faltar memória, dá pra trocar
`torch_dtype=torch.float32` por `torch.float16` em `metrics.py`.

## Uso rápido (demo)

```bash
python demo.py
```

Na primeira execução, o Hugging Face vai baixar os pesos do modelo
(~2–3 GB) — isso só acontece uma vez, depois fica em cache local.

## Uso no corpus completo

Organize os textos em uma pasta, com o nome do arquivo indicando a
origem (o script usa o prefixo antes do primeiro `_`):

```
corpus/
    humano_001.txt
    humano_002.txt
    chatgpt_001.txt
    claude_001.txt
    gemini_001.txt
```

Depois rode:

```bash
python batch_analyze.py --input corpus/ --output resultados.csv
```

O `resultados.csv` terá uma linha por texto, com colunas:
`arquivo, origem, perplexidade, burstiness, n_sentencas, n_tokens`.
Esse CSV é o ponto de partida para a análise estatística (testes de
normalidade, Mann-Whitney/t-test, curva ROC) descrita no capítulo de
Implementação do TCC.

## Próximos passos sugeridos no código (não implementados ainda)

- **Visualização exploratória**: histogramas/box-plots comparando
  `perplexidade` e `burstiness` por grupo (`origem`), direto a partir do
  CSV gerado — pode ser um notebook separado usando `pandas` + `matplotlib`.
- **Testes estatísticos**: script separado que lê o CSV e roda
  Shapiro-Wilk, Mann-Whitney U / t-test, e a curva ROC.
- **Interface visual (opcional)**: se quiser algo mais apresentável para
  a banca, dá pra empacotar `batch_analyze.py` num app Streamlit simples
  (upload de arquivos + tabela + gráfico na tela, sem precisar de
  terminal). Fica fácil de adicionar depois, sem mudar `metrics.py`.
- **Processamento em lote mais rápido**: atualmente cada sentença é
  processada individualmente pelo modelo; para corpus grandes, dá para
  agrupar sentenças em batches (mesmo tamanho de sequência) para acelerar
  a inferência na GPU.

## Nota sobre reprodutibilidade

Documente, junto com os resultados finais, a versão exata do
`transformers`/`torch` usada e o hash do commit do modelo no Hugging Face
(aparece na página do modelo). Isso facilita a banca (ou você mesmo, no
futuro) reproduzir os números exatamente.
