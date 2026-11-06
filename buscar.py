# BUSCAR VALOR (app BOLSA-LORENCITO): busca cualquier valor (par, acción, índice, materia prima, cripto)
# y guarda sus velas en velas/<SIM>.json para que la app dibuje su gráfico con la línea amarilla.
# Deja el resultado de la búsqueda en busqueda.json (la app lo lee para abrir el gráfico).
# Uso: python buscar.py "texto buscado" ID      (si el texto empieza por "=" se usa tal cual como ticker de Yahoo)
import sys, re, json, time
import pandas as pd, yfinance as yf
from velas import limpia, a_lista, cambios, AGRUPAR, MERCADOS

# Nombres en español que Yahoo no entiende bien
ALIAS = {
    "ORO": "GC=F", "GOLD": "GC=F", "PLATA": "SI=F", "SILVER": "SI=F", "PLATINO": "PL=F", "PALADIO": "PA=F",
    "PETROLEO": "CL=F", "PETROLEO WTI": "CL=F", "WTI": "CL=F", "BRENT": "BZ=F", "GAS NATURAL": "NG=F", "COBRE": "HG=F",
    "BITCOIN": "BTC-USD", "ETHEREUM": "ETH-USD", "SOLANA": "SOL-USD", "XRP": "XRP-USD",
    "IBEX": "^IBEX", "IBEX 35": "^IBEX", "IBEX35": "^IBEX", "SP500": "^GSPC", "S&P 500": "^GSPC", "S&P500": "^GSPC", "SP 500": "^GSPC",
    "NASDAQ": "^NDX", "NASDAQ 100": "^NDX", "DOW JONES": "^DJI", "DOW": "^DJI", "DAX": "^GDAXI", "CAC": "^FCHI", "CAC 40": "^FCHI",
    "EUROSTOXX": "^STOXX50E", "EURO STOXX 50": "^STOXX50E", "FTSE": "^FTSE", "NIKKEI": "^N225", "VIX": "^VIX",
}
DIVISAS = "EUR USD GBP JPY CHF CAD AUD NZD CNH CNY MXN SEK NOK DKK PLN TRY ZAR HKD SGD".split()
TIPOS = {"EQUITY": "Acción", "ETF": "ETF", "INDEX": "Índice", "CURRENCY": "Divisa", "CRYPTOCURRENCY": "Cripto",
         "FUTURE": "Futuro", "MUTUALFUND": "Fondo"}

def sin_acentos(t):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")

def candidatos(q):
    """Devuelve [(ticker, nombre, tipo, bolsa), ...] empezando por el más probable."""
    u = sin_acentos(q).upper().strip()
    if u.startswith("="):
        return [(q.strip()[1:].strip(), "", "", "")]
    if u in ALIAS:
        return [(ALIAS[u], q.strip().upper(), "", "")]
    fx = re.fullmatch(r"([A-Z]{3})\s*[/\-]?\s*([A-Z]{3})", u)
    if fx and fx.group(1) in DIVISAS and fx.group(2) in DIVISAS:
        a, b = fx.groups()
        return [(("CNH=X" if (a, b) == ("USD", "CNH") else f"{a}{b}=X"), f"{a}/{b}", "Divisa", "")]
    sal = []
    try:
        for x in yf.Search(q, max_results=8, news_count=0).quotes:
            t = x.get("symbol")
            if not t: continue
            sal.append((t, x.get("shortname") or x.get("longname") or t, TIPOS.get(x.get("quoteType", ""), x.get("quoteType", "")),
                        x.get("exchDisp") or x.get("exchange") or ""))
    except Exception as ex:
        print("Búsqueda de Yahoo falló:", ex)
    # Si la misma empresa cotiza en Madrid, primero la de Madrid (p. ej. Santander: SAN.MC antes que SAN de Nueva York)
    if sal:
        n0 = sal[0][1].upper()[:12]
        for i, x in enumerate(sal):
            if x[0].upper().endswith(".MC") and x[1].upper()[:12] == n0 and i:
                sal.insert(0, sal.pop(i)); break
    if not sal:
        sal = [(q.strip().upper(), q.strip().upper(), "", "")]   # probar el texto tal cual como ticker
    return sal

def nombre_archivo(ticker):
    # Si es uno de los mercados de los radares, se usa su archivo de siempre
    for sim, t in MERCADOS.items():
        if t == ticker: return sim
    return "B_" + re.sub(r"[^A-Za-z0-9]", "_", ticker).upper()

