"""Descarga las Planillas Diarias oficiales de CAFCI archivadas por la CNV
(https://www.cnv.gov.ar/SitioWeb/FondosComunesInversion/CuotaPartes) y la ultima
planilla publicada por CAFCI (https://api.pub.cafci.org.ar/pb_get).

Guarda los archivos originales, sin modificar, en cafci/raw/.
modo "explorar": guarda la pagina indice y respuestas intermedias en cafci/debug/.
"""
import json, os, re, sys, time, html
from datetime import datetime
import requests

BASE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(BASE, "raw"); DBG = os.path.join(BASE, "debug")
os.makedirs(RAW, exist_ok=True); os.makedirs(DBG, exist_ok=True)
CFG = json.load(open(os.path.join(BASE, "config.json")))
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36",
      "Accept-Language": "es-AR,es;q=0.9"}
S = requests.Session(); S.headers.update(UA)
INDEX = "https://www.cnv.gov.ar/SitioWeb/FondosComunesInversion/CuotaPartes"

def log(*a): print(*a, flush=True)
def save(name, data):
    p = os.path.join(DBG, name)
    with open(p, "wb" if isinstance(data, bytes) else "w") as f: f.write(data)
    log("  guardado", p, len(data))

def cafci_ultima():
    log("== CAFCI pb_get")
    try:
        r = S.get("https://api.pub.cafci.org.ar/pb_get", timeout=120,
                  headers={"Referer": "https://www.cafci.org.ar/", "Origin": "https://www.cafci.org.ar"})
        cd = r.headers.get("Content-Disposition", "")
        log("  status", r.status_code, r.headers.get("Content-Type"), cd, len(r.content))
        m = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)', cd)
        name = m.group(1) if m else f"cafci_pb_get_{datetime.utcnow():%Y%m%d}.xlsx"
        if r.ok and len(r.content) > 10000:
            os.makedirs(os.path.join(RAW, "cafci"), exist_ok=True)
            open(os.path.join(RAW, "cafci", name), "wb").write(r.content)
            log("  OK", name)
        else:
            save("cafci_pb_get_respuesta.txt", r.text[:5000])
    except Exception as e:
        log("  ERROR", repr(e))

def indice():
    log("== Indice CNV")
    r = S.get(INDEX, timeout=120); log("  status", r.status_code, len(r.text))
    if CFG["modo"] == "explorar": save("cnv_index.html", r.text)
    return r.text

def filas(txt):
    """Devuelve [(fecha_doc, fecha_recepcion, descripcion, href)] desde la tabla."""
    out = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", txt, flags=re.S | re.I):
        tds = [re.sub(r"<[^>]+>", " ", c) for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, flags=re.S | re.I)]
        tds = [html.unescape(re.sub(r"\s+", " ", c)).strip() for c in tds]
        hrefs = re.findall(r'href="([^"]+)"', tr, flags=re.I)
        if tds and "Cuotaparte" in " ".join(tds):
            out.append((tds, hrefs))
    return out

def cadena(href, tag):
    """publicview -> blob -> valet key publica -> POST DownloadBlob."""
    url = html.unescape(href)
    if url.startswith("/"): url = "https://www.cnv.gov.ar" + url
    log("  meta", url)
    r = S.get(url, timeout=120, allow_redirects=True)
    log("   status", r.status_code, r.url, r.headers.get("Content-Type"), len(r.content))
    if CFG["modo"] == "explorar": save(f"meta_{tag}.txt", r.text[:200000])
    guids = re.findall(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", r.text + " " + r.url)
    log("   guids", list(dict.fromkeys(guids))[:10])
    nombre = re.search(r"\d{8}_Planilla_Diaria_A\.xlsx", r.text)
    nombre = nombre.group(0) if nombre else None
    log("   nombre", nombre)
    for g in dict.fromkeys(guids):
        vk = S.get(f"https://aif2.cnv.gov.ar/api/ValetKeyProvider/GetPublicValetKey/{g}?operation=DownloadBlob%2F", timeout=60)
        log("   valet", g, vk.status_code, vk.text[:200].replace("\n", " "))
        if not vk.ok or len(vk.text) < 10: continue
        key = vk.text.strip().strip('"')
        try:
            j = vk.json(); key = j if isinstance(j, str) else (j.get("ValetKey") or j.get("valetKey") or j.get("key") or json.dumps(j))
        except Exception: pass
        d = S.post(f"https://blob.cnv.gov.ar/BlobWebService.svc/DownloadBlob/{g}", headers={"ValetKey": key}, timeout=180)
        log("   blob", d.status_code, d.headers.get("Content-Type"), d.headers.get("Content-Disposition"), len(d.content), d.content[:4])
        if d.ok and d.content[:2] == b"PK":
            return nombre, d.content
    return nombre, None

def main():
    cafci_ultima()
    txt = indice()
    fl = filas(txt); log("  filas con Cuotaparte:", len(fl))
    for tds, hrefs in fl[:5]: log("   ", tds, hrefs)
    if CFG["modo"] == "explorar":
        save("hrefs.txt", "\n".join(sorted(set(re.findall(r'href="([^"]+)"', txt)))))
    n = 0
    for i, (tds, hrefs) in enumerate(fl):
        if n >= CFG.get("max_archivos", 2): break
        for h in hrefs:
            nombre, data = cadena(h, f"{i}")
            if data:
                nombre = nombre or f"cnv_{i}.xlsx"
                rid = re.sub(r"[^0-9A-Za-z-]", "", tds[-1]) if tds else str(i)
                p = os.path.join(RAW, "cnv", f"{nombre[:-5]}__{rid}.xlsx"); os.makedirs(os.path.dirname(p), exist_ok=True)
                open(p, "wb").write(data); log("  OK", p, len(data)); n += 1
                break
        time.sleep(1)
    log("== fin, descargados", n)

if __name__ == "__main__":
    main()
