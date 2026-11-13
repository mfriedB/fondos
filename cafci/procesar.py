"""Procesa las Planillas Diarias oficiales (cafci/raw/cnv/*.xlsx) al formato de la base de 1816.

Salidas (cafci/procesado/):
  clases_diario/AAAA-MM.csv.gz        una fila por clase y fecha de planilla
  fondos_cafci_AAAA-MM-DD.csv         una fila por fondo y mes, mismas columnas que fondos_para_looker_*.csv
  index.json                          lista de archivos disponibles (para consumir como API)

Metodologia (montos en millones de ARS, como 1816):
  - Suscripciones netas del dia = (cuotapartes hoy - cuotapartes dia anterior) x valor de cuotaparte de hoy.
  - Fondos en otra moneda: se pasan a pesos con el tipo de cambio implicito de la planilla
    (columna "Reexp.Pesos" / valor de cuotaparte), mediana por moneda y fecha.
  - AUM_Inicial / AUM_Final: patrimonio al cierre del mes anterior y del mes (o ultima fecha disponible).
  - Rendimiento = AUM_Final - AUM_Inicial - Suscripciones netas.
  - AUM_promedio: promedio por dia calendario (fines de semana y feriados repiten el ultimo dato).
  - Facturacion: honorario anual de la planilla (SG y SD, % sobre patrimonio) x patrimonio diario / 365.
  - Se excluyen fondos cerrados y fondos del Decreto 596 (igual que la vista de 1816).
"""
import glob, gzip, json, os, re
from datetime import date, datetime, timedelta, timezone
import openpyxl
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(BASE, "raw", "cnv"); PROC = os.path.join(BASE, "procesado")
os.makedirs(os.path.join(PROC, "clases_diario"), exist_ok=True)

COLS = {0: "fondo_clase", 1: "moneda", 2: "region", 3: "horizonte", 4: "fecha_txt", 5: "vcp", 6: "vcp_ant", 8: "vcp_reexp_ars",
        12: "ccp", 13: "ccp_ant", 14: "patrimonio", 15: "patrimonio_ant", 17: "depositaria", 18: "codigo_cnv", 20: "codigo_cafci",
        23: "gerente", 24: "codigo_clasificacion", 30: "hon_sg", 31: "hon_sd", 36: "moneda_fondo", 37: "plazo_liq",
        38: "decreto_596", 43: "minimo_inversion", 44: "ley_27743", 45: "tipo_dinero", 46: "calificado"}

def leer(path):
    ws = openpyxl.load_workbook(path, read_only=True, data_only=True).active
    rows = list(ws.iter_rows(values_only=True))
    fecha_ant = datetime.strptime(str(rows[8][6]), "%d/%m/%y").date()
    out, clasif = [], None
    for r in rows[10:]:
        if r[0] and all(v is None for v in r[1:6]):
            clasif = str(r[0]).strip(); continue
        if not r[0] or not r[4] or r[20] is None: continue
        d = {v: r[k] for k, v in COLS.items()}
        d["clasificacion_cafci"] = clasif
        out.append(d)
    df = pd.DataFrame(out)
    df["fecha"] = pd.to_datetime(df.fecha_txt, format="%d/%m/%y").dt.date
    df["fecha_ant"] = fecha_ant
    fp = df.fecha.mode()[0]
    # algunos fondos (p.ej. Fima Premium) informan con 1-3 dias de rezago: se toma su ultimo dato
    # disponible (hasta 7 dias) como valor de esa planilla; fechas mas viejas = fondos suspendidos
    df = df[(df.fecha <= fp) & (df.fecha >= fp - timedelta(days=7))].copy()
    df["fecha_dato"] = df.fecha
    df["fecha"] = fp
    return fp, df

def categoria_1816(r):
    c = r.clasificacion_cafci or ""
    if c.startswith("Mercado de Dinero"): return "Money Market"
    if c.startswith("Renta Variable"): return "Renta Variable"
    if c.startswith("Renta Mixta") or c.startswith("Retorno Total"): return "Renta Mixta"
    if c.startswith(("PyMes", "Infraestructura", "ASG", "RG900")): return "Destino Esp."
    if c.startswith("Renta Fija"):
        if r.moneda_fondo == "ARS" and str(r.horizonte).startswith("Cor") and (pd.to_numeric(r.plazo_liq, errors="coerce") or 9) <= 1:
            return "T+1"
        return "Renta Fija"
    return None   # Fondos Cerrados u otros

def nombre_fondo(s):
    return re.sub(r"\s*-\s*Clase\s+[A-Z0-9]+.*$", "", str(s)).strip()

