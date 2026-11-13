"""Prueba fuentes: API historica CAFCI, AIF con timeout largo y APIs de dolar MEP."""
import os, sys, json, requests
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out"); os.makedirs(OUT, exist_ok=True)
S = requests.Session(); S.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124 Safari/537.36"
log = open(os.path.join(OUT, "fuentes.txt"), "w")
def t(name, url, n=600, **kw):
    try:
        r = S.get(url, timeout=(15, 90), **kw)
        log.write(f"== {name} {r.status_code} {len(r.content)} {r.headers.get('content-type')} {url}\n{r.text[:n]!r}\n")
        return r
    except Exception as e:
        log.write(f"== {name} ERR {e!r} {url}\n")
for u in ["https://api.pub.cafci.org.ar/pb_get?fecha=2020-01-02", "https://api.pub.cafci.org.ar/pb_get/2020-01-02",
          "https://api.pub.cafci.org.ar/estadisticas/informacion/diaria/4/2020-01-02",
          "https://api.cafci.org.ar/estadisticas/informacion/diaria/4/2020-01-02",
          "https://api.pub.cafci.org.ar/estadisticas/informacion/diaria/2/2024-06-28",
          "https://api.pub.cafci.org.ar/fondo?estado=1&include=entidad;depositaria,entidad;gerente,tipoRenta,region,benchmark,horizonte,duration,tipo_fondo,clase_fondo&limit=0&order=clase_fondos.nombre",
          "https://api.pub.cafci.org.ar/pb_get?ano=2020&mes=1&dia=2"]:
    t("cafci", u, headers={"Referer": "https://www.cafci.org.ar/"})
import descargar_cnv as d
d.S.headers["User-Agent"] = S.headers["User-Agent"]
docs = d.indice(); f = sorted(docs)[0]
try:
    r = S.get(docs[f]["href"], timeout=(15, 300)); log.write(f"== AIF {f} {r.status_code} {len(r.content)}\n")
except Exception as e: log.write(f"== AIF ERR {e!r}\n")
for name, u in [("ambito_mep", "https://mercados.ambito.com//dolarrava/mep/historico-general/2026-09-25/2026-11-12"),
                ("ambito_mep2", "https://mercados.ambito.com/dolarrava/mep/historico-general/01-10-2026/12-11-2026"),
                ("argdatos_bolsa", "https://api.argentinadatos.com/v1/cotizaciones/dolares/bolsa"),
                ("dolarito_hist", "https://www.dolarito.ar/cotizacion/dolar-hoy"),
                ("dolarito_api", "https://api.dolarito.ar/api/frontend/history"),
                ("dolarapi_mep", "https://dolarapi.com/v1/dolares/bolsa"),
                ("bcra_api", "https://api.bcra.gob.ar/estadisticascambiarias/v1.0/Cotizaciones/USD?fechadesde=2026-10-01&fechahasta=2026-10-31"),
                ("byma", "https://open.bymadata.com.ar/vanoms-be-core/rest/api/bymadata/free/bnown/seriesHistoricas/iamc/bonos")]:
    t(name, u, 800)
log.close()
