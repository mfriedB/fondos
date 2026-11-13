"""Baja planillas de muestra de distintos anios para revisar el formato (encabezados)."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import descargar_cnv as d
import openpyxl
from datetime import date
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out"); os.makedirs(OUT, exist_ok=True)
docs = d.indice()
fechas = sorted(docs)
quiero = [date(2020, 1, 2), date(2020, 12, 30), date(2021, 12, 30), date(2022, 6, 30), date(2023, 6, 30), date(2024, 6, 28), date(2025, 6, 30)]
log = open(os.path.join(OUT, "headers.txt"), "w")
for q in quiero:
    f = min(fechas, key=lambda x: abs((x - q).days))
    try:
        nombre, data, _ = d.bajar(docs[f])
        p = os.path.join(OUT, f"{f}.xlsx"); open(p, "wb").write(data)
        ws = openpyxl.load_workbook(p, read_only=True).active
        rows = list(ws.iter_rows(min_row=1, max_row=14, values_only=True))
        log.write(f"== {f} {nombre} ncols={len(rows[8])}\n")
        for i in range(len(rows[8])):
            log.write(f"  {i} {rows[7][i]!r} | {rows[8][i]!r} | {rows[11][i]!r}\n")
    except Exception as e:
        log.write(f"== {f} ERROR {e!r}\n")
log.close()
