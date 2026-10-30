import sys, json
import numpy as np, pandas as pd, yfinance as yf, requests
# Mismos mercados e indicadores que el RADAR CAMBIO TENDENCIAS, pero en M5, M15, M30, H1, H2 y H4
from alertas_forex import PARES, COMMODITIES, NOMBRES, TEMA, indicadores, indicadores_serie, estado, cerradas, rangos_recencia, marca

TFS = ["M5", "M15", "M30", "H1", "H2", "H4"]
MINS = {"M5": 5, "M15": 15, "M30": 30, "H1": 60, "H2": 120, "H4": 240}
ESTADO = "estado_radar_rapido.json"
NOMBRE = "VIGILANTE RADAR M5-M15-M30-H1-H2-H4"

def signo(e): return "+" if e == 1 else "-" if e == -1 else "."

def main():
    ahora = pd.Timestamp.now(tz="UTC")
    madrid = ahora.tz_convert("Europe/Madrid")
    if madrid.weekday() >= 5 and "--prueba" not in sys.argv:
        print("Fin de semana (hora de Madrid): no se vigila."); return
    T = ahora.floor("5min")                 # último cierre de M5
    P = T - pd.Timedelta(minutes=30)        # situación en la revisión anterior (cada 30 min)
    datos = {}
    for par, t in PARES.items():
        try:
            m5 = yf.download(t, period="60d", interval="5m", progress=False, auto_adjust=False)
            m15 = yf.download(t, period="60d", interval="15m", progress=False, auto_adjust=False)
            m30 = yf.download(t, period="60d", interval="30m", progress=False, auto_adjust=False)
            h1 = yf.download(t, period="200d", interval="1h", progress=False, auto_adjust=False)
        except Exception as ex:
            print(f"Error descargando {par}: {ex}"); continue
        ds = {}
        for tf, d in zip(["M5", "M15", "M30", "H1"], (m5, m15, m30, h1)):
            if isinstance(d.columns, pd.MultiIndex): d.columns = d.columns.get_level_values(0)
            if len(d) == 0: break
            ds[tf] = d.tz_convert("UTC")["Close"].dropna()
        if "H1" in ds:
            ds["H2"] = ds["H1"].resample("2h", origin="epoch", label="left", closed="left").last().dropna()
            ds["H4"] = ds["H1"].resample("4h", origin="epoch", label="left", closed="left").last().dropna()
        if len(ds) < len(TFS):
            print(f"Sin datos para {par}, se omite"); continue
        datos[par] = ds

    def desde_cuando(par, combo, hasta):
        # Busca la vela M5 desde la que el signo de todas las temporalidades es el mismo que ahora
        estados = {}
        for tf in TFS:
            s = datos[par][tf]
            st = pd.Series(indicadores_serie(s.values), index=s.index + pd.Timedelta(minutes=MINS[tf]))
            estados[tf] = st[st.index <= hasta]
        cierres = estados[TFS[0]].index
        if len(cierres) == 0: return None
        gs = np.ones(len(cierres), dtype=bool); vals = {}
        for tf in TFS:
            st = estados[tf]
            pos = st.index.searchsorted(cierres, side="right") - 1
            vals[tf] = np.where(pos >= 0, st.values[np.clip(pos, 0, None)], 0)
            gs &= (vals[tf] == combo[tf])
        if not gs[-1]: return None
        malos = np.where(~gs)[0]
        rangos = rangos_recencia(vals, combo, TFS)
        if len(malos) == 0: return ("antes", cierres[0], rangos)
        i = malos[-1]
        return ("", cierres[i + 1], rangos)

    try:
        with open(ESTADO) as f: guardado = json.load(f)
    except Exception:
        guardado = {}
    nuevo = dict(guardado)
    avisos = []; resumen = []
    for par in PARES:
        if par not in datos: continue
        ind_now = {tf: indicadores(cerradas(datos[par][tf], MINS[tf], T).values) for tf in TFS}
        ind_prev = {tf: indicadores(cerradas(datos[par][tf], MINS[tf], P).values) for tf in TFS}
        e_now = {tf: estado(v) for tf, v in ind_now.items()}
        e_prev = {tf: estado(v) for tf, v in ind_prev.items()}
        g = lambda e: 1 if all(x == 1 for x in e.values()) else -1 if all(x == -1 for x in e.values()) else 0
        g_now, g_prev = g(e_now), g(e_prev)
        if par in guardado: g_prev = guardado[par]
        nuevo[par] = g_now
        texto = ""; cambiadas = {}
        try:
            d = desde_cuando(par, e_now, T)
            if d:
                cambiadas = d[2]
                texto = (" antes" if d[0] else "") + f" {d[1].tz_convert('Europe/Madrid'):%d/%m %H:%M}"
        except Exception as ex:
            print(f"No se pudo calcular desde cuándo para {par}: {ex}")
        resumen.append(f"{par}: " + " ".join(marca(f"{tf}{signo(e_now[tf])}", cambiadas.get(tf, 0)) for tf in TFS)
                       + (" ALCISTA" if g_now == 1 else " BAJISTA" if g_now == -1 else "") + texto)
        if g_now != g_prev:
            if g_prev != 0:
                fallos = []
                for tf in TFS:
                    v = ind_now[tf]
                    malos = [NOMBRES[i] for i in range(4) if not (v[i] > 0 if g_prev == 1 else v[i] < 0)]
                    if malos: fallos.append(f"{tf}: {', '.join(malos)}")
                avisos.append(("FIN " + ("ALCISTA " if g_prev == 1 else "BAJISTA ") + par,
                               f"⚠️ {par} deja de estar {'ALCISTA' if g_prev == 1 else 'BAJISTA'}. Falla: " + " | ".join(fallos)))
            if g_now != 0:
                avisos.append((("ALCISTA " if g_now == 1 else "BAJISTA ") + par,
                               f"{'🟢' if g_now == 1 else '🔴'} {par} {'ALCISTA' if g_now == 1 else 'BAJISTA'}: los 4 indicadores "
                               f"{'positivos' if g_now == 1 else 'negativos'} en las 6 temporalidades (M5, M15, M30, H1, H2 y H4)"))

    resumen.sort(key=lambda l: (l.split(":")[0] in COMMODITIES, l.split(":")[0]))
    i = next((n for n, l in enumerate(resumen) if l.split(":")[0] in COMMODITIES), None)
    if i is not None: resumen.insert(i, "— COMMODITIES —")
    if i: resumen.insert(0, "— FOREX —")
    print(f"Vela evaluada: {T:%d/%m %H:%M} UTC")
    print("\n".join(resumen))
    for titulo, msg in avisos:
        print("AVISO:", titulo, "-", msg)
        requests.post(f"https://ntfy.sh/{TEMA}", data=msg.encode("utf-8"),
                      headers={"Title": f"{NOMBRE}: {titulo}".encode("utf-8"), "Priority": "high", "Tags": "chart_with_upwards_trend"}, timeout=15)
    if "--prueba" in sys.argv:
        requests.post(f"https://ntfy.sh/{TEMA}", data=("Prueba OK. Estado actual:\n" + "\n".join(resumen)).encode("utf-8"),
                      headers={"Title": f"{NOMBRE}: funcionando".encode("utf-8"), "Priority": "default"}, timeout=15)
    if not avisos: print("Sin cambios: no se envía aviso.")
    with open(ESTADO, "w") as f: json.dump(nuevo, f, indent=1, ensure_ascii=False)

if __name__ == "__main__":
    main()
