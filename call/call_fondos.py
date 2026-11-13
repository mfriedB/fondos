"""Actualiza las slides 4 a 9 de la Call de Fondos sin pasar por Power BI ni por 1816.

Datos: base oficial CAFCI/CNV publicada en GitHub (rama cafci-datos, carpeta cafci/procesado).
Mapeo local (no se publica): mapeo_fondos_1816.csv (categoria y nombre corto por Codigo CNV, tomado una sola vez
de 1816 para mantener la misma clasificacion) y mapeo_gerentes.csv (nombre corto y tipo de gerente).

Uso:  python call_fondos.py --pptx "Call de Fondos -13.11.2026.pptx" --salida "Call de Fondos -20.11.2026.pptx"
      (sin --pptx solo genera los graficos en la carpeta graficos/)
"""
import argparse, io, json, os, re, sys, urllib.request
from datetime import date
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

BASE_URL = "https://raw.githubusercontent.com/mfriedB/fondos/cafci-datos/cafci/procesado/"
AQUI = os.path.dirname(os.path.abspath(__file__))
NAVY, LIGHT, BZ, IND, VIOLET, GRISAZ, TITLE = "#2B3270", "#5B84D1", "#6B5CFF", "#232A5C", "#7400F5", "#5E7AA6", "#2E3283"
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
MESES_L = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
FONT = next((f for f in ["Segoe UI", "Carlito", "Calibri", "DejaVu Sans"] if any(f == x.name for x in font_manager.fontManager.ttflist)), "DejaVu Sans")
plt.rcParams.update({"font.family": FONT, "font.weight": "bold", "axes.spines.top": False, "axes.spines.right": False})
DPI = 100

# ---------------------------------------------------------------- datos
def leer_url(nombre):
    with urllib.request.urlopen(BASE_URL + nombre, timeout=120) as r: return r.read()

def cargar(desde="2025-12"):
    idx = json.loads(leer_url("index.json"))
    meses = [m for m in idx["mensual"] if m["mes"] >= desde]
    D = pd.concat([pd.read_csv(io.BytesIO(leer_url(m["archivo"]))) for m in meses], ignore_index=True)
    D["mes"] = D.Fecha.str[:7]
    mf = pd.read_csv(os.path.join(AQUI, "mapeo_fondos_1816.csv"))
    mg = pd.read_csv(os.path.join(AQUI, "mapeo_gerentes.csv"))
    D = D.merge(mf, on="Codigo_CNV", how="left").merge(mg, left_on="Gerente", right_on="Sociedad_Gerente", how="left", suffixes=("", "_sg"))
    D["Gerente_corto"] = D.Gerente_corto.fillna(D.Gerente.str.split().str[0])
    D["Tipo_Gerente"] = D.Tipo_Gerente.fillna("Independientes")
    D["Cat"] = D.Categoria_1816.fillna(D.Categoria)
    rf_usd_1816 = D.Subcategoria_1816.isin(["RF USD CP", "RF USD Disc", "RF USD GL Ex ARG", "RF USD GL Inc ARG", "RF USD corp loc"])
    rf_usd_cafci = D.Subcategoria_1816.isna() & (D.Cat == "Renta Fija") & D.Subcategoria.str.startswith("Renta Fija Dolar", na=False)
    D["RF_USD"] = rf_usd_1816 | rf_usd_cafci
    D["Nombre"] = D.Fondo_1816.fillna(D.Fondo).str.strip()
    D["Balanz"] = D.Gerente_corto.eq("Balanz")
    for c in ["AUM_promedio", "AUM_Final", "Susc_Netas"]: D[c] = D[c] / 1e6        # millones -> billones
    return D, idx

def fmt(v, d=2): return f"{v:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")
def etiqueta_mes(m): y, mm = m.split("-"); return f"{MESES[int(mm)-1]} {y}"

def titulo(fig, ax_box, texto, fs=26):
    x0, y0, w, h = ax_box
    fig.patches.append(plt.Rectangle((x0, y0 + h), w, 0.075 if h > .5 else 0.07, transform=fig.transFigure, color=TITLE, zorder=5))
    fig.text(x0 + w / 2, y0 + h + 0.035, texto, ha="center", va="center", color="white", fontsize=fs, weight="normal", zorder=6)
    fig.patches.append(plt.Rectangle((x0, 0.005), w, y0 + h - 0.005, transform=fig.transFigure, fill=False, ec=TITLE, lw=2.5, zorder=5))

