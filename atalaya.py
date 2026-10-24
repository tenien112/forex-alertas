# VIGILANTE ATALAYA by Lorenzo
# Mismo algoritmo que la app ATALAYA (tenien112/faro): ruta Argelia-Cartagena en 3 puntos,
# oleaje (3 modelos) + viento (4 modelos) de Open-Meteo, patera (20 h) y taxi (5 h),
# temporada y franjas horarias. Envía un aviso diario al móvil por ntfy.
import sys, math, datetime as dt
import requests
from zoneinfo import ZoneInfo

TEMA = "forex-lorenzito-7k3q9"   # mismo tema de ntfy que el Vigilante FOREX
UMBRAL = 70

PUNTOS = [(36.20, -0.40), (36.95, -0.75), (37.50, -0.95)]
RUMBO = 345
TIPOS = {
    "patera": dict(dur=20, olaOk=0.5, olaMax=1.5, vOk=8, vMax=20, franja=[1.0, 0.75, 0.6, 0.9]),
    "taxi":   dict(dur=5, olaOk=1.0, olaMax=2.5, vOk=12, vMax=28, franja=[1.0, 0.7, 0.6, 0.95]),
}
TEMPORADA = [0.55, 0.55, 0.6, 0.7, 0.85, 1, 1, 1, 1, 0.9, 0.7, 0.6]
FRANJAS = [("Madrugada", 0), ("Mañana", 6), ("Tarde", 12), ("Noche", 18)]
MOD_OLA = ["meteofrance_wave", "ecmwf_wam025", "ncep_gfswave025"]
MOD_VTO = ["ecmwf_ifs025", "meteofrance_seamless", "icon_seamless", "gfs_seamless"]
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]

clamp = lambda x, a, b: max(a, min(b, x))
def lin(v, ok, mx): return 1 if v <= ok else 0 if v >= mx else 1 - (v - ok) / (mx - ok)

def pedir(url):
    r = requests.get(url, timeout=30); r.raise_for_status(); j = r.json()
    return j if isinstance(j, list) else [j]

def media_serie(arrs):
    n = max(len(a) for a in arrs); out = []
    for i in range(n):
        v = [a[i] for a in arrs if i < len(a) and a[i] is not None]
        out.append(sum(v) / len(v) if v else None)
    return out

def media_viento(vels, dirs):
    n = max(len(a) for a in vels); V, D = [], []
    for i in range(n):
        x = y = s = k = 0
        for m in range(len(vels)):
            v = vels[m][i] if i < len(vels[m]) else None; d = dirs[m][i] if i < len(dirs[m]) else None
            if v is None or d is None: continue
            r = math.radians(d); x += v * math.sin(r); y += v * math.cos(r); s += v; k += 1
        if not k: V.append(None); D.append(None); continue
        V.append(s / k); D.append((math.degrees(math.atan2(x, y)) + 360) % 360)
    return V, D

def cargar():
    lat = ",".join(str(p[0]) for p in PUNTOS); lon = ",".join(str(p[1]) for p in PUNTOS)
    comun = f"latitude={lat}&longitude={lon}&past_days=1&forecast_days=7&timezone=Europe%2FMadrid"
    base = "https://marine-api.open-meteo.com/v1/marine?" + comun + "&hourly=wave_height"
    baseV = "https://api.open-meteo.com/v1/forecast?" + comun + "&hourly=wind_speed_10m,wind_direction_10m&wind_speed_unit=kn"
    M = None
    try:
        r = pedir(base + "&models=" + ",".join(MOD_OLA)); horas = r[0]["hourly"]["time"]; ola = []
        for p in r:
            ser = [p["hourly"].get("wave_height_" + m) for m in MOD_OLA]
            ser = [a for a in ser if a and any(v is not None for v in a)]
            ola.append(media_serie(ser) if ser else None)
        if all(ola): M = (horas, ola)
    except Exception: pass
    if not M:
        r = pedir(base); M = (r[0]["hourly"]["time"], [p["hourly"]["wave_height"] for p in r])
    V = None
    try:
        r = pedir(baseV + "&models=" + ",".join(MOD_VTO)); vel, dir_ = [], []
        for p in r:
            vs, ds = [], []
            for m in MOD_VTO:
                a = p["hourly"].get("wind_speed_10m_" + m); b = p["hourly"].get("wind_direction_10m_" + m)
                if a and b and any(v is not None for v in a): vs.append(a); ds.append(b)
            if not vs: raise ValueError("sin viento")
            mv, md = media_viento(vs, ds); vel.append(mv); dir_.append(md)
        V = (r[0]["hourly"]["time"], vel, dir_)
    except Exception: pass
    if not V:
        r = pedir(baseV); V = (r[0]["hourly"]["time"], [p["hourly"]["wind_speed_10m"] for p in r], [p["hourly"]["wind_direction_10m"] for p in r])
    pos = {h: i for i, h in enumerate(V[0])}
    al = lambda a: [a[pos[h]] if h in pos else None for h in M[0]]
    return dict(horas=M[0], ola=M[1], vel=[al(a) for a in V[1]], dir=[al(a) for a in V[2]])

