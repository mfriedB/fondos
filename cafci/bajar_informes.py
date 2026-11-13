"""Baja los Informes Mensuales de la Industria de CAFCI (PDF publico) y deja su texto en cafci/informes/."""
import os, subprocess, requests
from datetime import date
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "informes"); os.makedirs(OUT, exist_ok=True)
S = requests.Session(); S.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124 Safari/537.36"
hoy = date.today(); y, m = 2025, 12
while (y, m) <= (hoy.year, hoy.month):
    n = f"{y}{m:02d}01_Resumen_Industria"
    pdf = os.path.join(OUT, n + ".pdf"); txt = os.path.join(OUT, n + ".txt")
    if not os.path.exists(txt):
        try:
            r = S.get(f"https://www.cafci.org.ar/Publica/Estadistica/Resumenes/Mensual/{n}.pdf", timeout=(15, 120))
            if r.ok and r.content[:4] == b"%PDF":
                open(pdf, "wb").write(r.content)
                subprocess.run(["pdftotext", "-layout", pdf, txt], check=True)
                print("ok", n, len(r.content))
            else:
                print("no", n, r.status_code)
        except Exception as e:
            print("err", n, e)
    y, m = (y + 1, 1) if m == 12 else (y, m + 1)
