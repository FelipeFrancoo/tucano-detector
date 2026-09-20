# -*- coding: utf-8 -*-
"""Extração generalizada da Introdução (lote 2) — mesmo protocolo do lote 1."""
import re, unicodedata, json, pathlib, sys

RAW = pathlib.Path("raw2")

# Ruído tipográfico do PDF. Cada alternativa precisa consumir a linha INTEIRA
# ou um prefixo inequívoco — regra frouxa aqui apaga texto legítimo.
LIXO = re.compile(
    r"^\s*(\d{1,4}\s*$"                      # linha só com número (nota ou página)
    r"|(Figura|Figure|Fig\.|Tabela|Table)\s*\d"  # legenda (exige o numero)
    r"|Agradecemos\s"                          # agradecimento
    r"|\d{1,2}(?=[A-ZÀ-Ý])"                     # nota colada: '1Constituição…'
    r"|\S*(Fapes|apoio financeiro|CNPq|CAPES)" # fomento
    r"|[^\s]{12,}[/][^\s]*\s*$"               # fragmento de URL quebrado
    r"|[^\s]*-[^\s]*-[^\s]*\s*$)", re.I)      # idem, com hífens

DESCARTE = re.compile(r"(\bFig\.|\bFigura|\bFigure|\bTabela|\bTable|\bSeção|\bSection|"
                      r"\bNesse artigo|\bNesse trabalho|\bNeste artigo os autores|\bFapes|\bFAPESP|\bCNPq|\bCAPES|apoio financeiro|\bagradec)", re.I)
DANGLING = re.compile(r"\b(como|em|por|segundo|conforme|de|da|do|e|ou)\s*[\.,;]|"
                      r"\b(como|em|por|de)\s+(e|ou)\b")

CIT  = re.compile(r"\[[^\]]{1,400}\]")
# Trecho antes da citação formado só por nomes próprios: citação autor-proeminente.
# Dois sobrenomes ligados por 'e/and/&' logo antes da citação: também é
# autor-proeminente. Exige inicial maiúscula seguida de minúsculas, para não
# confundir sobrenome com sigla (SDN, RPL).
NOMES_FIM = re.compile(r"(?:^|[,;:]\s*)[A-ZÀ-Ý][a-zà-ÿ]{2,}"
                       r"(?:\s*,\s*[A-ZÀ-Ý][a-zà-ÿ]{2,})*"
                       r"\s*(?:e|and|&)\s*[A-ZÀ-Ý][a-zà-ÿ]{2,}\s*$"
                       r"|[A-ZÀ-Ý][a-zà-ÿ]{2,}\s+et\s+al\.?\s*$")
SO_NOMES = re.compile(r"[A-ZÀ-Ý][\wÀ-ÿ'-]*(?:\s*,?\s*(?:e|and|&)?\s*[A-ZÀ-Ý][\wÀ-ÿ'-]*)*\s*")
PREP = re.compile(r"\b(em|por|de|da|do|e|ou|como|segundo|conforme|apresentad[ao]s? em|"
                  r"proposto em|realizada em|utilizad[ao]s? em|trabalho de|trabalhos de)\s*$", re.I)

# Numeração da seção: "1." (SBC), "I." (IEEE) e "1 -" (SBBD 2017 usa travessão).
CAB_INI = re.compile(r"^\s*(1\s*[\.\)\-–—]|I\s*\.)\s*I\s*ntrodu", re.I)
CAB_FIM = re.compile(r"^\s*(2\s*[\.\)\-–—]|II\s*\.)\s+\S")
ROADMAP = re.compile(r"(está|estão)\s+(organizad|estruturad|dividid)|(organizad[oa]|estruturad[oa]|dividid[oa])\\s+(como segue|da seguinte|conforme)|restante d(este|o) (artigo|trabalho)|(seções|seçoes) seguintes|apresentad[oa] na (seção|secao) \\d", re.I)


INVISIVEIS = dict.fromkeys(map(ord, "\u200b\u200c\u200d\ufeff\u2060\u00ad"), None)


def corrigir_unicode(t):
    t = t.translate(INVISIVEIS).replace("\u00a0", " ")
    t = t.replace("ı", "i").replace("ﬁ", "fi").replace("ﬂ", "fl")
    t = unicodedata.normalize("NFC", t)
    return (t.replace("’", "'").replace("“", '"').replace("”", '"')
             .replace("–", "-").replace("—", "-"))


