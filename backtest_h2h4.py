# Backtest: radar H2/H4 con medias más cortas vs actual. Datos H1 Yahoo 730d.
import json, numpy as np, pandas as pd, yfinance as yf, time
from alertas_forex import PARES

COSTE = {"ORO": .0004, "PLATA": .0008, "PETROLEO WTI": .0008, "PLATINO": .0020, "PALADIO": .0035, "BITCOIN": .0020}
VARIANTES = {"ACTUAL (5 capas)": (5, 5), "4 capas": (4, 4), "3 capas": (3, 3), "2 capas": (2, 2)}

def ema(a, p): return pd.Series(a).ewm(span=p, adjust=False).mean().values

def estado(c, NL, EC, BF=12, BS=26, BG=9, EB=18):
    c = np.asarray(c, float); n = len(c)
    az = np.zeros(n); ro = np.zeros(n); su = np.zeros(n)
    for L in range(NL):
        m = 1 << L
        macd = ema(c, BF*m) - ema(c, BS*m); h = macd - ema(macd, BG*m)
        az += np.maximum(h, 0); ro += np.maximum(-h, 0); su += macd
    t = az + ro
    cons = np.divide(az - ro, t, out=np.zeros(n), where=t > 0); res = su/NL
    e = [ema(c, EB*(1 << L)) for L in range(EC)]
    if EC > 1:
        sube = np.all([e[i] > e[i+1] for i in range(EC-1)], axis=0); baja = np.all([e[i] < e[i+1] for i in range(EC-1)], axis=0)
    else:
        sube = c > e[0]; baja = c < e[0]
    o3 = np.where(sube, 1, np.where(baja, -1, 0))
    o4 = np.where(sube & (c > e[0]), 1, np.where(baja & (c < e[0]), -1, 0))
    tot = np.sign(cons) + np.sign(res) + o4
    v = np.vstack([cons, res, o3, tot])
    return np.where(np.all(v > 0, 0), 1, np.where(np.all(v < 0, 0), -1, 0))

def sistema(c, st, coste):
    # Entra en el sentido del estado cuando pasa a +1/-1 y sale cuando deja de estarlo. Opera al cierre de la vela.
    ops = []; pos = 0; ent = 0
    for i in range(1, len(c)):
        if pos and st[i] != pos:
            ops.append(pos*(c[i]/ent - 1) - coste); pos = 0
        if not pos and st[i] != 0 and st[i] != st[i-1]:
            pos = st[i]; ent = c[i]
    return ops

def acierto(c, st, k):
    # % de velas en tendencia (+/-) en las que el precio de las k velas siguientes va en ese sentido
    f = np.r_[c[k:]/c[:-k] - 1, np.full(k, np.nan)]
    m = (st != 0) & ~np.isnan(f)
    return float(np.mean(np.sign(f[m]) == st[m])) if m.any() else np.nan

def retraso(c, st):
    # velas que tarda en marcar +/- después de un mínimo/máximo de 10 días (giro): media de lo que tarda en aparecer el nuevo signo
    return None

def resumen(ops):
    if not ops: return dict(ops=0, total=0, pf=0)
    o = np.array(ops); g = o[o > 0].sum(); p = -o[o < 0].sum()
    return dict(ops=len(o), total=round(o.sum()*100, 1), pf=round(g/p, 2) if p > 0 else 99)

def main():
    tick = list(PARES.values())
    for i in range(3):
        try:
            raw = yf.download(tick, period="730d", interval="1h", group_by="ticker", progress=False, auto_adjust=False, threads=True); break
        except Exception as e: print(e); time.sleep(20)
    filas = []
    for nom, t in PARES.items():
        try:
            d = raw[t][["Open", "High", "Low", "Close"]].dropna()
        except Exception: continue
        if len(d) < 2000: continue
        d = d.tz_convert("UTC") if d.index.tz is not None else d.tz_localize("UTC")
        coste = COSTE.get(nom, 0.0002)
        for regla, tf in [("2h", "H2"), ("4h", "H4")]:
            s = d.resample(regla, origin="epoch", label="left", closed="left").agg({"Close": "last"}).dropna()["Close"].values
            mitad = len(s)//2
            for vn, (NL, EC) in VARIANTES.items():
                st = estado(s, NL, EC)
                st[:300] = 0                      # calentamiento igual para todas
                ops_a = sistema(s[:mitad], st[:mitad], coste); ops_b = sistema(s[mitad:], st[mitad:], coste)
                r = resumen(ops_a + ops_b); ra = resumen(ops_a); rb = resumen(ops_b)
                filas.append(dict(mercado=nom, tf=tf, variante=vn, **r, mitad1=ra["total"], mitad2=rb["total"],
                                  acierto6=round(acierto(s, st, 6)*100, 1), acierto24=round(acierto(s, st, 24)*100, 1),
                                  en_tendencia=round(float(np.mean(st[300:] != 0))*100, 1),
                                  duracion=round(float(np.mean(np.diff(np.r_[0, np.flatnonzero(np.diff(st[300:]) != 0)]))), 1)))
        print(nom, "ok")
    df = pd.DataFrame(filas); df.to_csv("bt_h2h4_detalle.csv", index=False)
    g = df.groupby(["tf", "variante"]).agg(total=("total", "sum"), ops=("ops", "sum"), mitad1=("mitad1", "sum"), mitad2=("mitad2", "sum"),
        positivos=("total", lambda x: int((x > 0).sum())), mercados=("total", "size"), acierto6=("acierto6", "mean"),
        acierto24=("acierto24", "mean"), en_tendencia=("en_tendencia", "mean"), duracion_velas=("duracion", "mean")).round(1)
    g.to_csv("bt_h2h4_resumen.csv"); print(g.to_string())

if __name__ == "__main__": main()