# ---------------------------------------------------------------- slide 4
def slide4(D, out):
    u = D[D.mes == D.mes.max()]
    g = u.groupby(["Gerente_corto", "Tipo_Gerente"]).AUM_promedio.sum().reset_index().sort_values("AUM_promedio", ascending=False)
    top = g.head(30)
    fig = plt.figure(figsize=(30, 16.5), dpi=DPI)
    ax = fig.add_axes([0.075, 0.0, 0.25, 1.0])
    y = np.arange(len(top))[::-1]
    cols = [NAVY if t == "Bancarias" else LIGHT for t in top.Tipo_Gerente]
    ax.barh(y, top.AUM_promedio, color=cols, height=0.82)
    ax.set_yticks(y, top.Gerente_corto, fontsize=21); ax.set_xticks([]); ax.tick_params(length=0)
    for s in ax.spines.values(): s.set_visible(False)
    for yy, v in zip(y, top.AUM_promedio): ax.text(v + top.AUM_promedio.max() * 0.03, yy, f"{fmt(v)} bill.", va="center", fontsize=21)
    ax.set_ylim(-0.6, len(top) - 0.4); ax.set_xlim(0, top.AUM_promedio.max() * 1.35)
    tot = u.AUM_promedio.sum()
    # tarjeta total
    fig.patches.append(plt.Rectangle((0.348, 0.74), 0.307, 0.135, transform=fig.transFigure, fill=False, ec=TITLE, lw=6))
    fig.patches.append(plt.Rectangle((0.348, 0.84), 0.307, 0.035, transform=fig.transFigure, color=TITLE))
    fig.text(0.5, 0.857, "Activos Bajo Administración:", ha="center", va="center", color="white", fontsize=28, weight="normal")
    fig.text(0.5, 0.79, f"{fmt(tot)} bill.", ha="center", va="center", fontsize=58)
    # por tipo de gerente
    fig.patches.append(plt.Rectangle((0.348, 0.505), 0.307, 0.047, transform=fig.transFigure, color=TITLE))
    fig.text(0.5, 0.528, "AUM por Tipo de Gerente", ha="center", va="center", color="white", fontsize=24, weight="normal")
    ax2 = fig.add_axes([0.445, 0.31, 0.2, 0.18])
    t = u.groupby("Tipo_Gerente").AUM_promedio.sum().reindex(["Bancarias", "Independientes"]).fillna(0)
    ax2.barh([1, 0], t.values, color=[NAVY, LIGHT], height=0.82)
    ax2.set_yticks([1, 0], t.index, fontsize=21); ax2.set_xticks([]); ax2.tick_params(length=0)
    for s in ax2.spines.values(): s.set_visible(False)
    for yy, v in zip([1, 0], t.values): ax2.text(v + t.max() * 0.07, yy, f"{fmt(v, 1)} bill.", va="center", fontsize=21)
    ax2.set_xlim(0, t.max() * 1.6)
    # por categoria
    fig.patches.append(plt.Rectangle((0.698, 0.825), 0.302, 0.05, transform=fig.transFigure, color=TITLE))
    fig.text(0.849, 0.85, "AUM por Categoría de Fondo", ha="center", va="center", color="white", fontsize=24, weight="normal")
    fig.text(0.705, 0.795, "●", color=NAVY, fontsize=18, va="center"); fig.text(0.713, 0.795, "Bancarias", fontsize=18, va="center", color="#555555", weight="normal")
    fig.text(0.762, 0.795, "●", color=LIGHT, fontsize=18, va="center"); fig.text(0.770, 0.795, "Independientes", fontsize=18, va="center", color="#555555", weight="normal")
    ax3 = fig.add_axes([0.79, 0.26, 0.2, 0.5])
    c = u.pivot_table(index="Cat", columns="Tipo_Gerente", values="AUM_promedio", aggfunc="sum").fillna(0)
    c = c.reindex(c.sum(axis=1).sort_values().index)
    yy = np.arange(len(c))
    b = c.get("Bancarias", pd.Series(0, index=c.index)); i = c.get("Independientes", pd.Series(0, index=c.index))
    ax3.barh(yy, b, color=NAVY, height=0.82); ax3.barh(yy, i, left=b, color=LIGHT, height=0.82)
    ax3.set_yticks(yy, c.index, fontsize=21); ax3.set_xticks([]); ax3.tick_params(length=0)
    for s in ax3.spines.values(): s.set_visible(False)
    for y_, v in zip(yy, c.sum(axis=1)): ax3.text(v + c.sum(axis=1).max() * 0.07, y_, f"{fmt(v, 1)} bill.", va="center", fontsize=21)
    ax3.set_xlim(0, c.sum(axis=1).max() * 1.45)
    fig.savefig(out, dpi=DPI); plt.close(fig)
    pos = list(top.Gerente_corto).index("Balanz") + 1 if "Balanz" in list(top.Gerente_corto) else None
    return {"puesto_balanz": pos, "n": len(top), "total": tot}