def main():
    files = sorted(glob.glob(os.path.join(RAW, "*_Planilla_Diaria_A.xlsx")))
    dfs = []
    for f in files:
        fp, df = leer(f); dfs.append(df); print("leido", os.path.basename(f), fp, len(df))
    D = pd.concat(dfs, ignore_index=True)
    # Panel por FECHA DEL DATO (como 1816): si un fondo informa con rezago, su dato del dia t aparece en la
    # planilla de t+1; se toma esa version (la de la planilla mas nueva que lo contenga).
    D = D.rename(columns={"fecha": "planilla"}).sort_values("planilla")
    D = D.drop_duplicates(["codigo_cafci", "fecha_dato"], keep="last")
    D["fecha"] = D.fecha_dato
    for c in ["vcp", "vcp_ant", "vcp_reexp_ars", "ccp", "ccp_ant", "patrimonio", "patrimonio_ant", "hon_sg", "hon_sd"]:
        D[c] = pd.to_numeric(D[c], errors="coerce").fillna(0.0)
    D["categoria_1816"] = D.apply(categoria_1816, axis=1)
    D["fondo"] = D.fondo_clase.map(nombre_fondo)
    # tipo de cambio implicito por moneda y fecha
    # el patrimonio y el VCP estan expresados en la moneda de la CLASE (col. Moneda), no la del fondo
    fxr = D[(D.moneda != "ARS") & (D.vcp > 0) & (D.vcp_reexp_ars > 0)].assign(r=lambda x: x.vcp_reexp_ars / x.vcp)
    fx = fxr.groupby(["fecha", "moneda"]).r.median().rename("fx").reset_index()
    D = D.merge(fx, on=["fecha", "moneda"], how="left")
    D.loc[D.moneda == "ARS", "fx"] = 1.0
    D["fx"] = D.groupby("moneda").fx.transform(lambda s: s.ffill().bfill())
    D["patrimonio_ars"] = D.patrimonio * D.fx
    # flujo = variacion de cuotapartes entre planillas consecutivas (un dato rezagado repetido no suma dos veces)
    D = D.sort_values(["codigo_cafci", "fecha"])
    prev = D.groupby("codigo_cafci").ccp.shift()
    ccp_prev = prev.where(prev.notna(), D.ccp_ant)
    D["flujo_ars"] = (D.ccp - ccp_prev) * D.vcp / 1000 * D.fx
    D["mes"] = pd.to_datetime(D.fecha).dt.to_period("M")
    keep = ["fecha", "planilla", "fecha_ant", "codigo_cafci", "codigo_cnv", "fondo_clase", "fondo", "gerente", "clasificacion_cafci", "categoria_1816",
            "moneda", "moneda_fondo", "horizonte", "plazo_liq", "decreto_596", "ley_27743", "tipo_dinero", "vcp", "ccp", "patrimonio", "fx",
            "patrimonio_ars", "flujo_ars", "hon_sg", "hon_sd", "minimo_inversion", "calificado"]
    for m, g in D.groupby("mes"):
        g[keep].sort_values(["fecha", "codigo_cafci"]).to_csv(os.path.join(PROC, "clases_diario", f"{m}.csv.gz"), index=False, compression="gzip")

    U = D[(D.decreto_596 != "S") & D.categoria_1816.notna()].copy()
    fechas = sorted(U.fecha.unique())
    # foto diaria por dia calendario: cada clase con su ultimo dato disponible (hasta 7 dias de antiguedad)
    cal_all = pd.date_range(pd.Timestamp(fechas[0]), pd.Timestamp(fechas[-1]), freq="D")
    W = U.pivot_table(index="fecha", columns="codigo_cafci", values="patrimonio_ars", aggfunc="last")
    W.index = pd.to_datetime(W.index)
    W = W.reindex(cal_all).ffill(limit=7).fillna(0.0)
    clase = U.sort_values("fecha").drop_duplicates("codigo_cafci", keep="last").set_index("codigo_cafci")
    hon = U.sort_values("fecha").pivot_table(index="fecha", columns="codigo_cafci", values=["hon_sg", "hon_sd"], aggfunc="last")
    hon.index = pd.to_datetime(hon.index); hon = hon.reindex(cal_all).ffill().bfill().fillna(0.0)
    fondo_de = clase.codigo_cnv
    salidas = []
    for viejo in glob.glob(os.path.join(PROC, "fondos_cafci_*.csv")): os.remove(viejo)  # el mes parcial cambia de nombre cada dia
    for m in sorted(U.mes.unique()):
        ini = (m.start_time - timedelta(days=1)).date(); fin_mes = m.end_time.date()
        f_mes = [f for f in fechas if ini < f <= fin_mes]
        if not f_mes or pd.Timestamp(ini) < cal_all[0]: continue
        f1 = fin_mes if fin_mes <= fechas[-1] else f_mes[-1]
        cal = pd.date_range(pd.Timestamp(ini) + timedelta(days=1), pd.Timestamp(f1), freq="D")
        k = ["codigo_cnv"]
        num = W.loc[cal].sum().groupby(fondo_de).sum()
        a = pd.DataFrame({"numeral": num})
        a.index.name = "codigo_cnv"
        a["fac_g"] = (W.loc[cal] * hon["hon_sg"].loc[cal]).sum().groupby(fondo_de).sum() / 100 / 365
        a["fac_d"] = (W.loc[cal] * hon["hon_sd"].loc[cal]).sum().groupby(fondo_de).sum() / 100 / 365
        a["AUM_promedio"] = a.numeral / len(cal)
        a["AUM_Inicial"] = W.loc[pd.Timestamp(ini)].groupby(fondo_de).sum()
        a["AUM_Final"] = W.loc[pd.Timestamp(f1)].groupby(fondo_de).sum()
        a["Susc_Netas"] = U[(U.fecha > ini) & (U.fecha <= f1)].groupby(k).flujo_ars.sum()
        a = a.fillna(0.0)
        a["Rendimiento"] = a.AUM_Final - a.AUM_Inicial - a.Susc_Netas
        f0 = ini
        meta = U[U.fecha <= f1].sort_values(["fecha", "patrimonio_ars"]).drop_duplicates("codigo_cnv", keep="last").set_index("codigo_cnv")
        a = a.join(meta[["fondo", "gerente", "categoria_1816", "clasificacion_cafci"]])
        out = pd.DataFrame({
            "Fecha": f1.isoformat(),
            "Categoria": a.categoria_1816, "Subcategoria": a.clasificacion_cafci, "Fondo": a.fondo, "Gerente": a.gerente,
            "AUM_promedio": a.AUM_promedio / 1e6, "AUM_Inicial": a.AUM_Inicial / 1e6, "AUM_Final": a.AUM_Final / 1e6,
            "Susc_Netas": a.Susc_Netas / 1e6, "Rendimiento": a.Rendimiento / 1e6,
            "Facturacion_Gerente": a.fac_g / 1e6, "Facturacion_Depo": a.fac_d / 1e6})
        out = out[(out.AUM_promedio != 0) | (out.AUM_Inicial != 0) | (out.AUM_Final != 0)].copy()
        tot = out.AUM_promedio.sum(); mm = out.Categoria == "Money Market"; bz = out.Gerente.str.contains("Balanz", na=False)
        out["suma_aums_mensual"] = tot
        out["suma_mensual_balanz"] = bz * out[bz].AUM_promedio.sum()
        out["suma_aums_mm_mensual"] = mm * out[mm].AUM_promedio.sum()
        out["suma_aums_no_mm_mensual"] = (~mm) * out[~mm].AUM_promedio.sum()
        out = out.sort_values(["Gerente", "Fondo"]).reset_index().rename(columns={"codigo_cnv": "Codigo_CNV"})
        cols = ["Fecha", "Categoria", "Subcategoria", "Fondo", "Gerente", "AUM_promedio", "AUM_Inicial", "AUM_Final", "Susc_Netas",
                "Rendimiento", "Facturacion_Gerente", "Facturacion_Depo", "suma_aums_mensual", "suma_mensual_balanz",
                "suma_aums_mm_mensual", "suma_aums_no_mm_mensual", "Codigo_CNV"]
        nombre = f"fondos_cafci_{out.Fecha.iloc[0]}.csv"
        out[cols].to_csv(os.path.join(PROC, nombre), index=False, float_format="%.15g", lineterminator="\r\n")
        salidas.append({"archivo": nombre, "mes": str(m), "desde": ini.isoformat(), "hasta": f1.isoformat(),
                        "parcial": f1 < fin_mes and str(m) == str(U.mes.max()), "fondos": int(len(out)), "planillas": len(f_mes)})
        print(nombre, len(out), "fondos, planillas", len(f_mes), "AUM prom", round(tot / 1e6, 1) if False else round(tot, 1))
    json.dump({"actualizado": datetime.now(timezone.utc).isoformat(timespec="seconds"), "fuente": "Planilla Diaria CAFCI archivada por la CNV",
               "fechas_planilla": [f.isoformat() for f in fechas], "mensual": salidas},
              open(os.path.join(PROC, "index.json"), "w"), ensure_ascii=False, indent=1)

if __name__ == "__main__":
    main()
