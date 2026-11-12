"""Explora el sitio publico de la CNV buscando informacion de cuotapartistas por fondo."""
import os, re, requests
OUT = os.path.join(os.path.dirname(__file__), "out"); os.makedirs(OUT, exist_ok=True)
S = requests.Session(); S.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124 Safari/537.36"
log = open(os.path.join(OUT, "log.txt"), "w")
def get(u, name):
    try:
        r = S.get(u, timeout=(15, 60)); open(os.path.join(OUT, name), "wb").write(r.content)
        log.write(f"{r.status_code} {len(r.content)} {u}\n"); return r.text
    except Exception as e:
        log.write(f"ERR {u} {e!r}\n"); return ""
base = "https://www.cnv.gov.ar/SitioWeb/FondosComunesInversion"
h = get(base, "fci_home.html")
links = sorted(set(re.findall(r'href="([^"]*FondosComunesInversion[^"]*)"', h, re.I)))
log.write("LINKS FCI:\n" + "\n".join(links) + "\n")
for i, l in enumerate(links[:40]):
    u = l if l.startswith("http") else "https://www.cnv.gov.ar" + l
    t = get(u, f"p{i:02d}.html")
    for m in sorted(set(re.findall(r'>([^<>]{0,80}[Cc]uotapartista[^<>]{0,80})<', t)))[:20]:
        log.write(f"   [{i}] {m.strip()}\n")
    tipos = sorted(set(re.findall(r'<td[^>]*>\s*([^<>]{3,60})\s*</td>', t)))
    log.write(f"   [{i}] celdas ejemplo: {tipos[:25]}\n")
log.close()
