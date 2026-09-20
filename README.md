# Detecção de texto gerado por IA em português — perplexidade e burstiness

Código do TCC II *"Análise da eficácia de métricas de perplexidade e burstiness
na detecção de texto gerado por IA em produções acadêmicas em português
brasileiro"* (Bacharelado em Ciência da Computação, UFJ).

O projeto tem duas metades: a **construção do corpus** (textos humanos extraídos
de anais da SBC e textos sintéticos gerados por API) e a **medição**
(perplexidade e burstiness calculadas com o modelo `TucanoBR/Tucano-1b1`).

## Arquivos

### Medição

| Arquivo | O que faz |
|---|---|
| `metrics.py` | Núcleo. Carrega o Tucano, segmenta em sentenças e calcula perplexidade e burstiness. Sem CLI e sem I/O — só a lógica. |
| `batch_analyze.py` | Linha de comando: processa uma pasta de `.txt` e gera um CSV com as métricas de cada texto. |
| `app.py` | Interface visual (Streamlit): análise de um texto único ou de um lote, com box-plot por grupo. |
| `diagnostico_burstiness.py` | Verifica se o burstiness de algum texto está sendo determinado por uma única sentença fora da curva, em vez do estilo do texto. |
| `ver_sentencas.py` | Lista a perplexidade de cada sentença de um arquivo, da maior para a menor. Usado para inspecionar os casos sinalizados pelo diagnóstico. |

### Construção do corpus

| Arquivo | O que faz |
|---|---|
| `extrair_anais.py` | Primeiro passe sobre os PDFs dos anais: recorta a seção Introdução e remove ruído de conversão (notas, legendas, URLs, citações em colchetes). |
| `limpar_citacoes.py` | Segundo passe: remove as citações autor-data remanescentes e descarta sentenças com citação narrativa. |
| `common.py` | Temas, quotas, prompt de geração e validação de extensão — compartilhado pelos três geradores. |
| `gerar_chatgpt.py`, `gerar_claude.py`, `gerar_gemini.py` | Geração da parcela sintética via API oficial de cada provedor. |
| `fontes_anais.csv` | Procedência de cada texto humano: título, autores, evento, ano e URL. |

## Instalação

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

pip install -r requirements.txt
python -m spacy download pt_core_news_sm
```

Na primeira execução o Hugging Face baixa os pesos do Tucano (~2–3 GB) e os
mantém em cache local. O dispositivo é escolhido automaticamente: CUDA, depois
Metal (`mps`, em Macs Apple Silicon) e, por último, CPU. Para a variante de 1,1B
em `float32`, 6–8 GB de VRAM bastam; faltando memória, troque
`torch_dtype=torch.float32` por `torch.float16` em `metrics.py`.

## Uso

### Medir um corpus

```bash
python batch_analyze.py --input corpus/ --output resultados.csv
```

O CSV tem uma linha por texto: `arquivo, origem, perplexidade, burstiness,
n_sentencas, n_tokens`. A origem é inferida do prefixo do nome do arquivo
(`anais_*`, `chatgpt_*`, `claude_*`, `gemini_*`).

### Verificar a qualidade da medição

```bash
python diagnostico_burstiness.py --input corpus/anais-21 --detalhe
python ver_sentencas.py corpus/anais-21/anais_banco_de_dados_002.txt
```

Um texto é sinalizado quando a maior perplexidade por sentença supera dez vezes
a mediana do próprio texto. Rodar isso **antes** do `batch_analyze.py` é o que
separa defeito de extração de variação estilística real.

### Gerar a parcela sintética

```bash
export OPENAI_API_KEY="..."      # ANTHROPIC_API_KEY / GEMINI_API_KEY
python gerar_chatgpt.py --saida corpus --quantidade 5 --limite-usd 3
```

Os três scripts têm a mesma interface. Cada execução continua a numeração de
onde a anterior parou, então é seguro gerar em lotes pequenos. Textos fora da
faixa de 300 a 450 palavras, ou cortados pelo limite de tokens, são descartados
e regerados (até três tentativas). Confira os preços por token no topo de cada
script antes de rodar em lote — o limite de gasto depende deles.

## Estrutura do corpus

```
corpus/
    anais-21/     textos humanos (introduções de artigos dos anais, 2016–2021)
    chatgpt/      \
    claude/        > parcela sintética, 50 textos por modelo
    gemini/       /
```

## Reprodutibilidade

O cálculo das métricas é determinístico dado o mesmo checkpoint e as mesmas
versões de biblioteca. A geração via API é estocástica e não reproduzível bit a
bit — por isso o corpus gerado é versionado junto com o código. Ao reportar
resultados, registre a versão do `torch`/`transformers` e o hash do commit do
modelo no Hugging Face.