def simbolo_tv(ticker):
    t = ticker.upper()
    if t.endswith("=X"): return "FX:" + t[:-2] if len(t) == 8 else ""
    if t.endswith("-USD"): return "COINBASE:" + t[:-4] + "USD"
    if t.endswith(".MC"): return "BME:" + t[:-3]
    if t.endswith(".DE"): return "XETR:" + t[:-3]
    if t.endswith(".PA"): return "EURONEXT:" + t[:-3]
    if t.endswith(".L"): return "LSE:" + t[:-2]
    if t.endswith(".MI"): return "MIL:" + t[:-3]
    if t.endswith(".AS"): return "EURONEXT:" + t[:-3]
    ind = {"^IBEX": "BME:IBC", "^GSPC": "SP:SPX", "^NDX": "NASDAQ:NDX", "^DJI": "DJ:DJI", "^GDAXI": "XETR:DAX",
           "^FCHI": "EURONEXT:PX1", "^STOXX50E": "TVC:SX5E", "^FTSE": "TVC:UKX", "^N225": "TVC:NI225", "^VIX": "TVC:VIX",
           "GC=F": "OANDA:XAUUSD", "SI=F": "OANDA:XAGUSD", "CL=F": "TVC:USOIL", "BZ=F": "TVC:UKOIL", "NG=F": "TVC:NATURALGAS",
           "HG=F": "COMEX:HG1!", "PL=F": "OANDA:XPTUSD", "PA=F": "OANDA:XPDUSD"}
    if t in ind: return ind[t]
    if "." in t or "^" in t or "=" in t: return ""
    return t   # acciones de EE. UU.: TradingView las encuentra por el ticker

def descarga(ticker):
    tk = yf.Ticker(ticker)
    series = {}
    for intervalo, periodo, mins in [("5m", "60d", 5), ("15m", "60d", 15), ("30m", "60d", 30), ("1h", "730d", 60)]:
        for intento in range(2):
            try:
                d = tk.history(period=periodo, interval=intervalo, auto_adjust=False)
                if len(d): series[mins] = limpia(d)
                break
            except Exception as ex:
                print(f"Error {ticker} {intervalo}: {ex}"); time.sleep(5)
    if 60 in series:
        for m2, regla in AGRUPAR:
            series[m2] = series[60].resample(regla, origin="epoch", label="left", closed="left").agg(
                {"Open": "first", "High": "max", "Low": "min", "Close": "last"}).dropna()
    if 60 not in series or len(series[60]) < 50:
        # Sin velas horarias suficientes: se da por no encontrado
        return None
    return series

def main():
    q = sys.argv[1] if len(sys.argv) > 1 else ""
    ident = sys.argv[2] if len(sys.argv) > 2 else ""
    ahora = int(time.time())
    res = {"id": ident, "q": q, "hora": ahora, "ok": False}
    cands = candidatos(q) if q.strip() else []
    res["alternativas"] = [{"ticker": t, "nombre": n, "tipo": ti, "bolsa": b} for t, n, ti, b in cands[:8]]
    for t, n, ti, b in cands[:4]:          # si el primero no tiene datos, prueba los siguientes
        series = descarga(t)
        if not series: continue
        sim = nombre_archivo(t)
        sal = {"actualizado": ahora, "tf": {}, "radar": {}, "ticker": t, "nombre": n or t, "tv": simbolo_tv(t)}
        for mins, d in series.items():
            sal["tf"][str(mins)] = a_lista(d)
        desde = min((v[0][0] for v in sal["tf"].values() if v), default=0)
        for mins, d in series.items():
            try: sal["radar"][str(mins)] = cambios(d, mins, ahora, desde)
            except Exception as ex: print(f"Sin radar {t} {mins}: {ex}")
        with open(f"velas/{sim}.json", "w") as f:
            json.dump(sal, f, separators=(",", ":"))
        res.update({"ok": True, "sim": sim, "ticker": t, "nombre": n or t, "tipo": ti, "bolsa": b, "tv": sal["tv"]})
        print(f"Encontrado: {t} ({n}) -> velas/{sim}.json")
        break
    if not res["ok"]:
        res["error"] = "No he encontrado ese valor o Yahoo no tiene velas de él."
        print(res["error"])
    with open("busqueda.json", "w") as f:
        json.dump(res, f, ensure_ascii=False, separators=(",", ":"))

if __name__ == "__main__":
    main()
