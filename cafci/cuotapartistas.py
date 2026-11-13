"""Cuotapartistas: (1) serie oficial por tipo de fondo y segmento (Informes Mensuales CAFCI, via tradicional)
(2) ESTIMACION de cuentas por fondo, calibrada a esos totales.

Salidas (cafci/procesado/):
  cuotapartistas_tipo.csv     mes, tipo_fondo, segmento, monto_millones, cuentas      (dato oficial CAFCI)
  cuotapartistas_estimados_AAAA-MM.csv   una fila por fondo con cuentas estimadas      (estimacion, NO dato oficial)

Metodo de la estimacion (por tipo de fondo, mes del ultimo informe con datos):
  - Ticket promedio de cada segmento = monto / cuentas (Personas Humanas, Personas Juridicas directas, ACDIs).
  - El patrimonio de cada clase se reparte entre segmentos: el monto de Personas Humanas del tipo se asigna a las
    clases "minoristas" (minimo de inversion bajo y no exclusivas de inversores calificados) en proporcion a su
    patrimonio; el resto del patrimonio de la clase se asigna a Personas Juridicas y ACDIs en la proporcion del tipo.
  - Cuentas estimadas = monto asignado / ticket del segmento. Los totales por tipo coinciden con el informe.
  - Las cuentas via ACDI (billeteras, bancos que agrupan clientes) cuentan como 1 cuenta por ACDI, igual que CAFCI.
"""
import glob, os, re
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
INF = os.path.join(BASE, "informes"); PROC = os.path.join(BASE, "procesado")
TIPOS = [("Mercado de Dinero", "Mercado de Dinero"), ("Renta Fija", "Renta Fija"), ("Renta Mixta", "Renta Mixta"),
         ("Renta Variable", "Renta Variable"), ("PyMes", "PyMEs"), ("PyMEs", "PyMEs"), ("Retorno Total", "Retorno Total"),
         ("Infraestructura", "Infraestructura"), ("Títulos del Tesoro", "Títulos del Tesoro"), ("RG900", "Títulos del Tesoro"),
         ("ASG", "ASG"), ("Sustentable", "ASG")]
SEG = r"(Personas Humanas Argentina|Personas Jurídicas Argentina|ACDIs|PyMes|Corporativos|Institucionales|Personas Jurídicas Exterior|Personas Humanas Exterior|Total Cuotapartistas)"
ROW = re.compile(SEG + r"\s+\$\s*([\d\.]+)\s+([\d\.]+)\s*$")
num = lambda s: float(s.replace(".", ""))

def parse(path):
    L = open(path, encoding="utf-8", errors="ignore").read().split("\n")
    mes = os.path.basename(path)[:6]; out = []
    tot = [i for i, l in enumerate(L) if ROW.search(l) and "Total Cuotapartistas" in l]
    for t in tot:
        ini = t
        while ini > 0 and t - ini < 40 and not (ROW.search(L[ini - 1]) is None and "Personas Humanas Argentina" in L[ini]): ini -= 1
        bloque = L[max(0, t - 40):t + 1]
        tipo = None
        for l in reversed(L[max(0, t - 60):t]):
            m = re.search(r"Fondos (?:de |de la )?(Mercado de Dinero|Renta Fija|Renta Mixta|Renta Variable|PyMes|PyMEs|Retorno Total|Infraestructura|Títulos del Tesoro|ASG|Sustentable)", l)
            if m: tipo = dict(TIPOS)[m.group(1)]; break
        if tipo is None:
            for l in bloque:
                for k, v in TIPOS:
                    if re.match(r"^\s{20,}" + re.escape(k) + r"\s*$", l): tipo = v
        if tipo is None: continue
        for l in bloque:
            m = ROW.search(l)
            if m: out.append({"mes": f"{mes[:4]}-{mes[4:]}", "tipo_fondo": tipo, "segmento": m.group(1),
                              "monto_millones": num(m.group(2)), "cuentas": num(m.group(3))})
    df = pd.DataFrame(out)
    return df.drop_duplicates(["mes", "tipo_fondo", "segmento"], keep="last") if len(df) else df

TIPO_DE_CLASIF = [("Mercado de Dinero", "Mercado de Dinero"), ("Renta Fija", "Renta Fija"), ("Renta Mixta", "Renta Mixta"),
                  ("Renta Variable", "Renta Variable"), ("PyMes", "PyMEs"), ("Retorno Total", "Retorno Total"),
                  ("Infraestructura", "Infraestructura"), ("RG900", "Títulos del Tesoro"), ("ASG", "ASG")]

