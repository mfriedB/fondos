"""Actualiza TNA, TIR y Duration de tir_fondos.xlsx desde la hoja "Cuadro Resumen - PPT" de Comments - Daily.xlsx.

Uso:
  python scripts/actualizar-tir.py "ruta/a/Comments - Daily.xlsx"            # actualiza tir_fondos.xlsx
  python scripts/actualizar-tir.py "ruta/a/Comments - Daily.xlsx" --probar   # solo muestra los cambios

- Cada fondo de tir_fondos.xlsx se busca en la columna "Fondo" del cuadro (ver EQUIVALENCIAS).
- Toma TNA (col. E), TIR (col. F) y Duration (col. G). Los textos tipo "5,30% (USD)" se pasan a numero.
- Los fondos con "-" en el cuadro no se tocan.
- Imprime una tabla markdown con valor anterior -> nuevo y sale con codigo 2 si algun fondo no se encontro.
"""
import re
import sys
from pathlib import Path

import openpyxl

RAIZ = Path(__file__).resolve().parent.parent
TIR = RAIZ / "tir_fondos.xlsx"
HOJA = "Cuadro Resumen - PPT"

# fondo en tir_fondos.xlsx -> nombre en el cuadro (sin espacios sobrantes)
EQUIVALENCIAS = {
    "Balanz Money Market USD": "Balanz Money Market USD",
    "Dolar Corto Plazo": "Balanz Dólar Corto Plazo",
    "Corporativo": "Balanz Corporativo",
    "Soberano": "Balanz Soberano",
    "Latam": "Balanz Latam",
    "Latam (SIN Arg)": "Balanz Sudamericano",
    "Money Market": "Balanz Money Market",
    "Lecaps": "Balanz Lecaps",
    "Ahorro corto plazo": "Balanz Ahorro Corto Plazo",
    "Balanz Crédito Privado": "Balanz Crédito Privado CP",
    "Dolar Linked": "Balanz Dólar Linked",
    "Inflation linked": "Balanz Inflation Linked",
    "ONs": "Balanz ONs",
    "Opportunity": "Balanz Renta Fija Opportunity",
    "Balanz Long Pesos": "Balanz Long Pesos",
    "Balanz Capital Pymes": "Balanz Abierto Pymes",
    "Balanz Infraestructura FCI": "Balanz Abierto Infraestructura",
    "Renta Mixta": "Balanz Renta Mixta",
    "Balanz Renta Fija Global": "Balanz Renta Fija Global",
}


def numero(v):
    """0.0365 -> 0.0365 | '5,30% (USD)' -> 0.053 | '1,,26%' -> 0.0126 | '-' o vacio -> None"""
    if isinstance(v, (int, float)):
        return float(v)
    if v is None:
        return None
    m = re.match(r"\s*([\d.,]+)\s*%", re.sub(r",+", ",", str(v)))
    if not m:
        return None
    return round(float(m.group(1).replace(".", "").replace(",", ".")) / 100, 6)


def pct(x):
    return "-" if x is None else f"{x * 100:.2f}%".replace(".", ",")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        sys.exit("Indicar la ruta de Comments - Daily.xlsx")
    probar = "--probar" in sys.argv

    hoja = openpyxl.load_workbook(args[0], data_only=True, read_only=True)[HOJA]
    cuadro = {}
    for fila in hoja.iter_rows(min_row=1, max_row=60, values_only=True):
        nombre = fila[1] if len(fila) > 6 else None
        if isinstance(nombre, str) and nombre.strip() and nombre.strip() != "Fondo":
            cuadro[nombre.strip()] = (numero(fila[4]), numero(fila[5]), numero(fila[6]))

    wb = openpyxl.load_workbook(TIR)
    ws = wb.active
    enc = [str(c.value).strip().lower() if c.value else "" for c in ws[1]]
    ci = {k: enc.index(k) for k in ("fondo", "tna", "tir", "duration")}

    print("| Fondo | TNA | TIR | Duration |\n|---|---|---|---|")
    faltan, cambios = [], 0
    for fila in ws.iter_rows(min_row=2):
        fondo = fila[ci["fondo"]].value
        if not fondo:
            continue
        if fondo not in EQUIVALENCIAS:
            print(f"| {fondo} | sin cambio | | |")
            continue
        clave = EQUIVALENCIAS[fondo]
        if clave not in cuadro:
            faltan.append(f"{fondo} ({clave})")
            continue
        tna, tir, dur = cuadro[clave]
        if tir is None or dur is None:
            faltan.append(f"{fondo}: TIR o Duration vacia en el cuadro")
            continue
        celdas = {"tna": tna, "tir": tir, "duration": dur}
        ant = {k: fila[ci[k]].value for k in celdas}
        for k, v in celdas.items():
            if v is not None and v != ant[k]:
                fila[ci[k]].value = v
                cambios += 1
        d0 = f"{ant['duration']:.2f}" if isinstance(ant["duration"], (int, float)) else "-"
        print(f"| {fondo} | {pct(ant['tna'])} → {pct(tna)} | {pct(ant['tir'])} → {pct(tir)} | "
              f"{d0} → {dur:.2f} |".replace(".", ","))

    if faltan:
        print("\nNO ENCONTRADOS en el cuadro:", "; ".join(faltan))
    if cambios and not probar:
        wb.save(TIR)
        print(f"\ntir_fondos.xlsx actualizado ({cambios} valores).")
    elif not cambios:
        print("\nSin cambios: tir_fondos.xlsx queda igual.")
    sys.exit(2 if faltan else 0)


if __name__ == "__main__":
    main()
