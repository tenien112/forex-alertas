# Radares y robots con precios de cTrader (cuenta demo de Spotware) en vez de Yahoo, con Yahoo de reserva.
# Basta con importar este módulo: sustituye yfinance.download para UN ticker con intervalo 5m/15m/30m/1h.
# Las descargas de varios tickers a la vez (velas.py, gráfico de siempre) y lo que no está en cTrader
# (platino, acciones…) siguen yendo a Yahoo. Si cTrader falla, todo vuelve a Yahoo solo.
import os, time
import pandas as pd
import yfinance as yf

_original = yf.download
YAHOO_A_CTRADER = {
    "AUDUSD=X": "AUDUSD", "CHFJPY=X": "CHFJPY", "EURAUD=X": "EURAUD", "EURCAD=X": "EURCAD", "EURCHF=X": "EURCHF", "EURCNH=X": "EURCNH",
    "EURGBP=X": "EURGBP", "EURJPY=X": "EURJPY", "EURUSD=X": "EURUSD", "GBPAUD=X": "GBPAUD", "GBPCAD=X": "GBPCAD",
    "GBPCHF=X": "GBPCHF", "GBPJPY=X": "GBPJPY", "GBPUSD=X": "GBPUSD", "USDCAD=X": "USDCAD", "USDCHF=X": "USDCHF",
    "CNH=X": "USDCNH", "USDJPY=X": "USDJPY",
    "GC=F": "XAUUSD", "SI=F": "XAGUSD", "PA=F": "XPDUSD", "CL=F": "XTIUSD", "BTC-USD": "BTCUSD", "ETH-USD": "ETHUSD",
}
PERIODO = {"5m": "M5", "15m": "M15", "30m": "M30", "1h": "H1"}
# Días como máximo por temporalidad (los indicadores del radar se estabilizan con ~1.500 velas; así va más rápido)
TOPE_DIAS = {"5m": 15, "15m": 30, "30m": 60, "1h": 730}

_estado = {"con": None, "cuenta": None, "sims": None, "falla": os.environ.get("RADAR_FUENTE", "").lower() == "yahoo"}
_cache = {}
usados = {"ctrader": set(), "yahoo": set()}

def _conecta():
    if _estado["con"] is None and not _estado["falla"]:
        try:
            import ctrader_api as ct
            access, _ = ct.token(renovar=False)
            c, cuenta, _ = ct.conecta(access)
            _estado.update(con=c, cuenta=cuenta, sims=ct.simbolos(c, cuenta))
        except Exception as ex:
            print("cTrader no disponible, los radares usan Yahoo:", ex)
            _estado["falla"] = True
    return _estado["con"]

def _dias(period):
    try:
        p = str(period)
        if p.endswith("d"): return int(p[:-1])
        if p.endswith("mo"): return int(p[:-2]) * 31
        if p.endswith("y"): return int(p[:-1]) * 366
    except Exception:
        pass
    return 60

def download(tickers=None, *args, **kw):
    interval = kw.get("interval", "1d")
    simbolo = YAHOO_A_CTRADER.get(tickers) if isinstance(tickers, str) else None
    if simbolo and interval in PERIODO:
        clave = (tickers, interval, kw.get("period"))
        if clave in _cache: return _cache[clave].copy()
        c = _conecta()
        sid = (_estado["sims"] or {}).get(simbolo) if c else None
        if sid:
            try:
                import ctrader_api as ct
                ahora = int(time.time() * 1000)
                dias = min(_dias(kw.get("period", "60d")), TOPE_DIAS[interval])
                v = ct.velas(c, _estado["cuenta"], sid, PERIODO[interval], ahora - dias * 86400000, ahora)
                if v:
                    d = pd.DataFrame([x[1:] for x in v], columns=["Open", "High", "Low", "Close"],
                                     index=pd.DatetimeIndex(pd.to_datetime([x[0] for x in v], unit="ms", utc=True), name="Datetime"))
                    d = d[~d.index.duplicated(keep="last")].sort_index()
                    d["Adj Close"] = d["Close"]; d["Volume"] = 0
                    _cache[clave] = d
                    usados["ctrader"].add(tickers)
                    return d.copy()
            except Exception as ex:
                print(f"cTrader falló con {tickers} {interval}, uso Yahoo: {ex}")
    if isinstance(tickers, str): usados["yahoo"].add(tickers)
    return _original(tickers, *args, **kw)

yf.download = download

import atexit
@atexit.register
def _resumen():
    if usados["ctrader"] or usados["yahoo"]:
        print(f"FUENTE DE PRECIOS · cTrader: {len(usados['ctrader'])} mercados · Yahoo: {sorted(usados['yahoo'])}")
    try:
        if _estado["con"]: _estado["con"].cierra()
    except Exception:
        pass
