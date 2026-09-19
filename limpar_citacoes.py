# -*- coding: utf-8 -*-
"""Remove citações autor-data (ABNT) que sobraram do padrão de colchetes.

Duas classes, tratadas de forma diferente — o mesmo critério já usado para
as citações em colchetes:

  A) PARENTÉTICA  "...desbalanceamento dos dados (He and Garcia 2009)."
     A citação é um aposto: sai inteira, a frase continua gramatical.

  B) NARRATIVA    "Os autores em Carpita et al. (2015) citam que..."
     O nome do autor é argumento sintático da frase. Remover quebraria a
     sintaxe, então a SENTENÇA INTEIRA é descartada — idêntico ao que foi
     feito com "foi realizada em [Barbosa et al. 2019]".
"""
import re, sys, pathlib

ANO = r"(?:1[89]|20)\d{2}[a-z]?"

# (B) sobrenome(s) seguidos de (ano) — inclui "et al.", "e", "and", "&" e listas
NARRATIVA = re.compile(
    r"\b(?:(?:de|da|do|dos|das|van|von|del)\s+)?[A-ZÀ-Ý][\wÀ-ÿ'’-]*"
    r"(?:\s*,\s*[A-ZÀ-Ý][\wÀ-ÿ'’-]*)*"
    r"(?:\s*,?\s*(?:e|and|&)\s+[A-ZÀ-Ý][\wÀ-ÿ'’-]*)?"
    r"\.?\s*(?:et\s+al\.?\s*)?"
    rf"\(\s*{ANO}\s*\)")

# (A) parêntese cujo conteúdo é uma citação
PAREN = re.compile(rf"\(\s*[^()]{{0,160}}?{ANO}\s*\)")


def eh_citacao(trecho):
    """É citação se o miolo abre com sobrenome (ou partícula + sobrenome),
    ou é só um ano. '(entre 2020-2021)' não passa em nenhuma das regras."""
    miolo = trecho[1:-1].strip()
    if re.match(r"(?:de|da|do|dos|das|van|von|del|di)\s+[A-ZÀ-Ý]", miolo):
        return True                            # "de Araujo ... 2015"
    if re.match(r"[A-ZÀ-Ý]", miolo):
        return True                            # "Zhang, 2011"
    if re.fullmatch(ANO, miolo):
        return True                            # "(2015)"
    return False


def limpar_paren(s):
    out, pos = [], 0
    for m in PAREN.finditer(s):
        if eh_citacao(m.group()):
            out.append(s[pos:m.start()]); pos = m.end()
    out.append(s[pos:])
    return "".join(out)


INVISIVEIS = dict.fromkeys(map(ord, "\u200b\u200c\u200d\ufeff\u2060\u00ad"), None)


def pontuar(s):
    s = s.translate(INVISIVEIS).replace("\u00a0", " ")
    s = re.sub(r"\s+([,\.;:%])", r"\1", s)
    s = re.sub(r"(,\s*)+,", ",", s)
    s = re.sub(r",\s*\.", ".", s)
    s = re.sub(r"\(\s*[,;]?\s*\)", "", s)
    return re.sub(r"\s{2,}", " ", s).strip()


def sentencas(t):
    return [x.strip() for x in re.split(r'(?<=[\.\?\!])\s+(?=[A-ZÀ-Ý"])', t) if x.strip()]


def processar(texto):
    mantidas, descartadas = [], []
    for s in sentencas(texto):
        if NARRATIVA.search(s):
            descartadas.append(s); continue
        s2 = pontuar(limpar_paren(s))
        if len(s2.split()) < 5:
            descartadas.append(s); continue
        mantidas.append(s2)
    return " ".join(mantidas), len(mantidas), descartadas


if __name__ == "__main__":
    alvo = pathlib.Path(sys.argv[1])
    for p in sorted(alvo.glob("anais_*.txt")):
        orig = p.read_text(encoding="utf-8").strip()
        novo, ns, desc = processar(orig)
        n0 = len(sentencas(orig))
        if novo != orig:
            p.write_text(novo + "\n", encoding="utf-8")
            marca = "  <-- ABAIXO DO PISO" if ns < 10 else ""
            print("%-52s %2d -> %2d sent | %3d -> %3d pal%s"
                  % (p.stem[6:], n0, ns, len(orig.split()), len(novo.split()), marca))