# ---------------------------------------------------------------- slide 5
def lineas(ax, x, series, colores, nombres, dec=0, pct=True):
    for s, c, n in zip(series, colores, nombres):
        ax.plot(range(len(x)), s, color=c, lw=4.5, marker="o", ms=13, zorder=3)
        for k, v in enumerate(s):
            ax.annotate(f"{fmt(v, dec)} %", (k, v), textcoords="offset points", xytext=(0, 18), ha="center", fontsize=19)
        ax.annotate(f"— {n}", (len(x) - 1, s.iloc[-1]), textcoords="offset points", xytext=(14, -2), va="center", fontsize=23, color=c if n == "Balanz" else "#666666")
    ax.set_xticks(range(len(x)), x, rotation=35, ha="right", fontsize=17, color="#666666", weight="normal")
    ax.set_yticks([]); ax.spines["left"].set_visible(False); ax.spines["bottom"].set_visible(False); ax.tick_params(length=0)
    ax.set_xlim(-0.3, len(x) - 1 + 1.6)

def slide5(D, out):
    fig = plt.figure(figsize=(30, 10.02), dpi=DPI)
    for k, (filtro, tit) in enumerate([(None, "Crecimiento de AUMs en Industria y en Balanz"), ("RF_USD", "Crecimiento de AUMs Renta Fija USD en Industria y en Balanz")]):
        X = D if filtro is None else D[D[filtro]]
        t = X.groupby("mes").AUM_Final.sum(); b = X[X.Balanz].groupby("mes").AUM_Final.sum()
        it, ib = (t / t.iloc[0] - 1) * 100, (b / b.iloc[0] - 1) * 100
        fechas = [pd.Period(m).end_time.strftime("%d/%m/%Y") for m in t.index]
        fechas[-1] = pd.Timestamp(D[D.mes == t.index[-1]].Fecha.iloc[0]).strftime("%d/%m/%Y")
        box = [0.005 + k * 0.5, 0.0, 0.49, 0.92]
        titulo(fig, box, tit)
        ax = fig.add_axes([box[0] + 0.035, 0.13, box[2] - 0.05, 0.72])
        lineas(ax, fechas, [ib, it], [BZ, IND], ["Balanz", "Industria"])
        ax.set_ylim(min(it.min(), ib.min()) - 3, max(it.max(), ib.max()) * 1.1 + 5)
    fig.savefig(out, dpi=DPI); plt.close(fig)

# ---------------------------------------------------------------- slide 6
def slide6(D, out, n=15):
    ult = D.mes.max()
    aum = D[D.mes == ult].groupby("Gerente_corto").AUM_promedio.sum().sort_values(ascending=False).head(n)
    G = D[D.Gerente_corto.isin(aum.index)]
    fin = G.groupby(["Gerente_corto", "mes"]).AUM_Final.sum().unstack()
    crec = (fin[ult] / fin[D.mes.min()] - 1) * 100
    susc = G[G.mes >= "2026-01"].groupby("Gerente_corto").Susc_Netas.sum()
    fig = plt.figure(figsize=(24.65, 17.13), dpi=DPI)
    titulo(fig, [0.0, 0.0, 1.0, 0.915], "Crecimiento, Suscripciones y AUM por Gerente", 30)
    ax = fig.add_axes([0.11, 0.11, 0.86, 0.79])
    cmap = plt.get_cmap("tab20")
    for k, gname in enumerate(aum.index):
        c = BZ if gname == "Balanz" else cmap(k % 20)
        ax.scatter(susc[gname], crec[gname], s=aum[gname] / aum.max() * 30000, color="#3A2B8C" if gname == "Balanz" else c, alpha=0.8, edgecolors=c, lw=2, zorder=3)
        r = np.sqrt(aum[gname] / aum.max() * 30000) / 2
        ax.annotate(gname, (susc[gname], crec[gname]), textcoords="offset points", xytext=(0, -r - 22), ha="center", fontsize=22)
    ax.grid(ls=(0, (6, 6)), color="#888888", lw=1.4); ax.set_axisbelow(True)
    for s in ax.spines.values(): s.set_visible(False)
    ax.set_xlabel("Suscripciones 2026", fontsize=30, weight="normal"); ax.set_ylabel("Crecimiento 2026", fontsize=30, weight="normal")
    ax.xaxis.set_major_formatter(lambda v, p: f"{fmt(v, 1)} bill.")
    ax.yaxis.set_major_formatter(lambda v, p: f"{v:.0f} %")
    ax.tick_params(labelsize=22, colors="#666666", length=0)
    xr = susc.max() - susc.min(); yr = crec.max() - crec.min()
    ax.set_xlim(susc.min() - xr * 0.06, susc.max() + xr * 0.08); ax.set_ylim(crec.min() - yr * 0.12, crec.max() + yr * 0.12)
    fig.savefig(out, dpi=DPI); plt.close(fig)

