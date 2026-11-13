"""Descarga las Planillas Diarias oficiales de CAFCI archivadas por la CNV.

Fuentes oficiales:
  - Indice CNV: https://www.cnv.gov.ar/SitioWeb/FondosComunesInversion/CuotaPartes
  - Ultima planilla CAFCI: https://api.pub.cafci.org.ar/pb_get
Para cada fecha se toma la revision mas reciente publicada por la CNV.
Los archivos originales quedan en cafci/raw/cnv/ y cada descarga se registra en
cafci/procesado/manifest.csv (fecha, ID de documento CNV, link publico, sha256).
"""
import csv, hashlib, html, json, os, re, sys, time
from datetime import date, datetime, timedelta
import requests

BASE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(BASE, "raw", "cnv"); PROC = os.path.join(BASE, "procesado")
os.makedirs(RAW, exist_ok=True); os.makedirs(PROC, exist_ok=True)
CFG = json.load(open(os.path.join(BASE, "config.json")))
S = requests.Session()
S.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36",
                  "Accept-Language": "es-AR,es;q=0.9"})
INDEX = "https://www.cnv.gov.ar/SitioWeb/FondosComunesInversion/CuotaPartes"
MESES = {"ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6, "jul": 7, "ago": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dic": 12}
T0 = time.time()
def log(*a): print(f"[{time.time()-T0:6.1f}s]", *a, flush=True)

def fecha_es(t):
    m = re.match(r"(\d{1,2}) (\w+)\.? (\d{4})(?: (\d{1,2}):(\d{2}))?", t.strip())
    if not m: return None
    d, mes, y, hh, mm = m.groups()
    return datetime(int(y), MESES[mes.lower()[:4] if mes.lower()[:4] in MESES else mes.lower()[:3]], int(d), int(hh or 0), int(mm or 0))

def indice():
    r = S.get(INDEX, timeout=(15, 90)); r.raise_for_status()
    docs = {}
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", r.text, flags=re.S | re.I):
        tds = [html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", c))).strip()
               for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, flags=re.S | re.I)]
        href = re.search(r'href="(https://aif2\.cnv\.gov\.ar/Presentations/publicview/[^"]+)"', tr)
        if len(tds) < 4 or not href or "Cuotaparte" not in tds[2]: continue
        fd, fr = fecha_es(tds[0]), fecha_es(tds[1])
        m_al = re.search(r"\bal (\d{1,2} \w+\.? \d{4})", tds[2])
        fdat = fecha_es(m_al.group(1)) if m_al else None
        if not (fdat or fd): continue
        # la fecha del DATO esta en la descripcion ("... al 23 jul. 2021"); la CNV re-publica revisiones de dias
        # anteriores con otra fecha de documento: se toma la ultima recepcion de cada fecha de dato
        k = (fdat or fd).date()
        if k not in docs or (fr and fr > docs[k]["recepcion"]):
            docs[k] = {"recepcion": fr, "href": href.group(1), "id": tds[3]}
    log("indice CNV:", len(docs), "fechas, de", min(docs), "a", max(docs))
    return docs

def bajar(doc):
    r = S.get(doc["href"], timeout=(15, 60)); r.raise_for_status()
    m = re.search(r'"nombreArchivo":"([^"]+)","tamano":"[^"]*","guid":"([0-9a-fA-F-]{36})","hash":"([^"]*)"', r.text)
    if not m: raise RuntimeError("sin metadata de archivo")
    nombre, guid, h = m.groups()
    vk = S.get(f"https://aif2.cnv.gov.ar/api/ValetKeyProvider/GetPublicValetKey/{guid}?operation=DownloadBlob", timeout=(15, 45))
    vk.raise_for_status()
    d = S.post(f"https://blob.cnv.gov.ar/BlobWebService.svc/DownloadBlob/{guid}", data={"ValetKey": vk.json()["valetKeyData"]}, timeout=(15, 120))
    d.raise_for_status()
    if d.content[:2] != b"PK": raise RuntimeError("respuesta no es xlsx")
    return nombre, d.content, h

def main():
    desde = date.fromisoformat(CFG["desde"]); hasta = date.fromisoformat(CFG.get("hasta") or date.today().isoformat())
    docs = indice()
    man_p = os.path.join(PROC, "manifest.csv")
    man = {r["fecha"]: r for r in csv.DictReader(open(man_p))} if os.path.exists(man_p) else {}
    pend = [f for f in sorted(docs) if desde <= f <= hasta]
    log("fechas en rango:", len(pend))
    ok = err = seguidos = 0
    limite = time.time() + float(os.environ.get("MINUTOS_DESCARGA", "100")) * 60
    for f in sorted(pend, reverse=True):          # primero lo mas reciente; el historial se completa en varias corridas
        if time.time() > limite: log("corte por tiempo; sigue en la proxima corrida"); break
        if seguidos >= 8: log("la CNV no responde (8 errores seguidos); sigue en la proxima corrida"); break
        doc = docs[f]; key = f.isoformat()
        dest = os.path.join(RAW, f"{f:%Y%m%d}_Planilla_Diaria_A.xlsx")
        if key in man and man[key]["id_cnv"] == doc["id"] and os.path.exists(dest): continue
        try:
            nombre, data, h = bajar(doc)
            open(dest, "wb").write(data)
            man[key] = {"fecha": key, "id_cnv": doc["id"], "recepcion_cnv": doc["recepcion"].isoformat() if doc["recepcion"] else "",
                        "link_cnv": doc["href"], "archivo_original": nombre, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
            ok += 1; seguidos = 0; log("OK", key, doc["id"], nombre, len(data))
        except Exception as e:
            err += 1; seguidos += 1; log("ERROR", key, doc["id"], repr(e))
        time.sleep(0.5)
    with open(man_p, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["fecha", "id_cnv", "recepcion_cnv", "link_cnv", "archivo_original", "sha256", "bytes"])
        w.writeheader(); [w.writerow(man[k]) for k in sorted(man)]
    log("fin: descargados", ok, "errores", err)
    if err and not ok: sys.exit(1)

if __name__ == "__main__":
    main()