SO_NUMERAL = re.compile(r"^\s*(\d{1,2}|[IVX]{1,4})\s*[\.\)]\s*$")


def juntar_numerais(linhas):
    """Alguns PDFs (IEEE) quebram 'I.' e 'INTRODUÇÃO' em linhas separadas."""
    saida, i = [], 0
    while i < len(linhas):
        if SO_NUMERAL.match(linhas[i]) and i + 1 < len(linhas) and linhas[i + 1].strip():
            saida.append(linhas[i].strip() + " " + linhas[i + 1].strip()); i += 2
        else:
            saida.append(linhas[i]); i += 1
    return saida


CAB_NU = re.compile(r"^\s*Introdu[çc][ãa]o\s*$", re.I)   # cabeçalho sem numeração


def eh_cabecalho_solto(linha):
    """Linha curta, começando em maiúscula e sem pontuação final — nos PDFs
    sem numeração de seção é assim que o próximo título aparece."""
    s = linha.strip()
    return (3 < len(s) < 60 and s[0].isupper()
            and not s.endswith((".", ",", ";", ":")) and " " in s or
            3 < len(s) < 30 and s[0].isupper() and not s.endswith((".", ",", ";")))


def recortar_intro(bruto):
    linhas = juntar_numerais(bruto.split("\n"))
    i = next((n for n, l in enumerate(linhas) if CAB_INI.match(l)), None)
    if i is not None:
        j = next((n for n in range(i + 1, len(linhas))
                  if CAB_FIM.match(linhas[n]) and len(linhas[n].strip()) < 80), len(linhas))
        return "\n".join(linhas[i + 1:j])

    # fallback: seções sem numeração ("Introdução" sozinho numa linha)
    i = next((n for n, l in enumerate(linhas) if CAB_NU.match(l)), None)
    if i is None:
        raise ValueError("cabeçalho de Introdução não encontrado")
    j = next((n for n in range(i + 2, len(linhas))
              if eh_cabecalho_solto(linhas[n])), len(linhas))
    return "\n".join(linhas[i + 1:j])


# Cabeçalho corrido que o pdftotext insere no meio do parágrafo, na virada de
# página. Não é linha isolada: vem grudado no texto, então é removido por string.
MES = "January|February|March|April|May|June|July|August|September|October|November|December"
BANNER = re.compile(
    rf"\s*\d{{0,4}}\s*\d{{4}}\s+SBC\s+\S+\s+Brazilian Symposium on [^)]{{0,60}}\)\s*"
    rf"(?:{MES})\s+\d{{1,2}}\s*-\s*\d{{1,2}},\s*\d{{4}}\s*-\s*[^,]{{0,30}},\s*\w{{2}},\s*Brazil\s*"
    rf"|\s*\d{{0,4}}\s*[IVXL]+\s+Simpósio Brasileiro de [^/]{{0,60}}/\s*[IVXL]+\s+Brazilian Symposium on "
    rf"[^/]{{0,60}}Artigos Técnicos\s*/\s*Research Papers\s*", re.I)

# Rodapé dos anais que o pdftotext costura no meio do texto:
# "October 2-5, 2017 - Uberlândia, MG, Brazil", "32nd SBBD - Full Papers - ISSN ...",
# "paper:171414".
RODAPE_ANAIS = re.compile(
    rf"\s*(?:{MES})\s+\d{{1,2}}\s*-\s*\d{{1,2}},\s*\d{{4}}\s*-\s*[^,]{{0,30}},\s*\w{{2}},\s*Brazil\s*"
    r"|\s*\d{1,3}(?:st|nd|rd|th)\s+\w{2,6}\s*-\s*(?:Full|Short|Demo)\s+Papers?\s*-\s*ISSN\s*[\d-]+\s*"
    r"|\s*paper\s*:\s*\d+\s*", re.I)

