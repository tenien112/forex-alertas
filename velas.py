# Guarda las últimas velas (OHLC) de todos los mercados en velas/<SIMBOLO>.json
# para que la app BOLSA-LORENCITO dibuje su propio gráfico con la línea vertical del último cambio.
# Se ejecuta al final de las pruebas manuales (las que lanza la app).
import os, json, time
import numpy as np, pandas as pd, yfinance as yf
from alertas_forex import indicadores_serie, BF, BS, BG, NL, EB, EC, INVERTIR   # el mismo cálculo de los radares

# Nombre del archivo = símbolo base de TradingView que usa la app (FX:EURUSD -> EURUSD, OANDA:XAUUSD -> XAUUSD...)
MERCADOS = {
    "AUDUSD": "AUDUSD=X", "EURAUD": "EURAUD=X", "EURCAD": "EURCAD=X", "EURCHF": "EURCHF=X", "EURCNH": "EURCNH=X",
    "EURGBP": "EURGBP=X", "EURJPY": "EURJPY=X", "EURUSD": "EURUSD=X", "GBPAUD": "GBPAUD=X", "GBPCAD": "GBPCAD=X",
    "GBPCHF": "GBPCHF=X", "GBPJPY": "GBPJPY=X", "GBPUSD": "GBPUSD=X", "USDCAD": "USDCAD=X", "USDCHF": "USDCHF=X",
    "USDCNH": "CNH=X", "USDJPY": "USDJPY=X",
    "XAUUSD": "GC=F", "XAGUSD": "SI=F", "XPTUSD": "PL=F", "XPDUSD": "PA=F", "USOIL": "CL=F",
    "BTCUSD": "BTC-USD", "ETHUSD": "ETH-USD",
}
# Mismo histórico que los radares, para que el estado de cada vela salga igual que en el radar
DESCARGAS = [("5m", "60d", 5), ("15m", "60d", 15), ("30m", "60d", 30), ("1h", "730d", 60)]
AGRUPAR = [(120, "2h"), (240, "4h"), (480, "8h")]   # se sacan de H1, igual que en los radares
MAX_VELAS = 400

def limpia(d):
    d = d[["Open", "High", "Low", "Close"]].dropna()
    return d.tz_convert("UTC") if d.index.tz is not None else d.tz_localize("UTC")

