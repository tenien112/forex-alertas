import time
"""
VIGILANTE BOT COMMODITIES by Lorenzo
Mismo sistema que el BOT COMPRAVENTA, pero un escalón más lento (probado 1 año
y 18 meses con su propio código, los cuatro mercados en positivo):
  - Solo ORO, PLATA, PETRÓLEO WTI y BITCOIN
  - 4 temporalidades: H1, H2, H4, H8 (los 4 indicadores de siempre)
  - ENTRADA: COMPRA cuando las 4 se alinean positivas por primera vez
             (alineación nueva); VENDE cuando se alinean negativas.
  - SALIDA:  con 1 temporalidad (H1): cierra cuando H1 deja de cumplir,
             o si la alineación global se da la vuelta.
  - Sin SL, sin TP, sin filtro EMA, sin trailing.

No guarda posiciones: en cada ejecución vuelve a simular el sistema vela a vela
sobre los últimos días y avisa de las señales nuevas (ABRE LARGO / ABRE CORTO / CIERRA LARGO / CIERRA CORTO)
que todavía no se hayan avisado. Solo guarda la hora del último aviso enviado
(estado_commodities.json) para no repetir.
"""
import sys, json, os
import numpy as np, pandas as pd, yfinance as yf, requests

MERCADOS = {"ORO": "GC=F", "PLATA": "SI=F", "PETRÓLEO WTI": "CL=F", "BITCOIN": "BTC-USD"}
FOREX = set()
TEMA = "forex-lorenzito-7k3q9"
BF, BS, BG, NL = 12, 26, 9, 5          # MACD cascada
EB, EC = 18, 5                         # EMA cascada
INVERTIR = False
TFS = [("H1", 60), ("H2", 120), ("H4", 240), ("H8", 480)]
TFS_MERCADO = {}
TF_SALIDA = 1                          # salir con las N temporalidades más pequeñas (modo Todas)
DIAS_SIM = 60                          # días de H1 que se re-simulan en cada ejecución
VENTANA_H = 8                          # se avisan señales de como mucho hace 8 h (por retrasos de GitHub)
ESTADO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "estado_commodities.json")


def ema(a, p):
    return pd.Series(a).ewm(span=p, adjust=False).mean().values


def estados_serie(c):
    """Estado (+1/-1/0) de los 4 indicadores en CADA vela de la serie de cierres c."""
    c = np.asarray(c, dtype=float)
    azul = np.zeros(len(c)); roja = np.zeros(len(c)); suma = np.zeros(len(c))
    for L in range(NL):
        m = 1 << L
        macd = ema(c, BF * m) - ema(c, BS * m)
        h = macd - ema(macd, BG * m)
        azul += np.maximum(h, 0); roja += np.maximum(-h, 0); suma += macd
    tot_ab = azul + roja
    cons = np.where(tot_ab > 0, (azul - roja) / np.where(tot_ab > 0, tot_ab, 1), 0)   # 1 MACD-HISTOGRAMA
    res = (-1 if INVERTIR else 1) * suma / NL                                          # 2 MACD-MULTIPLE
    e = [ema(c, EB * (1 << L)) for L in range(EC)]
    up = np.ones(len(c), bool); dn = np.ones(len(c), bool)
    for i in range(EC - 1):
        up &= e[i] > e[i + 1]; dn &= e[i] < e[i + 1]
    o3 = np.where(up, 1, np.where(dn, -1, 0))                                          # 3 EMAS-ORDENADAS (sin precio)
    o4 = np.where(up & (c > e[0]), 1, np.where(dn & (c < e[0]), -1, 0))
    tot = np.sign(cons) + np.sign(res) + o4                                            # 4 COMBINACION (con precio)
    pos = (cons > 0) & (res > 0) & (o3 > 0) & (tot > 0)
    neg = (cons < 0) & (res < 0) & (o3 < 0) & (tot < 0)
    return np.where(pos, 1, np.where(neg, -1, 0))


def descargar(ticker, ahora):
    m30 = yf.download(ticker, period="60d", interval="30m", progress=False, auto_adjust=False)
    h1 = yf.download(ticker, period="730d", interval="1h", progress=False, auto_adjust=False)
    for d in (m30, h1):
        if isinstance(d.columns, pd.MultiIndex):
            d.columns = d.columns.get_level_values(0)
    if len(m30) == 0 or len(h1) == 0:
        return None
    m30 = m30.tz_convert("UTC")["Close"].dropna()
    h1 = h1.tz_convert("UTC")["Close"].dropna()
    # solo velas ya cerradas
    m30 = m30[m30.index + pd.Timedelta(minutes=30) <= ahora]
    h1 = h1[h1.index + pd.Timedelta(minutes=60) <= ahora]
    series = {"M30": m30, "H1": h1}
    for nombre, mins in (("H2", 120), ("H4", 240), ("H8", 480)):
        s = h1.resample(f"{mins}min", origin="epoch", label="left", closed="left").last().dropna()
        series[nombre] = s[s.index + pd.Timedelta(minutes=mins) <= ahora]
    return series


