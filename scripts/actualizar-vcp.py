"""Actualiza los VCP de data.xlsx desde la base CAFCI/CNV publicada por mfriedB/cafci.

Fuente: rama `datos` de https://github.com/mfriedB/cafci (procesado/clases_diario/AAAA-MM.csv.gz),
la misma base que lee la API https://cafci.vercel.app. Cada fondo de data.xlsx se identifica por su
clase CAFCI en scripts/mapeo-vcp.csv. El VCP de CAFCI viene por 1.000 cuotapartes y se divide por 1.000.

Que hace:
  - Baja los dos ultimos meses de la base (alcanza para cubrir fondos que publican con atraso y dias
    que la CNV sube mas tarde).
  - Agrega toda combinacion fecha-fondo que todavia no este en data.xlsx. No pisa valores existentes.
  - Moneda, Categoria, Riesgo, Horizonte y Liquidacion se copian de la ultima fila del fondo.
  - Descarta saltos diarios de mas de 30% contra el VCP anterior (dato erroneo de la planilla) y avisa.
  - Si no hay nada nuevo, no toca el archivo.

Uso:
  python scripts/actualizar-vcp.py            # actualiza data.xlsx
  python scripts/actualizar-vcp.py --probar   # solo muestra lo que agregaria
"""
import copy
import csv
import gzip
import io
import json
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

import openpyxl

BASE = "https://raw.githubusercontent.com/mfriedB/cafci/datos/procesado/"
RAIZ = Path(__file__).resolve().parent.parent
DATA = RAIZ / "data.xlsx"
MAPEO = RAIZ / "scripts" / "mapeo-vcp.csv"
MESES = 2            # meses de la base que se revisan en cada corrida
SALTO_MAX = 0.30     # variacion diaria maxima aceptada


def bajar(rel):
    req = urllib.request.Request(BASE + rel, headers={"User-Agent": "fondos-actualizar-vcp"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def main():
    probar = "--probar" in sys.argv

    with open(MAPEO, encoding="utf-8") as f:
        mapeo = {int(r["codigo_cafci"]): r["fondo"] for r in csv.DictReader(f)}

    # --- Base CAFCI: ultimos meses, una fila por fecha y clase (la de la planilla mas nueva)
    indice = json.loads(bajar("index.json"))
    meses = [m["mes"] for m in indice["mensual"]][-MESES:]
    cafci = {}
    for mes in meses:
        texto = gzip.decompress(bajar(f"clases_diario/{mes}.csv.gz")).decode("utf-8")
        for r in csv.DictReader(io.StringIO(texto)):
            cod = int(r["codigo_cafci"])
            if cod not in mapeo or not r["vcp"]:
                continue
            clave = (r["fecha"], cod)
            if clave not in cafci or r["planilla"] >= cafci[clave][0]:
                cafci[clave] = (r["planilla"], float(r["vcp"]) / 1000)
    print(f"Base CAFCI: meses {', '.join(meses)}; ultima planilla {indice['fechas_planilla'][-1]}")

    # --- data.xlsx actual
    wb = openpyxl.load_workbook(DATA)
    ws = wb.active
    filas = [r for r in ws.iter_rows(min_row=2) if isinstance(r[0].value, datetime)]
    existentes = set()
    ultima = {}       # fondo -> fila mas reciente (plantilla de metadatos y formato)
    serie = {}        # fondo -> {fecha: vcp}
    for r in filas:
        f, fondo = r[0].value.strftime("%Y-%m-%d"), r[2].value
        existentes.add((f, fondo))
        serie.setdefault(fondo, {})[f] = r[1].value
        if fondo not in ultima or r[0].value >= ultima[fondo][0].value:
            ultima[fondo] = r

    sin_datos = [m for m in mapeo.values() if m not in ultima]
    if sin_datos:
        print("AVISO: fondos del mapeo que no estan en data.xlsx (se ignoran):", ", ".join(sin_datos))

    # --- Filas a agregar
    nuevas, descartadas = [], []
    for (fecha, cod), (_, vcp) in sorted(cafci.items()):
        fondo = mapeo[cod]
        if fondo not in ultima or (fecha, fondo) in existentes:
            continue
        previas = [d for d in serie.get(fondo, {}) if d < fecha]
        if previas:
            ant = serie[fondo][max(previas)]
            if ant and abs(vcp / ant - 1) > SALTO_MAX:
                descartadas.append((fecha, fondo, ant, vcp))
                continue
        nuevas.append((fecha, fondo, round(vcp, 6)))
        serie[fondo][fecha] = round(vcp, 6)

    for fecha, fondo, ant, vcp in descartadas:
        print(f"AVISO: salto de {vcp / ant - 1:+.1%} en {fondo} el {fecha} ({ant} -> {vcp:.6f}); no se carga")

    if not nuevas:
        print("Sin VCP nuevos: data.xlsx queda igual.")
        return

    resumen = {}
    for fecha, _, _ in nuevas:
        resumen[fecha] = resumen.get(fecha, 0) + 1
    print("VCP nuevos por fecha:", ", ".join(f"{f}: {n}" for f, n in sorted(resumen.items())))
    faltan = {f: sorted(set(ultima) - {fo for fe, fo in existentes | {(x[0], x[1]) for x in nuevas} if fe == f})
              for f in resumen}
    for f, lista in faltan.items():
        if lista:
            print(f"  {f} sin dato todavia: {', '.join(lista)}")

    if probar:
        print("(--probar: no se guarda nada)")
        return

    for fecha, fondo, vcp in nuevas:
        plantilla = ultima[fondo]
        valores = [datetime.strptime(fecha, "%Y-%m-%d"), vcp] + [c.value for c in plantilla[2:8]]
        fila = ws.max_row + 1
        for j, (v, origen) in enumerate(zip(valores, plantilla[:8]), start=1):
            celda = ws.cell(row=fila, column=j, value=v)
            if origen.has_style:
                celda._style = copy.copy(origen._style)
    wb.save(DATA)
    print(f"data.xlsx actualizado: {len(nuevas)} VCP nuevos, hasta el {max(resumen)}.")


if __name__ == "__main__":
    main()
