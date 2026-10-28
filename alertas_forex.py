import sys, json, datetime as dt
import numpy as np, pandas as pd, yfinance as yf, requests

PARES = {"EUR/USD": "EURUSD=X", "EUR/GBP": "EURGBP=X", "EUR/JPY": "EURJPY=X", "GBP/USD": "GBPUSD=X",
         "USD/JPY": "USDJPY=X", "GBP/JPY": "GBPJPY=X", "EUR/AUD": "EURAUD=X", "EUR/CAD": "EURCAD=X",
         "AUD/USD": "AUDUSD=X", "USD/CAD": "USDCAD=X", "GBP/AUD": "GBPAUD=X", "GBP/CAD": "GBPCAD=X",
         "PETROLEO WTI": "CL=F", "ORO": "GC=F", "PLATA": "SI=F", "USD/CNH": "CNH=X", "EUR/CNH": "EURCNH=X", "USD/CHF": "USDCHF=X",
         "EUR/CHF": "EURCHF=X", "GBP/CHF": "GBPCHF=X", "BITCOIN": "BTC-USD"}
TFS = ["M30", "H1", "H2"]
TEMA = "forex-lorenzito-7k3q9"
ESTADO = "estado_forex.json"           # último estado de cada par (para no perder cambios)
BF, BS, BG, NL = 12, 26, 9, 5          # MACD cascada
EB, EC = 18, 5                         # EMA cascada
INVERTIR = False
NOMBRES = ["MACD-HISTOGRAMA", "MACD-MULTIPLE", "EMAS-ORDENADAS", "COMBINACION"]

def ema(a, p):
    return pd.Series(a).ewm(span=p, adjust=False).mean().values

def indicadores(c):
    azul = roja = suma = 0.0
    for L in range(NL):
        m = 1 << L
        macd = ema(c, BF*m) - ema(c, BS*m)
        h = macd[-1] - ema(macd, BG*m)[-1]
        azul += max(h, 0); roja += max(-h, 0); suma += macd[-1]
    cons = (azul-roja)/(azul+roja) if azul+roja > 0 else 0       # 1
    res = (-1 if INVERTIR else 1)*suma/NL                                              # 2 MACD media (ya en sentido correcto)
    e = [ema(c, EB*(1 << L))[-1] for L in range(EC)]
    def orden(precio):
        a = all(e[i] > e[i+1] for i in range(EC-1)) and (precio is None or c[-1] > e[0])
        b = all(e[i] < e[i+1] for i in range(EC-1)) and (precio is None or c[-1] < e[0])
        return 1 if a else -1 if b else 0
    o3 = orden(None)                                            # 3 (sin precio)
    tot = np.sign(cons) + np.sign(res) + orden(True)            # 4 (capa 3 con precio)
    return [cons, res, o3, tot]

def indicadores_serie(c):
    # Los mismos 4 indicadores, pero calculados en cada vela (las EMAs son causales)
    c = np.asarray(c, dtype=float)
    azul = np.zeros(len(c)); roja = np.zeros(len(c)); suma = np.zeros(len(c))
    for L in range(NL):
        m = 1 << L
        macd = ema(c, BF*m) - ema(c, BS*m)
        h = macd - ema(macd, BG*m)
        azul += np.maximum(h, 0); roja += np.maximum(-h, 0); suma += macd
    tot_ar = azul + roja
    cons = np.divide(azul - roja, tot_ar, out=np.zeros(len(c)), where=tot_ar > 0)
    res = (-1 if INVERTIR else 1)*suma/NL
    e = [ema(c, EB*(1 << L)) for L in range(EC)]
    sube = np.all([e[i] > e[i+1] for i in range(EC-1)], axis=0)
    baja = np.all([e[i] < e[i+1] for i in range(EC-1)], axis=0)
    o3 = np.where(sube, 1, np.where(baja, -1, 0))
    o4 = np.where(sube & (c > e[0]), 1, np.where(baja & (c < e[0]), -1, 0))
    tot = np.sign(cons) + np.sign(res) + o4
    v = np.vstack([cons, res, o3, tot])
    return np.where(np.all(v > 0, axis=0), 1, np.where(np.all(v < 0, axis=0), -1, 0))

def estado(v):
    if all(x > 0 for x in v): return 1
    if all(x < 0 for x in v): return -1
    return 0

def cerradas(df, minutos, hasta):
    # solo velas cuyo cierre es <= 'hasta'
    return df[df.index + pd.Timedelta(minutes=minutos) <= hasta]

def bonito(p): return p