def simular(series, tfs=None):
    tfs = tfs or TFS
    """Simula el sistema sobre las velas M30 de los últimos DIAS_SIM días.
    Devuelve (eventos, estado_final)."""
    tablas = []
    for nombre, mins in tfs:
        s = series[nombre]
        cierre = (s.index + pd.Timedelta(minutes=mins)).values
        tablas.append((nombre, cierre, estados_serie(s.values)))

    base, bmins = tfs[0]                                      # la temporalidad más pequeña marca el ritmo
    m30 = series[base]
    tiempos = m30.index + pd.Timedelta(minutes=bmins)         # momento de cierre de cada vela base
    precios = m30.values
    inicio = tiempos[-1] - pd.Timedelta(days=DIAS_SIM)

    eventos = []
    prev = None; pos = 0; entrada = None
    ult = None
    for t, precio in zip(tiempos, precios):
        if t < inicio:
            continue
        est = []
        for nombre, cierre, st in tablas:
            k = np.searchsorted(cierre, t.to_datetime64(), side="right") - 1
            est.append(int(st[k]) if k >= 0 else 0)
        glob = 1 if all(x == 1 for x in est) else -1 if all(x == -1 for x in est) else 0
        nueva_alc = prev is not None and prev != 1 and glob == 1
        nueva_baj = prev is not None and prev != -1 and glob == -1
        prev = glob

        n = min(TF_SALIDA, len(est))
        if pos == 1 and (glob == -1 or all(est[i] != 1 for i in range(n))):
            eventos.append({"t": t, "tipo": "CIERRA COMPRA", "precio": precio, "entrada": entrada, "est": est})
            pos = 0; entrada = None
        if pos == -1 and (glob == 1 or all(est[i] != -1 for i in range(n))):
            eventos.append({"t": t, "tipo": "CIERRA VENTA", "precio": precio, "entrada": entrada, "est": est})
            pos = 0; entrada = None
        if glob == 1 and pos == 0 and nueva_alc:
            pos = 1; entrada = (t, precio)
            eventos.append({"t": t, "tipo": "COMPRA", "precio": precio, "est": est})
        elif glob == -1 and pos == 0 and nueva_baj:
            pos = -1; entrada = (t, precio)
            eventos.append({"t": t, "tipo": "VENDE", "precio": precio, "est": est})
        ult = {"t": t, "est": est, "pos": pos, "entrada": entrada, "precio": precio}
    return eventos, ult


def txt_est(est):
    return " ".join(f"{nombre}{'+' if e == 1 else '-' if e == -1 else '.'}" for (nombre, _), e in zip(TFS, est))


def hora(t):
    return pd.Timestamp(t).tz_convert("Europe/Madrid").strftime("%d/%m %H:%M")


def fmt(p, mercado):
    if mercado in FOREX:
        return f"{p:.3f}" if "JPY" in mercado else f"{p:.5f}"
    return f"{p:.3f}" if mercado == "PLATA" else f"{p:.2f}"


def txt_dif(dif, mercado):
    """Ganancia/pérdida: en pips para el forex, por unidad en el resto."""
    if mercado in FOREX:
        pips = abs(dif) * (100 if "JPY" in mercado else 10000)
        return f"unos {pips:.0f} pips"
    return f"unos {fmt(abs(dif), mercado)} por unidad"


ETIQUETA = {"COMPRA": "ABRE LARGO", "VENDE": "ABRE CORTO",
            "CIERRA COMPRA": "CIERRA LARGO", "CIERRA VENTA": "CIERRA CORTO"}