def main():
    S = pd.concat([parse(f) for f in sorted(glob.glob(os.path.join(INF, "*_Resumen_Industria.txt")))], ignore_index=True)
    S.to_csv(os.path.join(PROC, "cuotapartistas_tipo.csv"), index=False)
    mes = S.mes.max(); s = S[S.mes == mes].pivot_table(index="tipo_fondo", columns="segmento", values=["monto_millones", "cuentas"], aggfunc="sum").fillna(0)
    print("ultimo informe con cuotapartistas:", mes, "tipos:", list(s.index))
    # clases a fin de ese mes
    fin = pd.Period(mes).end_time.date()
    C = pd.read_csv(os.path.join(PROC, "clases_diario", f"{mes}.csv.gz"))
    C = C[(C.fecha <= fin.isoformat())].sort_values("fecha").drop_duplicates("codigo_cafci", keep="last")
    C = C[C.decreto_596 != "S"].copy()
    C["tipo"] = C.clasificacion_cafci.map(lambda c: next((v for k, v in TIPO_DE_CLASIF if str(c).startswith(k)), None))
    C = C[C.tipo.notna() & (C.patrimonio_ars > 0)].copy()
    mi = pd.to_numeric(C.get("minimo_inversion"), errors="coerce") if "minimo_inversion" in C else pd.Series(0, index=C.index)
    lim = (mi * C.fx).fillna(0)
    calif = C.get("calificado", pd.Series("N", index=C.index)).fillna("N").astype(str).str.upper().str.startswith("S")
    C["minorista"] = (lim <= 5_000_000) & ~calif      # minimo de inversion hasta ~$5 millones y no exclusiva de calificados
    filas = []
    for tipo, g in C.groupby("tipo"):
        if tipo not in s.index: continue
        r = s.loc[tipo]
        ph_m = r[("monto_millones", "Personas Humanas Argentina")] + r[("monto_millones", "Personas Humanas Exterior")]
        ph_c = r[("cuentas", "Personas Humanas Argentina")] + r[("cuentas", "Personas Humanas Exterior")]
        acdi_m, acdi_c = r[("monto_millones", "ACDIs")], r[("cuentas", "ACDIs")]
        pj_m = r[("monto_millones", "Personas Jurídicas Argentina")] + r[("monto_millones", "Personas Jurídicas Exterior")] - acdi_m
        pj_c = r[("cuentas", "Personas Jurídicas Argentina")] + r[("cuentas", "Personas Jurídicas Exterior")] - acdi_c
        aum = g.patrimonio_ars / 1e6; R = aum[g.minorista].sum(); T = aum.sum()
        k = min(1.0, ph_m / R) if R > 0 else 0.0                      # parte de Personas Humanas en clases minoristas
        ph = aum.where(g.minorista, 0) * k
        resto_ph = max(ph_m - ph.sum(), 0)
        if resto_ph > 0: ph = ph + aum.where(~g.minorista, 0) * resto_ph / max(T - R, 1e-9)
        resto = aum - ph
        w_acdi = acdi_m / max(acdi_m + pj_m, 1e-9)
        cuentas = ph / (ph_m / ph_c if ph_c else 1) + resto * (1 - w_acdi) / (pj_m / pj_c if pj_c else 1) + resto * w_acdi / (acdi_m / acdi_c if acdi_c else 1)
        esc = (ph_c + pj_c + acdi_c) / cuentas.sum() if cuentas.sum() else 1     # ajusta a total del informe
        filas.append(g.assign(cuentas_est=cuentas * esc, monto_ph_est=ph, aum_millones=aum))
    E = pd.concat(filas)
    F = E.groupby(["codigo_cnv"]).agg(Fondo=("fondo", "first"), Gerente=("gerente", "first"), Tipo=("tipo", "first"),
                                     AUM_millones=("aum_millones", "sum"), Monto_PH_est=("monto_ph_est", "sum"),
                                     Cuentas_estimadas=("cuentas_est", "sum")).reset_index()
    F["Ticket_promedio_est"] = F.AUM_millones * 1e6 / F.Cuentas_estimadas.where(F.Cuentas_estimadas > 0)
    F["Cuentas_estimadas"] = F.Cuentas_estimadas.round(0)
    F.sort_values("Cuentas_estimadas", ascending=False).to_csv(os.path.join(PROC, f"cuotapartistas_estimados_{mes}.csv"), index=False, float_format="%.6g")
    print(F.Cuentas_estimadas.sum(), "cuentas estimadas en", len(F), "fondos")

if __name__ == "__main__":
    main()
