# Guarda las últimas velas (OHLC) de todos los mercados en velas/<SIMBOLO>.json
# para que la app BOLSA-LORENCITO dibuje su propio gráfico con la línea vertical del último cambio.
# Se ejecuta al final de las pruebas manuales (las que lanza la app).
import os, json, time
import numpy as np, pandas as pd, yfinance as yf
from alertas_forex import indicadores_serie   # el mismo cálculo de los radares

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

def main():
    os.makedirs("velas", exist_ok=True)
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
        sal = {"actualizado": ahora, "tf": {}, "radar": {}}
        series = {}
        for mins, df in bruto.items():
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
        if not sal["tf"]:
            print(f"Sin velas para {nombre}"); continue
        with open(f"velas/{nombre}.json", "w") as f:
            json.dump(sal, f, separators=(",", ":"))
        print(f"{nombre}: " + ", ".join(f"{k}={len(v)}/{len(sal['radar'].get(k, []))}" for k, v in sal["tf"].items()))

if __name__ == "__main__":
    main()
