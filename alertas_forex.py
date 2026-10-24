import sys, json, datetime as dt
import numpy as np, pandas as pd, yfinance as yf, requests

PARES = {"EUR/USD": "EURUSD=X", "EUR/GBP": "EURGBP=X", "EUR/JPY": "EURJPY=X", "GBP/USD": "GBPUSD=X",
         "USD/JPY": "USDJPY=X", "GBP/JPY": "GBPJPY=X", "EUR/AUD": "EURAUD=X", "EUR/CAD": "EURCAD=X",
         "AUD/USD": "AUDUSD=X", "USD/CAD": "USDCAD=X", "GBP/AUD": "GBPAUD=X", "GBP/CAD": "GBPCAD=X",
         "PETROLEO WTI": "CL=F", "ORO": "GC=F", "USD/CNH": "CNH=X", "USD/CHF": "USDCHF=X",
         "EUR/CHF": "EURCHF=X", "GBP/CHF": "GBPCHF=X"}
TFS = ["M30", "H1", "H2"]
TEMA = "forex-lorenzito-7k3q9"
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
    P = T - pd.Timedelta(hours=1)         # situación hace 1 hora
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

    def serie(par, tf, hasta):
        s, mins = datos[par][tf]
        if tf == "H2":
            s1 = cerradas(s, 60, hasta)
            s = s1.resample("2h", origin="epoch", label="left", closed="left").last().dropna()
        return cerradas(s, mins, hasta).values

    avisos = []; resumen = []
    for par in PARES:
        if par not in datos: continue
        ind_now = {tf: indicadores(serie(par, tf, T)) for tf in TFS}
        ind_prev = {tf: indicadores(serie(par, tf, P)) for tf in TFS}
        e_now = {tf: estado(v) for tf, v in ind_now.items()}
        e_prev = {tf: estado(v) for tf, v in ind_prev.items()}
        g_now = 1 if all(x == 1 for x in e_now.values()) else -1 if all(x == -1 for x in e_now.values()) else 0
        g_prev = 1 if all(x == 1 for x in e_prev.values()) else -1 if all(x == -1 for x in e_prev.values()) else 0
        resumen.append(f"{bonito(par)}: " + " ".join(f"{tf}{'+' if e_now[tf]==1 else '-' if e_now[tf]==-1 else '.'}" for tf in TFS)
                       + (" ALCISTA" if g_now == 1 else " BAJISTA" if g_now == -1 else ""))
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
                               f"{'positivos' if g_now==1 else 'negativos'} en M30, H1 y H2"))

    print(f"Vela evaluada: {T:%d/%m %H:%M} UTC (comparada con {P:%H:%M})")
    print("\n".join(resumen))
    enviar = "--prueba" in sys.argv
    for titulo, msg in avisos:
        print("AVISO:", titulo, "-", msg)
        requests.post(f"https://ntfy.sh/{TEMA}", data=msg.encode("utf-8"),
                      headers={"Title": "FOREX " + titulo, "Priority": "high", "Tags": "chart_with_upwards_trend"}, timeout=15)
    if enviar:
        requests.post(f"https://ntfy.sh/{TEMA}", data=("Prueba OK. Estado actual:\n" + "\n".join(resumen)).encode("utf-8"),
                      headers={"Title": "FOREX agente funcionando", "Priority": "default"}, timeout=15)
    if not avisos: print("Sin cambios: no se envía aviso.")

if __name__ == "__main__":
    main()