def mensaje(mercado, ev):
    p = fmt(ev["precio"], mercado)
    if ev["tipo"] == "COMPRA":
        cuerpo = (f"🟢 ABRE LARGO en {mercado} ahora (entrar comprando).\n"
                  f"Precio aproximado: {p}\n"
                  f"(Señal de las {hora(ev['t'])})")
        prio, tag = "urgent", "green_circle"
    elif ev["tipo"] == "VENDE":
        cuerpo = (f"🔴 ABRE CORTO en {mercado} ahora (entrar vendiendo).\n"
                  f"Precio aproximado: {p}\n"
                  f"(Señal de las {hora(ev['t'])})")
        prio, tag = "urgent", "red_circle"
    else:
        t0, p0 = ev["entrada"]
        dif = ev["precio"] - p0 if ev["tipo"] == "CIERRA COMPRA" else p0 - ev["precio"]
        que = "LARGO" if ev["tipo"] == "CIERRA COMPRA" else "CORTO"
        cuerpo = (f"🔔 CIERRA el {que} de {mercado} ahora (solo cerrar, no abrir nada).\n"
                  f"Abierto el {hora(t0)} a {fmt(p0, mercado)}\n"
                  f"Precio aproximado: {p}\n"
                  f"{'Ganas' if dif >= 0 else 'Pierdes'} {txt_dif(dif, mercado)}\n"
                  f"(Señal de las {hora(ev['t'])})")
        prio, tag = "urgent", "bell"
    return f"VIGILANTE BOT COMMODITIES: {ETIQUETA[ev['tipo']]} {mercado}", cuerpo, prio, tag


def enviar(titulo, cuerpo, prio="high", tag="chart_with_upwards_trend"):
    print("AVISO:", titulo, "|", cuerpo.replace("\n", " | "))
    try:
        requests.post(f"https://ntfy.sh/{TEMA}", data=cuerpo.encode("utf-8"),
                      headers={"Title": titulo.encode("utf-8"), "Priority": prio, "Tags": tag}, timeout=15)
    except Exception as ex:
        print("Error enviando a ntfy:", ex)


def main():
    prueba = "--prueba" in sys.argv
    ahora = pd.Timestamp.now(tz="UTC")
    try:
        estado = json.load(open(ESTADO, encoding="utf-8"))
    except Exception:
        estado = {}

    resumen = []
    for mercado, ticker in MERCADOS.items():
        series = descargar(ticker, ahora)
        if series is None:
            print(f"Sin datos para {mercado}"); continue
        eventos, ult = simular(series, TFS_MERCADO.get(mercado, TFS))

        # Último aviso enviado; la primera vez solo se avisa de lo de la última hora
        ultimo = pd.Timestamp(estado[mercado]) if mercado in estado else ahora - pd.Timedelta(hours=1)
        limite = max(ultimo, ahora - pd.Timedelta(hours=VENTANA_H))
        nuevos = [e for e in eventos if e["t"] > limite]
        for ev in nuevos:
            enviar(*mensaje(mercado, ev))
        if nuevos:
            estado[mercado] = nuevos[-1]["t"].isoformat()
        elif mercado not in estado and eventos:
            estado[mercado] = eventos[-1]["t"].isoformat()

        if ult:
            g = 1 if all(x == 1 for x in ult["est"]) else -1 if all(x == -1 for x in ult["est"]) else 0
            tend = "sube ⬆️" if g == 1 else "baja ⬇️" if g == -1 else "sin dirección clara"
            if ult["pos"] == 0:
                linea = f"{mercado}: {tend}. No hay nada abierto. Espera el próximo aviso."
            else:
                t0, p0 = ult["entrada"]
                que = "LARGO" if ult["pos"] == 1 else "CORTO"
                linea = (f"{mercado}: {tend}. El sistema está en {que} desde el {hora(t0)} a {fmt(p0, mercado)}. "
                         f"Si no entraste, no entres ahora: espera al próximo aviso.")
            resumen.append(linea)

    bloques = list(resumen)
    print("\n".join(bloques))
    if prueba or "--resumen" in sys.argv:
        open("resumen_commodities.txt", "w", encoding="utf-8").write("\n\n".join(bloques) + "\n")

    partes = ["\n\n".join(bloques)] if bloques else []   # mensaje corto: va entero en uno

    def mandar(titulo, prio, tag):
        n = len(partes)
        for i in range(n, 0, -1):
            sufijo = f" ({i}/{n})" if n > 1 else ""
            enviar(titulo + sufijo, partes[i - 1], prio, tag)
            time.sleep(2)

    if prueba:
        mandar("VIGILANTE BOT COMMODITIES: estado actual", "default", "white_check_mark")
    elif "--resumen" in sys.argv:
        mandar("VIGILANTE BOT COMMODITIES: resumen diario", "default", "sunrise")

    json.dump(estado, open(ESTADO, "w", encoding="utf-8"), indent=1)


if __name__ == "__main__":
    main()
