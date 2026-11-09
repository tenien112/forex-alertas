# Simula el RADAR CAMBIO TENDENCIAS (M30-H1-H2) en los últimos ~55 días con señales de Yahoo y con señales de cTrader.
# Regla (la del radar): entrar cuando M30, H1 y H2 se alinean (alineación nueva), salir cuando la M30 deja de acompañar.
# Las operaciones de las dos fuentes se miden con los MISMOS precios (cTrader, contado), para comparar solo las señales.
import numpy as np, pandas as pd
import fuente_ctrader as F
from alertas_forex import PARES, indicadores_serie

def baja(fuente, t, iv, per):
    d = (F._original if fuente == "yahoo" else F.download)(t, period=per, interval=iv, progress=False, auto_adjust=False)
    if isinstance(d.columns, pd.MultiIndex): d.columns = d.columns.get_level_values(0)
    return d.tz_convert("UTC")["Close"].dropna() if len(d) else None

def estados(s, mins):
    return pd.Series(indicadores_serie(s.values), index=s.index + pd.Timedelta(minutes=mins))   # estado al CIERRE

def senales(m30, h1, rejilla):
    h2 = h1.resample("120min", origin="epoch", label="left", closed="left").last().dropna()
    e = {k: estados(s, m).reindex(rejilla, method="ffill").fillna(0).values
         for k, (s, m) in {"M30": (m30, 30), "H1": (h1, 60), "H2": (h2, 120)}.items()}
    return e

def opera(e, precio):
    pos, ent, ops = 0, 0.0, []
    alin_prev = 0
    for i in range(len(precio)):
        a = 1 if (e["M30"][i] == 1 and e["H1"][i] == 1 and e["H2"][i] == 1) else -1 if (e["M30"][i] == -1 and e["H1"][i] == -1 and e["H2"][i] == -1) else 0
        if pos and e["M30"][i] != pos:
            ops.append(pos * (precio[i] - ent) / ent * 100); pos = 0
        if not pos and a and a != alin_prev:
            pos, ent = a, precio[i]
        alin_prev = a
    if pos: ops.append(pos * (precio[-1] - ent) / ent * 100)
    return ops

def resumen(ops):
    g = sum(x for x in ops if x > 0); p = -sum(x for x in ops if x < 0)
    return len(ops), sum(ops), (g / p if p else float("inf")), (100 * sum(1 for x in ops if x > 0) / len(ops) if ops else 0)

filas, tot = [], {"yahoo": [], "ctrader": []}
for nombre, t in PARES.items():
    if t not in F.YAHOO_A_CTRADER: continue
    try:
        S = {f: (baja(f, t, "30m", "60d"), baja(f, t, "1h", "730d")) for f in ("yahoo", "ctrader")}
        if any(v is None for par in S.values() for v in par): raise ValueError("faltan datos")
        ini = max(S["yahoo"][0].index[0], S["ctrader"][0].index[0]) + pd.Timedelta(days=3)
        precio_ct = S["ctrader"][0]
        rejilla = (precio_ct[precio_ct.index >= ini].index + pd.Timedelta(minutes=30))
        precio = precio_ct[precio_ct.index >= ini].values
        res = {}
        for f in ("yahoo", "ctrader"):
            ops = opera(senales(S[f][0], S[f][1], rejilla), precio)
            tot[f] += ops; res[f] = resumen(ops)
        y, c = res["yahoo"], res["ctrader"]
        filas.append(f"| {nombre} | {y[0]} | {y[1]:+.2f} % | {y[2]:.2f} | {c[0]} | {c[1]:+.2f} % | {c[2]:.2f} |")
    except Exception as ex:
        filas.append(f"| {nombre} | error: {ex} | | | | | |")
Y, C = resumen(tot["yahoo"]), resumen(tot["ctrader"])
txt = ["# RADAR CAMBIO TENDENCIAS: señales de Yahoo frente a señales de cTrader (últimos ~55 días)", "",
       "Entrada al alinearse M30, H1 y H2; salida cuando la M30 deja de acompañar. Resultado medido con precios de cTrader, sin costes.", "",
       "| Mercado | Ops Yahoo | Resultado Yahoo | PF Yahoo | Ops cTrader | Resultado cTrader | PF cTrader |", "|---|---|---|---|---|---|---|"] + filas + ["",
       f"**TOTAL Yahoo:** {Y[0]} operaciones, suma {Y[1]:+.2f} %, PF {Y[2]:.2f}, aciertos {Y[3]:.0f} %",
       f"**TOTAL cTrader:** {C[0]} operaciones, suma {C[1]:+.2f} %, PF {C[2]:.2f}, aciertos {C[3]:.0f} %"]
open("comparacion_senales.md", "w").write("\n".join(txt)); print("\n".join(txt))
