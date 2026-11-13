"""Revisa si hay mas de un documento de cuotapartes por fecha en la CNV (ej. 2020-2021) y que archivos son."""
import os, sys, re, html
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import descargar_cnv as d
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out"); os.makedirs(OUT, exist_ok=True)
log = open(os.path.join(OUT, "docs_por_fecha.txt"), "w")
r = d.S.get(d.INDEX, timeout=(15, 90))
filas = []
for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", r.text, flags=re.S | re.I):
    tds = [html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", c))).strip() for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, flags=re.S | re.I)]
    href = re.search(r'href="(https://aif2\.cnv\.gov\.ar/Presentations/publicview/[^"]+)"', tr)
    if len(tds) >= 4 and href: filas.append((tds, href.group(1)))
from collections import Counter
c = Counter(f[0][2] for f in filas); log.write(f"tipos: {c}\n")
por = {}
for tds, h in filas: por.setdefault(tds[0], []).append((tds, h))
n = Counter(len(v) for v in por.values()); log.write(f"docs por fecha: {n}\n")
for fecha in ["1 jun. 2020", "30 jul. 2021", "2 ago. 2021", "11 nov. 2026"]:
    for tds, h in por.get(fecha, []):
        try:
            t = d.S.get(h, timeout=(15, 90)).text
            m = re.findall(r'"nombreArchivo":"([^"]+)"', t)
        except Exception as e: m = [repr(e)]
        log.write(f"{fecha} | {tds} | {m}\n")
log.close()
