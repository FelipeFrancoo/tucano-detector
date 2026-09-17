# -*- coding: utf-8 -*-
"""Extração generalizada da Introdução (lote 2) — mesmo protocolo do lote 1."""
import re, unicodedata, json, pathlib, sys

RAW = pathlib.Path("raw2")

LIXO = re.compile(
    r"^\s*(\d{1,2}|Figura\s|Figure\s|Fig\.\s|Tabela\s|Table\s|Agradecemos\s|"
    r"https?://|\S*(Fapes|apoio financeiro|CNPq|CAPES|FAPES)|[^\s]*[/\-][^\s]*$)", re.I)

DESCARTE = re.compile(r"(\bFig\.|\bFigura|\bFigure|\bTabela|\bTable|\bSeção|\bSection|"
                      r"\bNesse artigo|\bNesse trabalho|\bNeste artigo os autores|\bFapes|\bFAPESP|\bCNPq|\bCAPES|apoio financeiro|\bagradec)", re.I)
DANGLING = re.compile(r"\b(como|em|por|segundo|conforme|de|da|do|e|ou)\s*[\.,;]|"
                      r"\b(como|em|por|de)\s+(e|ou)\b")

CIT  = re.compile(r"\[[^\]]{1,200}\]")
PREP = re.compile(r"\b(em|por|de|da|do|e|ou|como|segundo|conforme|apresentad[ao]s? em|"
                  r"proposto em|realizada em|utilizad[ao]s? em|trabalho de|trabalhos de)\s*$", re.I)

CAB_INI = re.compile(r"^\s*(1\s*[\.\)]|I\s*\.)\s*I\s*ntrodu", re.I)
CAB_FIM = re.compile(r"^\s*(2\s*[\.\)]|II\s*\.)\s+\S")
ROADMAP = re.compile(r"(está|estão)\s+(organizad|estruturad)|organizado como segue|restante d(este|o) (artigo|trabalho)", re.I)


def corrigir_unicode(t):
    t = t.replace("ı", "i").replace("ﬁ", "fi").replace("ﬂ", "fl")
    t = unicodedata.normalize("NFC", t)
    return (t.replace("’", "'").replace("“", '"').replace("”", '"')
             .replace("–", "-").replace("—", "-"))


def recortar_intro(bruto):
    linhas = bruto.split("\n")
    i = next((n for n, l in enumerate(linhas) if CAB_INI.match(l)), None)
    if i is None:
        raise ValueError("cabeçalho de Introdução não encontrado")
    j = next((n for n in range(i + 1, len(linhas))
              if CAB_FIM.match(linhas[n]) and len(linhas[n].strip()) < 80), len(linhas))
    return "\n".join(linhas[i + 1:j])


def limpar(bruto):
    t = "\n".join(l for l in bruto.split("\n") if not LIXO.match(l))
    t = re.sub(r"(\w)-\n(\w)", r"\1\2", t)
    t = re.sub(r"\s*\n\s*", " ", t)
    t = re.sub(r"(?<=[a-zA-ZÀ-ÿ]{2})\d(?=[\s,\.])", "", t)
    t = re.sub(r"\b(20\d{2})\d\b", r"\1", t)
    return re.sub(r"\s{2,}", " ", t).strip()


def pontuar(s):
    s = re.sub(r"\s+([,\.;:%])", r"\1", s)
    s = re.sub(r"(,\s*)+,", ",", s)
    s = re.sub(r",\s*\.", ".", s)
    s = re.sub(r"\(\s*[,;]?\s*\)", "", s)
    return re.sub(r"\s{2,}", " ", s).strip()


def sentencas(t):
    return [s.strip() for s in re.split(r'(?<=[\.\?\!])\s+(?=[A-ZÀ-Ý"])', t) if s.strip()]


def carregada(s):
    return any(PREP.search(s[:m.start()]) for m in CIT.finditer(s))


def processar(caminho, min_pal=380, max_sent=14):
    bruto = corrigir_unicode(pathlib.Path(caminho).read_text(encoding="utf-8"))
    texto = limpar(recortar_intro(bruto))

    mantidas = []
    for s in sentencas(texto):
        if ROADMAP.search(s) or carregada(s) or DESCARTE.search(s):
            continue
        tinha_cit = bool(CIT.search(s))
        s = pontuar(CIT.sub("", s))
        if ((tinha_cit and DANGLING.search(s)) or len(s.split()) < 5
                or s.count("(") != s.count(")")
                or re.search(r"\(\s*(e|ou|[,;]|\s)*\)", s)):
            continue
        mantidas.append(s)

    saida, n = [], 0
    for s in mantidas:
        if len(saida) >= max_sent or (n >= min_pal and len(saida) >= 10):
            break
        saida.append(s); n += len(s.split())
    return " ".join(saida), len(saida), n, len(mantidas)


if __name__ == "__main__":
    rel = {}
    for p in sorted(RAW.glob("*.txt")):
        if not p.read_text(encoding="utf-8").strip():
            rel[p.stem] = "PDF SEM CAMADA DE TEXTO"; continue
        try:
            texto, ns, nw, disp = processar(p)
        except ValueError as e:
            rel[p.stem] = str(e); continue
        rel[p.stem] = dict(sentencas=ns, palavras=nw, disponiveis=disp)
        (RAW.parent / f"out2_{p.stem}.txt").write_text(texto + "\n", encoding="utf-8")
    print(json.dumps(rel, indent=2, ensure_ascii=False))
