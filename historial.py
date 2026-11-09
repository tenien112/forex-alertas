# Historial LARGO de velas de cTrader para el gráfico de la app BOLSA-LORENZITO (se ejecuta una vez al día).
# Escribe historial/<MERCADO>.json.gz (mismo formato que velas/, pero sin límite de velas) en la carpeta indicada.
# El workflow lo sube a la rama 'historial' borrando la versión anterior, para que el repositorio no crezca.
import os, sys, json, gzip, time
import velas, ctrader_velas
from velas import AGRUPAR, a_lista, cambios

DIAS = {5: 60, 15: 120, 30: 365, 60: 3 * 365}   # M5 2 meses, M15 4 meses, M30 1 año, H1 (y H2/H4/H8) 3 años

def main(destino):
    os.makedirs(destino, exist_ok=True)
    velas.MAX_VELAS = 10**9                       # sin recorte
    t0 = time.time()
    datos = ctrader_velas.descarga(list(velas.MERCADOS), DIAS, renovar=True)
    print(f"Descargado de cTrader en {time.time() - t0:.0f} s")
    ahora = int(time.time())
    for nombre, por_tf in datos.items():
        series = dict(por_tf)
        if 60 in por_tf:
            for m2, regla in AGRUPAR:
                series[m2] = por_tf[60].resample(regla, origin="epoch", label="left", closed="left").agg(
                    {"Open": "first", "High": "max", "Low": "min", "Close": "last"}).dropna()
        sal = {"actualizado": ahora, "fuente": "ctrader", "tf": {}, "radar": {}}
        for mins, d in series.items():
            sal["tf"][str(mins)] = a_lista(d)
            try:
                sal["radar"][str(mins)] = cambios(d, mins, ahora, 0)
            except Exception as ex:
                print(f"Sin radar {nombre} {mins}: {ex}")
        with gzip.open(os.path.join(destino, f"{nombre}.json.gz"), "wt", compresslevel=9) as f:
            json.dump(sal, f, separators=(",", ":"))
        print(f"{nombre}: " + ", ".join(f"{k}={len(v)}" for k, v in sal["tf"].items()),
              f"· {os.path.getsize(os.path.join(destino, nombre + '.json.gz')) // 1024} KB")

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "historial")
