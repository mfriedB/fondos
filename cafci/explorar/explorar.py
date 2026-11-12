"""Explora el sitio publico de la CNV buscando informacion de cuotapartistas por fondo (paso 2: Empresas y Personas)."""
import os, re, requests, html, json
OUT = os.path.join(os.path.dirname(__file__), "out"); os.makedirs(OUT, exist_ok=True)
S = requests.Session(); S.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124 Safari/537.36"
log = open(os.path.join(OUT, "log2.txt"), "w")
def get(u, name=None, **kw):
    try:
        r = S.get(u, timeout=(15, 60), **kw)
        if name: open(os.path.join(OUT, name), "wb").write(r.content)
        log.write(f"{r.status_code} {len(r.content)} {r.url}\n"); return r.text
    except Exception as e:
        log.write(f"ERR {u} {e!r}\n"); return ""
def texto(h):
    t = re.sub(r"<script.*?</script>|<style.*?</style>", "", h, flags=re.S)
    return [l.strip() for l in html.unescape(re.sub(r"<[^>]+>", "\n", t)).split("\n") if l.strip()]
h = get("https://www.cnv.gov.ar/SitioWeb/Empresas", "empresas.html")
log.write("FORMS: " + repr(re.findall(r'<form[^>]*>', h)) + "\n")
log.write("INPUTS: " + repr(re.findall(r'<input[^>]*>', h)[:20]) + "\n")
log.write("LINKS: " + repr(sorted(set(re.findall(r'href="(/SitioWeb/[^"]+)"', h)))) + "\n")
for js in sorted(set(re.findall(r'src="(/SitioWeb/[^"]+\.js[^"]*)"', h))):
    t = get("https://www.cnv.gov.ar" + js)
    for m in sorted(set(re.findall(r'["\'](/SitioWeb/[A-Za-z/]+)["\']', t))): log.write(f"  JS {js}: {m}\n")
for q in ["/SitioWeb/Empresas/Buscar?nombre=BALANZ", "/SitioWeb/Empresas/BuscarEmpresas?q=BALANZ", "/SitioWeb/Empresas?q=BALANZ", "/SitioWeb/Empresas/Empresas?search=BALANZ"]:
    t = get("https://www.cnv.gov.ar" + q, re.sub(r"\W", "_", q)[-40:] + ".html")
    log.write("   " + " | ".join(l for l in texto(t) if "ALANZ" in l.upper())[:500] + "\n")
    for l in sorted(set(re.findall(r'href="([^"]*Empresa[^"]*)"', t)))[:30]: log.write(f"   link {l}\n")
log.close()