def main():
    ahora = pd.Timestamp.now(tz="UTC")
    madrid = ahora.tz_convert("Europe/Madrid")
    if madrid.weekday() >= 5 and "--prueba" not in sys.argv:
        print("Fin de semana (hora de Madrid): no se vigila."); return
    T = ahora.floor("30min")              # último cierre de M30
    P = T - pd.Timedelta(minutes=30)      # situación hace media hora (se ejecuta cada 30 min)
    datos = {}
    for par in PARES:
        t = PARES[par]
        m30 = yf.download(t, period="60d", interval="30m", progress=False, auto_adjust=False)
        h1 = yf.download(t, period="730d", interval="1h", progress=False, auto_adjust=False)
        for d in (m30, h1):
            if isinstance(d.columns, pd.MultiIndex): d.columns = d.columns.get_level_values(0)
        if len(m30) == 0 or len(h1) == 0:
            print(f"Sin datos para {par}, se omite"); continue
        m30 = m30.tz_convert("UTC")["Close"].dropna(); h1 = h1.tz_convert("UTC")["Close"].dropna()
        h1 = h1[h1.index >= h1.index[-1] - pd.Timedelta(days=500)]
        datos[par] = {"M30": (m30, 30), "H1": (h1, 60), "H2": (h1, 120)}

    def serie_completa(par, tf):
        s, mins = datos[par][tf]
        if tf == "H2":
            s = s.resample("2h", origin="epoch", label="left", closed="left").last().dropna()
        return s, mins

    def desde_cuando(par, g, hasta):
        # Busca la vela M30 desde la que las 3 temporalidades están alineadas en el mismo sentido
        cierres = None; estados = {}
        for tf in TFS:
            s, mins = serie_completa(par, tf)
            st = pd.Series(indicadores_serie(s.values), index=s.index + pd.Timedelta(minutes=mins))
            estados[tf] = st[st.index <= hasta]
            if tf == "M30": cierres = estados[tf].index
        if cierres is None or len(cierres) == 0: return None
        gs = np.ones(len(cierres), dtype=bool)
        for tf in TFS:
            st = estados[tf]
            pos = st.index.searchsorted(cierres, side="right") - 1
            val = np.where(pos >= 0, st.values[np.clip(pos, 0, None)], 0)
            gs &= (val == g)
        if not gs[-1]: return None
        malos = np.where(~gs)[0]
        if len(malos) == 0: return ("antes del", cierres[0])
        return ("desde el", cierres[malos[-1] + 1])

    def serie(par, tf, hasta):
        s, mins = datos[par][tf]
        if tf == "H2":
            s1 = cerradas(s, 60, hasta)
            s = s1.resample("2h", origin="epoch", label="left", closed="left").last().dropna()
        return cerradas(s, mins, hasta).values

    try:
        with open(ESTADO) as f: guardado = json.load(f)
    except Exception:
        guardado = {}
    nuevo = dict(guardado)
    avisos = []; resumen = []
    for par in PARES:
        if par not in datos: continue
        ind_now = {tf: indicadores(serie(par, tf, T)) for tf in TFS}
        ind_prev = {tf: indicadores(serie(par, tf, P)) for tf in TFS}
        e_now = {tf: estado(v) for tf, v in ind_now.items()}
        e_prev = {tf: estado(v) for tf, v in ind_prev.items()}
        g_now = 1 if all(x == 1 for x in e_now.values()) else -1 if all(x == -1 for x in e_now.values()) else 0
        g_prev = 1 if all(x == 1 for x in e_prev.values()) else -1 if all(x == -1 for x in e_prev.values()) else 0
        # Si hay estado guardado de la última revisión, se compara con él (GitHub a veces se salta horas)
        if par in guardado: g_prev = guardado[par]
        nuevo[par] = g_now
        texto_desde = ""
        if g_now != 0:
            try:
                d = desde_cuando(par, g_now, T)
                if d: texto_desde = f" {d[0]} {d[1].tz_convert('Europe/Madrid'):%d/%m %H:%M}"
            except Exception as ex:
                print(f"No se pudo calcular desde cuándo para {par}: {ex}")
        resumen.append(f"{bonito(par)}: " + " ".join(f"{tf}{'+' if e_now[tf]==1 else '-' if e_now[tf]==-1 else '.'}" for tf in TFS)
                       + (" ALCISTA" if g_now == 1 else " BAJISTA" if g_now == -1 else "") + texto_desde)
        if g_now != g_prev:
            if g_prev != 0:
                fallos = []
                for tf in TFS:
                    v = ind_now[tf]
                    malos = [NOMBRES[i] for i in range(4) if not (v[i] > 0 if g_prev == 1 else v[i] < 0)]
                    if malos: fallos.append(f"{tf}: {', '.join(malos)}")
                avisos.append(("FIN " + ("ALCISTA " if g_prev == 1 else "BAJISTA ") + bonito(par),
                               f"⚠️ {bonito(par)} deja de estar {'ALCISTA' if g_prev==1 else 'BAJISTA'}. Falla: " + " | ".join(fallos)))
            if g_now != 0:
                avisos.append((("ALCISTA " if g_now == 1 else "BAJISTA ") + bonito(par),
                               f"{'🟢' if g_now==1 else '🔴'} {bonito(par)} {'ALCISTA' if g_now==1 else 'BAJISTA'}: los 4 indicadores "
                               f"{'positivos' if g_now==1 else 'negativos'} en las 3 temporalidades (M30, H1 y H2)"))

    print(f"Vela evaluada: {T:%d/%m %H:%M} UTC (comparada con {P:%H:%M})")
    print("\n".join(resumen))
    enviar = "--prueba" in sys.argv
    for titulo, msg in avisos:
        print("AVISO:", titulo, "-", msg)
        requests.post(f"https://ntfy.sh/{TEMA}", data=msg.encode("utf-8"),
                      headers={"Title": ("VIGILANTE RADAR CAMBIO TENDENCIAS: " + titulo).encode("utf-8"), "Priority": "high", "Tags": "chart_with_upwards_trend"}, timeout=15)
    if enviar:
        requests.post(f"https://ntfy.sh/{TEMA}", data=("Prueba OK. Estado actual:\n" + "\n".join(resumen)).encode("utf-8"),
                      headers={"Title": "VIGILANTE RADAR CAMBIO TENDENCIAS: funcionando".encode("utf-8"), "Priority": "default"}, timeout=15)
    if not avisos: print("Sin cambios: no se envía aviso.")
    with open(ESTADO, "w") as f: json.dump(nuevo, f, indent=1, ensure_ascii=False)

if __name__ == "__main__":
    main()