# ---------------------------------------------------------------- slide 7
def combo(ax, x, barras, linea, fmt_bar, leyenda):
    k = np.arange(len(x))
    ax.bar(k, barras, color=IND, width=0.72, zorder=2)
    for kk, v in zip(k, barras): ax.text(kk, v + barras.max() * 0.025, fmt_bar(v), ha="center", fontsize=18)
    ax2 = ax.twinx(); ax2.plot(k, linea, color=BZ, lw=4, marker="o", ms=12, zorder=4)
    for kk, v in zip(k, linea):
        ax2.annotate(f"{fmt(v, 1)} %", (kk, v), textcoords="offset points", xytext=(0, 26), ha="center", fontsize=18,
                     bbox=dict(boxstyle="square,pad=0.25", fc="#D7DAEE", ec="none"), zorder=5)
    ax2.set_ylim(linea.min() - (linea.max() - linea.min()) * 0.05, linea.max() + (linea.max() - linea.min()) * 0.55)
    ax.set_ylim(0, barras.max() * 1.12)
    for a in (ax, ax2):
        a.set_yticks([]); [s.set_visible(False) for s in a.spines.values()]
    ax.set_xticks(k, [etiqueta_mes(m) if i % 2 == 0 else "" for i, m in enumerate(x)], fontsize=18, color="#555555", weight="normal")
    ax.tick_params(length=0)
    ax.text(0.0, 1.07, "●", color=IND, fontsize=20, transform=ax.transAxes, va="center")
    ax.text(0.02, 1.07, leyenda[0], fontsize=19, transform=ax.transAxes, va="center", color="#555555", weight="normal")
    w = 0.02 + len(leyenda[0]) * 0.0105
    ax.text(w, 1.07, "●", color=BZ, fontsize=20, transform=ax.transAxes, va="center")
    ax.text(w + 0.02, 1.07, leyenda[1], fontsize=19, transform=ax.transAxes, va="center", color="#555555", weight="normal")

def slide7(D, out):
    X = D[D.mes >= "2026-01"]
    aum = X.groupby("mes").AUM_promedio.sum(); ms = X[X.Balanz].groupby("mes").AUM_promedio.sum() / aum * 100
    fl = X.groupby("mes").Susc_Netas.sum().cumsum(); fb = X[X.Balanz].groupby("mes").Susc_Netas.sum().cumsum() / fl * 100
    fig = plt.figure(figsize=(30, 10.05), dpi=DPI)
    titulo(fig, [0.003, 0.0, 0.482, 0.925], "AUMs en Industria y Market Share de Balanz")
    titulo(fig, [0.503, 0.0, 0.482, 0.925], "Flujo en Industria y % de Balanz")
    combo(fig.add_axes([0.008, 0.07, 0.475, 0.78]), list(aum.index), aum, ms, lambda v: f"{v:.0f} bill.", ["AUM Promedio Mes", "Market Share de Balanz"])
    combo(fig.add_axes([0.508, 0.07, 0.475, 0.78]), list(fl.index), fl, fb, lambda v: f"{fmt(v, 1)} bill.", ["Flujo Total Industria 2026", "% de Flujo de Balanz sobre Industria"])
    fig.savefig(out, dpi=DPI); plt.close(fig)

