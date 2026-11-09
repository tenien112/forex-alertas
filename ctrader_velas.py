# Velas de cTrader (cuenta demo de Spotware) para el gráfico de la app BOLSA-LORENZITO.
# Mismo formato que las de Yahoo: DataFrame con Open/High/Low/Close e índice en UTC.
import time
import pandas as pd
import ctrader_api as ct

# Nombre en la app -> símbolo en cTrader (el platino XPTUSD no está: sigue con Yahoo)
MAPA = {n: n for n in ["AUDUSD", "EURAUD", "EURCAD", "EURCHF", "EURCNH", "EURGBP", "EURJPY", "EURUSD", "GBPAUD",
                       "GBPCAD", "GBPCHF", "GBPJPY", "GBPUSD", "USDCAD", "USDCHF", "USDCNH", "USDJPY",
                       "XAUUSD", "XAGUSD", "XPDUSD", "BTCUSD", "ETHUSD"]}
MAPA["USOIL"] = "XTIUSD"
PERIODO = {5: "M5", 15: "M15", 30: "M30", 60: "H1"}

def a_df(v):
    if not v: return None
    d = pd.DataFrame([x[1:] for x in v], columns=["Open", "High", "Low", "Close"],
                     index=pd.to_datetime([x[0] for x in v], unit="ms", utc=True))
    return d[~d.index.duplicated(keep="last")].sort_index()

def descarga(nombres, dias, renovar=False):
    """{nombre: {minutos: DataFrame}} con 'dias' de historia por temporalidad (dict minutos->días)."""
    access, _ = ct.token(renovar=renovar)
    c, cuenta, _ = ct.conecta(access)
    sal = {}
    try:
        sims = ct.simbolos(c, cuenta)
        ahora = int(time.time() * 1000)
        for n in nombres:
            sid = sims.get(MAPA.get(n, ""))
            if not sid: continue
            sal[n] = {}
            for mins, per in PERIODO.items():
                try:
                    d = a_df(ct.velas(c, cuenta, sid, per, ahora - dias[mins] * 86400000, ahora))
                    if d is not None and len(d): sal[n][mins] = d
                except Exception as ex:
                    print(f"cTrader sin {n} {per}: {ex}")
    finally:
        c.cierra()
    return sal
