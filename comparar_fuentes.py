# Compara el radar calculado con precios de Yahoo (como ahora) y con precios de cTrader.
# Mismos indicadores; solo cambian los precios. Escribe comparacion.md.
import time
import numpy as np, pandas as pd
import fuente_ctrader as F
from alertas_forex import PARES, indicadores_serie

TFS = {"M5": ("5m", "60d", 5), "M15": ("15m", "60d", 15), "M30": ("30m", "60d", 30), "H1": ("1h", "730d", 60)}
AGR = {"H2": 120, "H4": 240}

def serie(d):
    if isinstance(d.columns, pd.MultiIndex): d.columns = d.columns.get_level_values(0)
    return d.tz_convert("UTC")["Close"].dropna() if len(d) else None

def estados(s, mins, ahora):
    st = pd.Series(indicadores_serie(s.values), index=s.index + pd.Timedelta(minutes=mins))
    st = st[st.index <= ahora]
    if not len(st): return None, None
    cambio = st.index[-1]
    dif = st.values != st.values[-1]
    if dif.any(): cambio = st.index[np.where(dif)[0][-1] + 1]
    return int(st.values[-1]), cambio

def todo(fuente, t, ahora):
    sal = {}
    for tf, (iv, per, mins) in TFS.items():
        d = (F._original if fuente == "yahoo" else F.download)(t, period=per, interval=iv, progress=False, auto_adjust=False)
        s = serie(d)
        if s is None: continue
        sal[tf] = estados(s, mins, ahora)
        if tf == "H1":
            for tf2, m2 in AGR.items():
                s2 = s.resample(f"{m2}min", origin="epoch", label="left", closed="left").last().dropna()
                sal[tf2] = estados(s2, m2, ahora)
    return sal

S = {1: "+", -1: "-", 0: "."}
ahora = pd.Timestamp.now(tz="UTC")
filas, iguales, total, iguales_hora = [], 0, 0, 0
for nombre, t in PARES.items():
    if t not in F.YAHOO_A_CTRADER: continue
    y, c = todo("yahoo", t, ahora), todo("ctrader", t, ahora)
    celdas = []
    for tf in ["M5", "M15", "M30", "H1", "H2", "H4"]:
        if tf not in y or tf not in c or y[tf][0] is None or c[tf][0] is None:
            celdas.append("?"); continue
        total += 1
        ey, hy = y[tf]; ec, hc = c[tf]
        mismo = ey == ec
        iguales += mismo
        misma_hora = mismo and abs((hy - hc).total_seconds()) <= TFS.get(tf, (0, 0, AGR.get(tf, 60)))[2] * 60
        iguales_hora += misma_hora
        hm = lambda h: h.tz_convert("Europe/Madrid").strftime("%d/%m %H:%M")
        celdas.append(f"{S[ey]}{'' if mismo else ' ≠ ' + S[ec]}" + ("" if misma_hora else f" ({hm(hy)} / {hm(hc)})"))
    filas.append(f"| {nombre} | " + " | ".join(celdas) + " |")
txt = [f"# Radar con Yahoo frente a cTrader ({ahora.tz_convert('Europe/Madrid'):%d/%m/%Y %H:%M})", "",
       "Signo de cada temporalidad: Yahoo ≠ cTrader cuando no coinciden; entre paréntesis la hora del último cambio (Yahoo / cTrader) cuando difiere.", "",
       "| Mercado | M5 | M15 | M30 | H1 | H2 | H4 |", "|---|---|---|---|---|---|---|"] + filas + ["",
       f"Mismo signo: {iguales} de {total} ({100*iguales/max(total,1):.0f} %). Mismo signo y misma hora de cambio: {iguales_hora} de {total} ({100*iguales_hora/max(total,1):.0f} %)."]
open("comparacion.md", "w").write("\n".join(txt))
print("\n".join(txt))