# ---------------------------------------------------------------- slide 8
def slide8(D, out):
    X = D[D.mes >= "2026-01"].copy()
    X["CO"] = X.Cat.where(X.Cat.isin(["Money Market", "Renta Fija", "T+1"]), "Otros")
    fig = plt.figure(figsize=(30, 10.98), dpi=DPI)
    cols = {"Money Market": IND, "Renta Fija": VIOLET, "T+1": GRISAZ, "Otros": BZ}
    for k, (Y, tit) in enumerate([(X, "Evolutivo Composición AUM Industria"), (X[X.Balanz], "Evolutivo Composición AUM Balanz")]):
        box = [0.003 + k * 0.505, 0.0, 0.485, 0.935]
        titulo(fig, box, tit)
        p = Y.pivot_table(index="mes", columns="CO", values="AUM_promedio", aggfunc="sum")
        p = p.div(p.sum(axis=1), axis=0) * 100
        ax = fig.add_axes([box[0] + 0.02, 0.07, box[2] - 0.1, 0.8])
        for c in ["Money Market", "Renta Fija", "T+1", "Otros"]:
            s = p[c]; ax.plot(range(len(s)), s, color=cols[c], lw=4.5, marker="o", ms=12)
            for kk, v in enumerate(s): ax.annotate(f"{fmt(v, 1)} %", (kk, v), textcoords="offset points", xytext=(0, 16), ha="center", fontsize=17, color="#555555")
            ax.annotate(f"— {c}", (len(s) - 1, s.iloc[-1]), textcoords="offset points", xytext=(12, -4), va="center", fontsize=21, color=cols[c])
        ax.set_xticks(range(len(p)), [etiqueta_mes(m) if i % 2 == 0 else "" for i, m in enumerate(p.index)], fontsize=18, color="#555555", weight="normal")
        ax.set_yticks([]); [s.set_visible(False) for s in ax.spines.values()]; ax.tick_params(length=0)
        ax.set_xlim(-0.4, len(p) - 1 + 1.9); ax.set_ylim(0, p.max().max() * 1.12)
    fig.savefig(out, dpi=DPI); plt.close(fig)

# ---------------------------------------------------------------- slide 9
def slide9(D, out, n=5):
    X = D[(D.mes >= "2026-01") & (D.Cat != "Money Market")]
    s = X.groupby(["Codigo_CNV"]).agg(Nombre=("Nombre", "last"), Balanz=("Balanz", "last"), Susc=("Susc_Netas", "sum")).sort_values("Susc", ascending=False).head(n)
    fig = plt.figure(figsize=(16.47, 7.72), dpi=DPI)
    titulo(fig, [0.002, 0.0, 0.996, 0.9], "Top Fondos Ex-MM en Flujo 2026 (en pesos)", 30)
    ax = fig.add_axes([0.06, 0.28, 0.9, 0.55])
    k = np.arange(len(s))
    ax.bar(k, s.Susc * 1000, color=NAVY, width=0.77)
    for kk, v in zip(k, s.Susc * 1000): ax.text(kk, v + (s.Susc.max() * 1000) * 0.04, f"$ {v:,.0f} mil M".replace(",", "."), ha="center", fontsize=24, color="#666666")
    ax.set_ylim(0, s.Susc.max() * 1000 * 1.18); ax.set_yticks([]); ax.set_xticks([])
    [sp.set_visible(False) for sp in ax.spines.values()]
    import textwrap
    cajas = []
    fig.canvas.draw()
    for kk, (nom, bz) in enumerate(zip(s.Nombre, s.Balanz)):
        t = fig.text(ax.transData.transform((kk, 0))[0] / fig.bbox.width, 0.235, "\n".join(textwrap.wrap(nom, 16)), ha="center", va="top", fontsize=25, linespacing=1.3)
        if bz:
            fig.canvas.draw(); bb = t.get_window_extent()
            cajas.append((bb.x0 / fig.bbox.width, 1 - bb.y1 / fig.bbox.height, bb.width / fig.bbox.width, bb.height / fig.bbox.height))
    fig.savefig(out, dpi=DPI); plt.close(fig)
    return cajas

# ---------------------------------------------------------------- PowerPoint
def fecha_larga(d): return f"{d.day} de {MESES_L[d.month-1]} de {d.year}"