def a_lista(d):
    d = d.tail(MAX_VELAS)
    t = ((d.index - pd.Timestamp("1970-01-01", tz="UTC")) // pd.Timedelta("1s")).tolist()
    return [[int(a)] + [float(f"{x:.6g}") for x in fila] for a, fila in zip(t, d.values.tolist())]

def cambios(d, mins, ahora, desde):
    # Estado del radar (1 alcista, -1 bajista, 0 neutro) de esta temporalidad al cierre de cada vela.
    # Solo se guardan los momentos en que cambia: [[hora de cierre, estado], ...]
    st = indicadores_serie(d["Close"].values)
    cierre = ((d.index - pd.Timestamp("1970-01-01", tz="UTC")) // pd.Timedelta("1s")).values + mins * 60
    sal, ant = [], None
    for t, e in zip(cierre.tolist(), st.tolist()):
        if t > ahora: break                      # vela aún abierta: el radar no la cuenta
        if e != ant:
            sal.append([int(t), int(e)]); ant = e
    while len(sal) > 1 and sal[1][0] <= desde: sal.pop(0)   # nada anterior a las velas guardadas
    return sal

def _ema_fin(a, p):
    # Último valor de la EMA (igual que ewm(span=p, adjust=False))
    return pd.Series(a).ewm(span=p, adjust=False).mean().values

def _giro_eval(c, X):
    # Estado del radar (1, -1, 0) si la próxima vela cierra en cada precio de X (vector).
    # Las EMAs son lineales en el último cierre: se calcula el estado previo una vez y se extiende a cada X.
    k = lambda p: 2.0 / (p + 1)
    sh = np.zeros_like(X); sm = np.zeros_like(X)
    for L in range(NL):
        m = 1 << L
        af, as_, ag = k(BF*m), k(BS*m), k(BG*m)
        ef, es = _ema_fin(c, BF*m), _ema_fin(c, BS*m)
        sig = _ema_fin(ef - es, BG*m)[-1]
        macd = (ef[-1]*(1-af) + af*X) - (es[-1]*(1-as_) + as_*X)
        h = macd - (sig*(1-ag) + ag*macd)
        sh += h; sm += macd
    cons = np.sign(sh)                      # (azul-roja) tiene el signo de la suma de histogramas
    res = (-1 if INVERTIR else 1)*np.sign(sm)
    e = []
    for L in range(EC):
        a = k(EB*(1 << L)); e.append(_ema_fin(c, EB*(1 << L))[-1]*(1-a) + a*X)
    sube = np.all([e[i] > e[i+1] for i in range(EC-1)], axis=0)
    baja = np.all([e[i] < e[i+1] for i in range(EC-1)], axis=0)
    o3 = np.where(sube, 1, np.where(baja, -1, 0))
    o4 = np.where(sube & (X > e[0]), 1, np.where(baja & (X < e[0]), -1, 0))
    tot = cons + res + o4
    pos = (cons > 0) & (res > 0) & (o3 > 0) & (tot > 0)
    neg = (cons < 0) & (res < 0) & (o3 < 0) & (tot < 0)
    return np.where(pos, 1, np.where(neg, -1, 0))

def precio_giro(d, mins, ahora):
    # Precio de cierre de la vela en curso a partir del cual el radar de esta temporalidad
    # pasa a BAJISTA (cierre por debajo) o a ALCISTA (cierre por encima). None si no es alcanzable en esta vela.
    t0 = ((d.index - pd.Timestamp("1970-01-01", tz="UTC")) // pd.Timedelta("1s")).values
    cerr = t0 + mins*60 <= ahora
    c = d["Close"].values[cerr].astype(float)
    if len(c) < 50: return None
    abierta = not cerr[-1]
    fin = int(t0[-1] + mins*60) if abierta else int(t0[-1] + 2*mins*60)
    p = float(d["Close"].values[-1])
    def busca(lo, hi, n):
        X = np.linspace(lo, hi, n); return X, _giro_eval(c, X)
    X, st = busca(p*0.85, p*1.15, 6001)   # más allá de ±15 % se da por inalcanzable
    sal = {"cierre": fin, "precio": p, "ahora": int(_giro_eval(c, np.array([p]))[0])}
    neg = np.where(st == -1)[0]; pos = np.where(st == 1)[0]
    paso = X[1] - X[0]
    if len(neg):
        b = X[neg[-1]]; X2, s2 = busca(b, b + paso, 401); sal["baja"] = float(X2[np.where(s2 == -1)[0][-1]])
    if len(pos):
        b = X[pos[0]]; X2, s2 = busca(b - paso, b, 401); sal["sube"] = float(X2[np.where(s2 == 1)[0][0]])
    return sal

# Días que se piden a cTrader para las velas de cada ejecución (como el histórico de Yahoo, para calcular bien el radar)
DIAS_CT = {5: 10, 15: 30, 30: 60, 60: 240}

def main():
    os.makedirs("velas", exist_ok=True)
    ct = {}
    try:
        import ctrader_velas
        t0 = time.time()
        ct = ctrader_velas.descarga(list(MERCADOS), DIAS_CT)
        print(f"cTrader: {len(ct)} mercados en {time.time() - t0:.0f} s")
    except Exception as ex:
        print("cTrader no disponible, uso Yahoo:", ex)
    tickers = list(MERCADOS.values())
    bruto = {}
    for intervalo, periodo, mins in DESCARGAS:
        for intento in range(2):
            try:
                bruto[mins] = yf.download(tickers, period=periodo, interval=intervalo, group_by="ticker",
                                          progress=False, auto_adjust=False, threads=True)
                break
            except Exception as ex:
                print(f"Error descargando {intervalo}: {ex}"); time.sleep(10)
    ahora = int(time.time())
    for nombre, t in MERCADOS.items():
        sal = {"actualizado": ahora, "tf": {}, "radar": {}, "giro": {}, "fuente": "yahoo"}
        series = {}
        if ct.get(nombre) and 60 in ct[nombre]:
            sal["fuente"] = "ctrader"
            for mins, d in ct[nombre].items():
                series[mins] = d
            d = ct[nombre][60]
            for m2, regla in AGRUPAR:
                series[m2] = d.resample(regla, origin="epoch", label="left", closed="left").agg(
                    {"Open": "first", "High": "max", "Low": "min", "Close": "last"}).dropna()
        for mins, df in ([] if sal["fuente"] == "ctrader" else bruto.items()):
            try:
                d = limpia(df[t])
            except Exception:
                continue
            if len(d) == 0: continue
            series[mins] = d
            if mins == 60:
                for m2, regla in AGRUPAR:
                    series[m2] = d.resample(regla, origin="epoch", label="left", closed="left").agg(
                        {"Open": "first", "High": "max", "Low": "min", "Close": "last"}).dropna()
        for mins, d in series.items():
            sal["tf"][str(mins)] = a_lista(d)
        # Desde la vela más antigua que se guarda (la de H8 suele ser la más lejana)
        desde = min((v[0][0] for v in sal["tf"].values() if v), default=0)
        for mins, d in series.items():
            try:
                sal["radar"][str(mins)] = cambios(d, mins, ahora, desde)
            except Exception as ex:
                print(f"Sin estados de radar para {nombre} {mins}: {ex}")
            try:
                g = precio_giro(d, mins, ahora)
                if g: sal["giro"][str(mins)] = g
            except Exception as ex:
                print(f"Sin precio de giro para {nombre} {mins}: {ex}")
        if not sal["tf"]:
            print(f"Sin velas para {nombre}"); continue
        with open(f"velas/{nombre}.json", "w") as f:
            json.dump(sal, f, separators=(",", ":"))
        print(f"{nombre} [{sal['fuente']}]: " + ", ".join(f"{k}={len(v)}/{len(sal['radar'].get(k, []))}" for k, v in sal["tf"].items()))

if __name__ == "__main__":
    main()
