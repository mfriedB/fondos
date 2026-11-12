"""Explora AIF (aif2.cnv.gov.ar): rutas publicas y tipos de presentaciones (paso 3)."""
import os, re, requests
OUT = os.path.join(os.path.dirname(__file__), "out"); os.makedirs(OUT, exist_ok=True)
S = requests.Session(); S.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124 Safari/537.36"
log = open(os.path.join(OUT, "log3.txt"), "w")
def get(u, name=None):
    try:
        r = S.get(u, timeout=(15, 60))
        if name: open(os.path.join(OUT, name), "wb").write(r.content)
        log.write(f"{r.status_code} {len(r.content)} {r.url}\n"); return r.text
    except Exception as e:
        log.write(f"ERR {u} {e!r}\n"); return ""
seen = set()
for u in ["https://aif2.cnv.gov.ar/", "https://aif2.cnv.gov.ar/Presentations/publicview/DD4B50E0-4B77-4615-AFBC-E86AA4A540A8"]:
    h = get(u, re.sub(r"\W", "_", u)[-30:] + ".html")
    for js in sorted(set(re.findall(r'src="([^"]+\.js[^"]*)"', h))):
        ju = js if js.startswith("http") else "https://aif2.cnv.gov.ar" + ("" if js.startswith("/") else "/") + js
        if ju in seen: continue
        seen.add(ju); t = get(ju)
        rutas = sorted(set(re.findall(r'["\'`](/?(?:api|Presentations|presentations|public|Public)[A-Za-z0-9_/\-]*)["\'`]', t)))
        log.write(f"  JS {ju}: {rutas[:80]}\n")
        for m in sorted(set(re.findall(r'.{60}[Cc]uotapartista.{60}', t)))[:15]: log.write(f"    CUOTAPARTISTA: {m}\n")
# rutas candidatas de busqueda publica
for p in ["/Presentations/publicsearch", "/Presentations/PublicSearch", "/api/Presentations/public", "/api/PublicPresentations", "/Presentations/public", "/api/DocumentTypes", "/api/Entities/public"]:
    t = get("https://aif2.cnv.gov.ar" + p, re.sub(r"\W", "_", p) + ".txt"); log.write("   " + t[:300].replace("\n", " ") + "\n")
log.close()