def actualizar_pptx(ruta, salida, imgs, corte, info4, cajas9):
    from pptx import Presentation
    from pptx.util import Emu
    prs = Presentation(ruta)
    for n, img in imgs.items():
        s = prs.slides[n - 1]
        pics = [sh for sh in s.shapes if sh.shape_type == 13]
        big = max(pics, key=lambda x: x.width * x.height)
        L, T, W, H = big.left, big.top, big.width, big.height
        from PIL import Image
        iw, ih = Image.open(img).size
        esc = min(W / iw, H / ih); w, h = int(iw * esc), int(ih * esc)
        nl, nt = L + (W - w) // 2, T + (H - h) // 2
        pic = s.shapes.add_picture(img, nl, nt, w, h)
        big._element.addprevious(pic._element)          # mismo orden z que la imagen vieja
        rid = big._element.blipFill.blip.rEmbed if hasattr(big._element, "blipFill") else None
        big._element.getparent().remove(big._element)
        for sh in s.shapes:                              # pie con la fecha (el texto puede venir partido en varios runs)
            if sh.has_text_frame:
                for p in sh.text_frame.paragraphs:
                    if not p.runs: continue
                    t = "".join(r.text for r in p.runs)
                    t2 = re.sub(r"al \d{1,2} de [A-Za-zé]+ de \d{4}", "al " + fecha_larga(corte), t).replace("fuente 1816", "fuente CAFCI / CNV")
                    if t2 != t:
                        p.runs[0].text = t2
                        for r in p.runs[1:]: r.text = ""
        if n == 4 and info4.get("puesto_balanz"):
            for sh in s.shapes:
                if sh.has_text_frame and sh.text_frame.text.strip().startswith("TOP"):
                    sh.text_frame.paragraphs[0].runs[0].text = f"TOP {info4['puesto_balanz']}"
                    for r in sh.text_frame.paragraphs[0].runs[1:]: r.text = ""
            # flecha y texto a la altura de la fila de Balanz (ranking de 30 filas en la mitad izquierda)
            fila_y = nt + h * (info4["puesto_balanz"] - 0.5) / info4["n"]
            for sh in s.shapes:
                if sh.name.startswith("Flecha") or (sh.has_text_frame and sh.text_frame.text.startswith("TOP")):
                    sh.top = int(fila_y - sh.height / 2)
        if n == 9:
            rects = [sh for sh in s.shapes if sh.name.startswith("Rect")]
            for k, sh in enumerate(rects):
                if k < len(cajas9):
                    x, y, ww, hh = cajas9[k]; m = 0.012
                    sh.left, sh.top = int(nl + (x - m) * w), int(nt + (y - m) * h)
                    sh.width, sh.height = int((ww + 2 * m) * w), int((hh + 2 * m) * h)
                else:
                    sh._element.getparent().remove(sh._element)
            for k in range(len(rects), len(cajas9)):     # mas fondos Balanz que recuadros: se duplica el primero
                import copy
                nuevo = copy.deepcopy(rects[0]._element); s.shapes._spTree.append(nuevo)
                sh = s.shapes[-1]; x, y, ww, hh = cajas9[k]; m = 0.012
                sh.left, sh.top = int(nl + (x - m) * w), int(nt + (y - m) * h)
                sh.width, sh.height = int((ww + 2 * m) * w), int((hh + 2 * m) * h)
    prs.save(salida)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pptx"); ap.add_argument("--salida"); ap.add_argument("--graficos", default=os.path.join(AQUI, "graficos"))
    a = ap.parse_args()
    os.makedirs(a.graficos, exist_ok=True)
    D, idx = cargar()
    corte = pd.Timestamp(D[D.mes == D.mes.max()].Fecha.iloc[0]).date()
    g = lambda n: os.path.join(a.graficos, f"slide{n}.png")
    info4 = slide4(D, g(4)); slide5(D, g(5)); slide6(D, g(6)); slide7(D, g(7)); slide8(D, g(8)); cajas9 = slide9(D, g(9))
    print("corte", corte, "| total AUM prom", round(info4["total"], 2), "bill. | Balanz puesto", info4["puesto_balanz"], "| fondos Balanz en top flujo:", len(cajas9))
    if a.pptx:
        actualizar_pptx(a.pptx, a.salida or a.pptx, {n: g(n) for n in range(4, 10)}, corte, info4, cajas9)
        print("presentacion:", a.salida or a.pptx)

if __name__ == "__main__":
    main()