EMAIL = re.compile(r"\S+@\S+")
# consulta/código embutido na prosa: é texto humano, mas não é prosa
CODIGO = re.compile(r"[{}]|\bselect\b[^.]{0,40}\bwhere\b|\?\w+\s+\?\w+", re.I)
# sequência de tokens curtos = conteúdo de tabela ("sujeito s1 s1 s2 predicado p1 p2")
TABELA = re.compile(r"(?:\b\S{1,3}\b[ ,]+){6,}")
# Ponto final seguido de minúscula dentro da mesma sentença: sinal de que uma
# nota de rodapé ou uma linha fora de ordem foi costurada no meio do parágrafo
# ("...de coleções Este nome alude a um sistema híbrido... de dados. distintas.").
# Abreviações comuns ficam de fora, senão "et al." e "i.e." disparam.
# Sujeito pronominal que se referia aos autores da citação anterior: com a
# citação removida, a frase fica sem antecedente ("Eles propuseram ...").
PRONOME_AUTOR = re.compile(
    r"^(?:(?:[OA]s? (?:autor|autora|autores|autoras|pesquisadores)|"
    r"[EO]stes autores|Esses autores|Os mesmos)\b"
    r"|(?:Eles|Elas)\s+(?:propuseram|apresentaram|utilizaram|desenvolveram|realizaram|"
    r"mostraram|descreveram|estudaram|avaliaram|compararam|concluíram|obtiveram)\b)", re.I)

ABREV = {"al", "i.e", "e.g", "etc", "ex", "p", "pp", "fig", "vs", "cf",
         "dr", "sr", "sra", "profa", "prof", "ed", "no", "num"}
CORTE = re.compile(r"(\S+?)([.!?])\s+[a-zà-ÿ]")


def costurada(s):
    for m in CORTE.finditer(s):
        tok = m.group(1).lower().strip("([\"'")
        if tok in ABREV or len(tok) <= 1:
            continue
        return True
    return False


# bigramas que não existem em português — resto de linha perdida na extração
# Fórmula matemática destruída pela conversão do PDF: sobra uma palavra
# terminada em maiúscula solta ("definir p nósP que servirão de hubs").
FORMULA_QUEBRADA = re.compile(r"\b[a-zà-ÿ]{2,}[A-ZÀ-Ý]\b")

QUEBRADO = re.compile(r"\bem do\b|\bde a\b|\bpor de\b|\bcom de\b|\bem de\b", re.I)


AUTORES = re.compile(r"[A-ZÀ-Ý][\wÀ-ÿ'.-]+\s*\d\s*,|@")
# Linha de rosto dos anais, impressa no alto da primeira página.
ROSTO = re.compile(r"Proceedings of|Anais d|Sociedade Brasileira de Computa|ISSN|ISBN|^\s*c\s*\d{4}\s*$|"
                   r"Symposium|Simpósio|Workshop|Encontro Nacional", re.I)


def titulo_do_artigo(bruto):
    """Título do artigo, lido das primeiras linhas do PDF.

    Alguns eventos (STIL 2017, por exemplo) imprimem um cabeçalho corrido
    com 'número da página + título do artigo', que o pdftotext costura no
    meio do parágrafo. Para removê-lo é preciso saber qual é o título.
    A linha de rosto dos anais, quando presente, vem antes e é pulada.
    """
    linhas = []
    for l in bruto.split("\n")[:16]:
        l = l.strip()
        if not l:
            if linhas:
                break
            continue
        if ROSTO.search(l) and not linhas:
            continue
        if AUTORES.search(l):
            break
        linhas.append(l)
    return " ".join(linhas).strip()


# O cabeçalho corrido nem sempre reproduz a acentuação do título (o STIL 2017
# imprime "Lingua" onde o título traz "Língua"), então a comparação ignora acento.
_VARIANTES = {"a": "aáàâãä", "e": "eéèêë", "i": "iíìîï", "o": "oóòôõö",
              "u": "uúùûü", "c": "cç", "n": "nñ"}


def _classe(ch):
    base = unicodedata.normalize("NFD", ch)[0].lower()
    grupo = _VARIANTES.get(base)
    if grupo:
        return "[" + grupo + grupo.upper() + "]"
    return re.escape(ch)


def remover_cabecalho_corrido(texto, titulo):
    """Apaga 'ruído + número da página + título' costurado no meio do texto."""
    palavras = titulo.split()
    if len(palavras) < 4:
        return texto
    corpo = r"\s+".join("".join(_classe(c) for c in w) for w in palavras)
    return re.sub(r"\s*(?:\d{1,4}\s*){0,2}" + corpo + r"\s*", " ", texto)