def viento_efectivo(vel, d):
    proa = math.cos(math.radians(d - RUMBO))
    return vel * (1 + 0.5 * proa if proa > 0 else 1 + 0.3 * proa)

def evalua(D, idx, tipo):
    T = TIPOS[tipo]; ini = idx - T["dur"]
    if ini < 0: return None
    olaMax = olaSum = vMax = vSum = 0; n = 0
    for k in range(ini, idx + 1):
        f = (k - ini) / T["dur"]; p = 0 if f < 1/3 else 1 if f < 2/3 else 2
        o, v, d = D["ola"][p][k], D["vel"][p][k], D["dir"][p][k]
        if o is None or v is None or d is None: continue
        ve = viento_efectivo(v, d)
        olaMax = max(olaMax, o); olaSum += o; vMax = max(vMax, ve); vSum += ve; n += 1
    if n < T["dur"] * 0.6: return None
    ola = 0.6 * olaMax + 0.4 * olaSum / n; vto = 0.6 * vMax + 0.4 * vSum / n
    return lin(ola, T["olaOk"], T["olaMax"]) ** 0.6 * lin(vto, T["vOk"], T["vMax"]) ** 0.4

def calcular(D):
    por_dia = {}
    for i, h in enumerate(D["horas"]): por_dia.setdefault(h[:10], []).append(i)
    hoy = dt.datetime.now(ZoneInfo("Europe/Madrid")).strftime("%Y-%m-%d"); res = []
    for fecha in sorted(por_dia):
        idxs = por_dia[fecha]
        if fecha < hoy or len(idxs) < 24: continue
        temp = TEMPORADA[int(fecha[5:7]) - 1]; dia = {"fecha": fecha}
        for tipo in ("patera", "taxi"):
            T = TIPOS[tipo]; fr = []
            for fi, (_, d0) in enumerate(FRANJAS):
                mejor = None
                for h in range(d0, d0 + 6):
                    mar = evalua(D, idxs[h], tipo)
                    if mar is None: continue
                    p = clamp(100 * mar * temp * T["franja"][fi], 0, 95)
                    mejor = p if mejor is None or p > mejor else mejor
                fr.append(round(mejor) if mejor is not None else None)
            vals = sorted([v for v in fr if v is not None], reverse=True)
            total = round(min(97, vals[0] + (100 - vals[0]) * 0.25 * ((vals[1] if len(vals) > 1 else 0) / 100))) if vals else None
            dia[tipo] = (total, fr)
        res.append(dia)
    return res

def fecha_txt(f):
    d = dt.date.fromisoformat(f); return f"{DIAS[d.weekday()]} {d.day} {MESES[d.month - 1]}"

def main():
    prueba = "--prueba" in sys.argv
    ahora = dt.datetime.now(ZoneInfo("Europe/Madrid"))
    if not prueba and ahora.hour != 8:
        print(f"Son las {ahora:%H:%M} en Madrid: solo se avisa a las 8. Nada que hacer."); return
    res = calcular(cargar())[:3]
    HORAS = ["00-06", "06-12", "12-18", "18-24"]
    f = lambda v: "–" if v is None else f"{v} %"
    bloques = []; riesgo = False
    for n, d in enumerate(res):
        pt, frp = d["patera"]; tx, frt = d["taxi"]
        if (pt or 0) > UMBRAL or (tx or 0) > UMBRAL: riesgo = True
        cab = ("HOY " if n == 0 else "MAÑANA " if n == 1 else "") + fecha_txt(d["fecha"]).upper()
        lin_ = [cab]
        for i, (nom, _) in enumerate(FRANJAS):
            lin_.append(f"{nom} {HORAS[i]}: patera {f(frp[i])} | taxi {f(frt[i])}")
        lin_.append(f"TOTAL DÍA: patera {f(pt)} | taxi {f(tx)}")
        bloques.append("\n".join(lin_))
    cuerpo = "\n\n".join(bloques)
    if riesgo:
        titulo, prio = "ATALAYA: POSIBLE LLEGADA", "high"
        cuerpo = "⚠️ Probabilidad alta (más del 70 %)\n\n" + cuerpo
    else:
        titulo, prio = "ATALAYA: sin riesgo relevante", "default"
    print(titulo); print(cuerpo)
    requests.post(f"https://ntfy.sh/{TEMA}", data=cuerpo.encode("utf-8"),
                  headers={"Title": titulo, "Priority": prio, "Tags": "ocean"}, timeout=15)

if __name__ == "__main__":
    main()
