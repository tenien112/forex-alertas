"""
VIGILANTE COMUNES M5-H4 by Lorenzo
Avisa al móvil (ntfy) cuando EMPIEZA una coincidencia nueva en COMUNES M5-H4 de la app BOLSA-LORENCITO:
  - RADAR M5-M30-H1-H2-H4 BAJISTA  + BOT COMPRAVENTA en CORTO
  - RADAR M5-M30-H1-H2-H4 ALCISTA  + BOT COMPRAVENTA en LARGO
Lo lanza el despertador cada 30 minutos (dentro de vigilante.yml). Guarda las coincidencias
en estado_comunes_m5h4.json para avisar solo de las nuevas.
"""
import sys, json, os, unicodedata
import pandas as pd, requests
import vigilante_radar_m5h4 as R
import vigilante_oro as B
from alertas_forex import indicadores, estado, cerradas, TEMA

ESTADO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "estado_comunes_m5h4.json")
NOMBRE = "VIGILANTE COMUNES M5-H4"


def norm(t):
    return unicodedata.normalize("NFD", t).encode("ascii", "ignore").decode().upper().strip()


def main():
    prueba = "--prueba" in sys.argv
    ahora = pd.Timestamp.now(tz="UTC")
    if ahora.tz_convert("Europe/Madrid").weekday() >= 5 and not prueba:
        print("Fin de semana (hora de Madrid): no se vigila."); return
    T = ahora.floor("5min")

    # Radar M5-M30-H1-H2-H4: 1 ALCISTA, -1 BAJISTA, 0 nada
    radar, lineas = {}, {}
    for par, ds in R.descargar_datos().items():
        e = {tf: estado(indicadores(cerradas(ds[tf], R.MINS[tf], T).values)) for tf in R.TFS}
        g = 1 if all(x == 1 for x in e.values()) else -1 if all(x == -1 for x in e.values()) else 0
        radar[norm(par)] = g
        lineas[norm(par)] = (par, " ".join(f"{tf}{R.signo(e[tf])}" for tf in R.TFS))

    # Bot compraventa: 1 LARGO, -1 CORTO, 0 nada abierto
    bot = {}
    for mercado, ticker in B.MERCADOS.items():
        series = B.descargar(ticker, ahora)
        if series is None: continue
        _, ult = B.simular(series, B.TFS_MERCADO.get(mercado, B.TFS))
        if ult: bot[norm(mercado)] = (ult["pos"], ult.get("entrada"))

    comunes = {}
    for k, g in radar.items():
        if g and k in bot and bot[k][0] == g:
            comunes[k] = g

    try:
        antes = json.load(open(ESTADO, encoding="utf-8"))
        primera = False
    except Exception:
        antes, primera = {}, True

    nuevas = [k for k, g in comunes.items() if antes.get(k) != g]
    print("Coincidencias ahora:", comunes or "ninguna")
    if primera and not prueba:
        print("Primera ejecución: se guarda el estado sin avisar.")
        nuevas = []
    for k in sorted(nuevas):
        g = comunes[k]; par, signos = lineas[k]
        lado = "CORTO" if g == -1 else "LARGO"
        cuerpo = (f"{'🔴' if g == -1 else '🟢'} EMPIEZA coincidencia en {par}: radar M5-H4 "
                  f"{'BAJISTA' if g == -1 else 'ALCISTA'} y bot en {lado}.\n{signos}")
        ent = bot[k][1]
        if ent:
            cuerpo += f"\nBot en {lado} desde el {B.hora(ent[0])}"
        print("AVISO:", cuerpo)
        try:
            requests.post(f"https://ntfy.sh/{TEMA}", data=cuerpo.encode("utf-8"),
                          headers={"Title": f"{NOMBRE}: {par} {lado}".encode("utf-8"),
                                   "Priority": "high", "Tags": "handshake"}, timeout=15)
        except Exception as ex:
            print("Error enviando a ntfy:", ex)
    # Coincidencias que se acaban
    terminadas = [] if primera else [k for k, g in antes.items() if k in radar and k in bot and comunes.get(k) != g]
    # Si falló la descarga de un mercado, se mantiene como estaba (no se da por terminado)
    for k, g in antes.items():
        if (k not in radar or k not in bot) and k not in comunes: comunes[k] = g
    for k in sorted(terminadas):
        g = antes[k]; lado = "CORTO" if g == -1 else "LARGO"
        par, signos = lineas.get(k, (k, ""))
        bpos = bot.get(k, (None,))[0]
        motivo = []
        if radar.get(k) != g: motivo.append("el radar M5-H4 ya no está " + ("BAJISTA" if g == -1 else "ALCISTA"))
        if bpos is not None and bpos != g: motivo.append(f"el bot ya no está en {lado}")
        cuerpo = (f"⚪ FIN de coincidencia en {par} ({lado}): " + (" y ".join(motivo) or "deja de coincidir") + "."
                  + (f"\n{signos}" if signos else ""))
        print("AVISO:", cuerpo)
        try:
            requests.post(f"https://ntfy.sh/{TEMA}", data=cuerpo.encode("utf-8"),
                          headers={"Title": f"{NOMBRE}: FIN {par} {lado}".encode("utf-8"),
                                   "Priority": "high", "Tags": "warning"}, timeout=15)
        except Exception as ex:
            print("Error enviando a ntfy:", ex)
    if prueba and not nuevas and not terminadas:
        txt = "\n".join(f"{lineas[k][0]}: {'CORTO' if g == -1 else 'LARGO'}" for k, g in sorted(comunes.items())) or "Ninguna coincidencia ahora mismo."
        requests.post(f"https://ntfy.sh/{TEMA}", data=("Prueba OK. Coincidencias:\n" + txt).encode("utf-8"),
                      headers={"Title": f"{NOMBRE}: funcionando".encode("utf-8"), "Priority": "default"}, timeout=15)
    json.dump(comunes, open(ESTADO, "w", encoding="utf-8"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