def limpar(bruto):
    # linha com URL em qualquer posição é rodapé/referência, nunca corpo
    linhas = [l for l in bruto.split("\n")
              if not LIXO.match(l)
              and not re.search(r"https?://|www\.", l, re.I)
              and not EMAIL.search(l)]
    t = "\n".join(linhas)
    t = re.sub(r"(\w)-\n(\w)", r"\1\2", t)
    t = re.sub(r"\s*\n\s*", " ", t)
    t = re.sub(r"(?<=[a-zA-ZÀ-ÿ]{2})\d(?=[\s,\.])", "", t)
    t = re.sub(r"(?<=\))\d(?=[\s,\.])", "", t)
    t = re.sub(r"\b(20\d{2})\d\b", r"\1", t)
    t = BANNER.sub(" ", t)
    t = RODAPE_ANAIS.sub(" ", t)
    return re.sub(r"\s{2,}", " ", t).strip()


def pontuar(s):
    s = re.sub(r"\s+([,\.;:%])", r"\1", s)
    # ponto colado na palavra seguinte: "plataforma kaggle.Os experimentos"
    s = re.sub(r"(?<=[a-zà-ÿ]{2})\.(?=[A-ZÀ-Ý])", ". ", s)
    s = re.sub(r"(,\s*)+,", ",", s)
    s = re.sub(r",\s*\.", ".", s)
    s = re.sub(r"\(\s*[,;]?\s*\)", "", s)
    return re.sub(r"\s{2,}", " ", s).strip()


def sentencas(t):
    return [s.strip() for s in re.split(r'(?<=[\.\?\!])\s+(?=[A-ZÀ-Ý"])', t) if s.strip()]


def carregada(s):
    """A citação é argumento sintático da frase — removê-la quebra a sintaxe.

    Três casos: citação no início do trecho; logo depois de ponto final (abre
    uma frase ortográfica que o segmentador não separou, porque o que vem a
    seguir é minúsculo: "(ACO). [Silva 2010] estudaram, por sua vez, ...");
    ou precedida de preposição ("foi realizada em [Barbosa 2019]").
    """
    for m in CIT.finditer(s):
        antes = s[:m.start()].rstrip()
        if not antes:
            return True
        if antes.endswith((".", "!", "?", ":", ";")):
            return True
        if PREP.search(antes):
            return True
        if SO_NOMES.fullmatch(antes) or NOMES_FIM.search(antes):
            return True
    return False


def processar(caminho, min_pal=380, max_sent=14):
    bruto = corrigir_unicode(pathlib.Path(caminho).read_text(encoding="utf-8"))
    texto = limpar(recortar_intro(bruto))
    texto = remover_cabecalho_corrido(texto, titulo_do_artigo(bruto))
    texto = re.sub(r"\s{2,}", " ", texto).strip()

    mantidas = []
    for s in sentencas(texto):
        if ROADMAP.search(s) or carregada(s) or DESCARTE.search(s) or PRONOME_AUTOR.match(s):
            continue
        tinha_cit = bool(CIT.search(s))
        s = pontuar(CIT.sub("", s))
        if ((tinha_cit and DANGLING.search(s)) or len(s.split()) < 5
                or s.count("(") != s.count(")")
                or re.search(r"\(\s*(e|ou|[,;]|\s)*\)", s)
                or re.search(r"\b\d{1,2}\.\s*$", s)      # fragmento de lista enumerada
                or TABELA.search(s) or QUEBRADO.search(s) or FORMULA_QUEBRADA.search(s) or EMAIL.search(s)
                or CODIGO.search(s) or costurada(s)):
            continue
        mantidas.append(s)

    CONECTIVO = re.compile(r"^(Entretanto|Porém|Contudo|Todavia|No entanto|Além disso|"
                           r"Assim|Portanto|Por isso|Dessa forma|Desse modo|Nesse sentido|"
                           r"Nesse contexto|Por outro lado|Ainda assim|Já|Também)\b", re.I)
    cortes = 0
    while mantidas and cortes < 2 and CONECTIVO.match(mantidas[0]):
        mantidas.pop(0); cortes += 1

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
