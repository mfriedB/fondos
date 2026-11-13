"""Serie diaria de dolar: MEP (cierre, Ambito / dato Rava) y oficial BCRA Com. A3500 (API oficial BCRA).

Salida: cafci/procesado/dolar.csv  (fecha, mep, a3500)
Respaldo del MEP si Ambito no responde: ArgentinaDatos (casa "bolsa", venta).
"""
import os, time, requests, pandas as pd
from datetime import date, timedelta
PROC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "procesado"); os.makedirs(PROC, exist_ok=True)
OUT = os.path.join(PROC, "dolar.csv")
S = requests.Session(); S.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124 Safari/537.36"
DESDE = date(2019, 12, 1); HOY = date.today()
num = lambda s: float(str(s).replace(".", "").replace(",", "."))

def mep_ambito():
    filas, d = [], DESDE
    while d <= HOY:
        h = min(d + timedelta(days=365), HOY)
        r = S.get(f"https://mercados.ambito.com/dolarrava/mep/historico-general/{d:%d-%m-%Y}/{h:%d-%m-%Y}", timeout=(15, 60)); r.raise_for_status()
        for f, v in r.json()[1:]:
            filas.append((pd.to_datetime(f, format="%d/%m/%Y").date(), num(v)))
        d = h + timedelta(days=1); time.sleep(1)
    return pd.DataFrame(filas, columns=["fecha", "mep"]).drop_duplicates("fecha").set_index("fecha").mep

def mep_respaldo():
    r = S.get("https://api.argentinadatos.com/v1/cotizaciones/dolares/bolsa", timeout=(15, 60)); r.raise_for_status()
    df = pd.DataFrame(r.json()); df["fecha"] = pd.to_datetime(df.fecha).dt.date
    return df.set_index("fecha").venta.rename("mep")

def a3500():
    filas, d = [], DESDE
    while d <= HOY:
        h = min(d + timedelta(days=360), HOY)
        r = S.get(f"https://api.bcra.gob.ar/estadisticascambiarias/v1.0/Cotizaciones/USD?fechadesde={d}&fechahasta={h}&limit=1000", timeout=(15, 60))
        r.raise_for_status()
        for x in r.json()["results"]:
            filas.append((date.fromisoformat(x["fecha"]), x["detalle"][0]["tipoCotizacion"]))
        d = h + timedelta(days=1); time.sleep(1)
    return pd.DataFrame(filas, columns=["fecha", "a3500"]).drop_duplicates("fecha").set_index("fecha").a3500

def main():
    try: m = mep_ambito(); fuente = "ambito"
    except Exception as e:
        print("Ambito no responde:", e); m = mep_respaldo(); fuente = "argentinadatos"
    try: o = a3500()
    except Exception as e:
        print("BCRA no responde:", e); o = pd.Series(dtype=float, name="a3500")
    df = pd.concat([m, o], axis=1).sort_index(); df.index.name = "fecha"
    if os.path.exists(OUT):     # conserva historia previa si alguna fuente vino incompleta
        old = pd.read_csv(OUT, parse_dates=["fecha"]).assign(fecha=lambda x: x.fecha.dt.date).set_index("fecha")
        df = df.combine_first(old)
    df.to_csv(OUT)
    print("dolar.csv:", len(df), "dias, MEP desde", fuente, "ultimo", df.dropna(subset=["mep"]).tail(1).to_dict("records"))

if __name__ == "__main__":
    main()
