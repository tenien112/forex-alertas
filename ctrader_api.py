# Conexión con la Open API de cTrader (app BOLSA-LORENZITO) para descargar velas con mucho historial.
# - Usa el protocolo JSON por WebSocket (puerto 5036), sin librerías de cTrader.
# - Claves: CTRADER_CLIENT_SECRET y CTRADER_REFRESH_TOKEN (secretos de GitHub). El Client ID no es secreto.
# - El refresh token cambia cada vez que se usa: el token vigente se guarda CIFRADO en ctrader_token.enc
#   (cifrado con una clave sacada del Client Secret), así el workflow lo puede renovar solo cada mes.
import os, json, time, base64, hashlib, urllib.request, urllib.parse, ssl
import websocket                      # pip install websocket-client
from cryptography.fernet import Fernet  # pip install cryptography

CLIENT_ID = "47661_ji4qQoQH3QicsYCNzh1kSlzZpwq9gS38uqwR8TqsV56lMoQZuZ"
SECRET = os.environ.get("CTRADER_CLIENT_SECRET", "")
REFRESH_INICIAL = os.environ.get("CTRADER_REFRESH_TOKEN", "")
FICH_TOKEN = "ctrader_token.enc"
HOSTS = {True: "live.ctraderapi.com", False: "demo.ctraderapi.com"}

# Tipos de mensaje de la Open API
APP_AUTH, APP_AUTH_R = 2100, 2101
ACC_AUTH, ACC_AUTH_R = 2102, 2103
SYMBOLS, SYMBOLS_R = 2114, 2115
TRENDBARS, TRENDBARS_R = 2137, 2138
ERROR = 2142
ACC_LIST, ACC_LIST_R = 2149, 2150
HEARTBEAT = 51
PERIODOS = {"M1": 1, "M5": 5, "M15": 7, "M30": 8, "H1": 9, "H4": 10, "D1": 12}

# ---------- Token (cifrado en el repo) ----------
def _fernet():
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(("bolsa-lorenzito|" + SECRET).encode()).digest()))

def _lee_token():
    if os.path.exists(FICH_TOKEN):
        try:
            return json.loads(_fernet().decrypt(open(FICH_TOKEN, "rb").read()))
        except Exception as ex:
            print("No se pudo leer el token guardado:", ex)
    return None

def _guarda_token(t):
    open(FICH_TOKEN, "wb").write(_fernet().encrypt(json.dumps(t).encode()))
    print("Token guardado (cifrado). Caduca:", time.strftime("%d/%m/%Y", time.gmtime(t["expira"])))

def _pide_token(refresh):
    q = urllib.parse.urlencode({"grant_type": "refresh_token", "refresh_token": refresh,
                                "client_id": CLIENT_ID, "client_secret": SECRET})
    req = urllib.request.Request("https://openapi.ctrader.com/apps/token?" + q, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.load(r)
    if not d.get("accessToken"):
        raise RuntimeError(f"cTrader no dio token: {d.get('errorCode')} {d.get('description')}")
    return {"access": d["accessToken"], "refresh": d["refreshToken"], "expira": int(time.time()) + int(d.get("expiresIn", 2628000))}

def token():
    """Devuelve un access token válido. Solo renueva si quedan menos de 5 días (cada renovación cambia el refresh token)."""
    t = _lee_token()
    if t and t["expira"] - time.time() > 5 * 86400:
        return t["access"], False
    refresh = (t or {}).get("refresh") or REFRESH_INICIAL
    if not refresh:
        raise RuntimeError("Falta el refresh token (secreto CTRADER_REFRESH_TOKEN)")
    try:
        t = _pide_token(refresh)
    except Exception as ex:
        if t and REFRESH_INICIAL and refresh != REFRESH_INICIAL:
            print("Falló el token guardado, pruebo con el del secreto:", ex)
            t = _pide_token(REFRESH_INICIAL)
        else:
            raise
    _guarda_token(t)
    return t["access"], True

# ---------- Conexión ----------
class CTrader:
    def __init__(self, live):
        self.ws = websocket.create_connection(f"wss://{HOSTS[live]}:5036", timeout=60, sslopt={"cert_reqs": ssl.CERT_REQUIRED})
        self.n = 0

    def pide(self, tipo, payload, espera):
        self.n += 1
        mid = f"m{self.n}"
        self.ws.send(json.dumps({"clientMsgId": mid, "payloadType": tipo, "payload": payload}))
        limite = time.time() + 60
        while time.time() < limite:
            m = json.loads(self.ws.recv())
            pt = m.get("payloadType")
            if pt == HEARTBEAT:
                self.ws.send(json.dumps({"payloadType": HEARTBEAT, "payload": {}}))
                continue
            if m.get("clientMsgId") != mid:
                continue
            if pt == ERROR or (m.get("payload") or {}).get("errorCode"):
                p = m.get("payload") or {}
                raise RuntimeError(f"cTrader: {p.get('errorCode')} {p.get('description', '')}")
            if pt == espera:
                return m.get("payload") or {}
        raise TimeoutError(f"Sin respuesta a {tipo}")

    def cierra(self):
        try: self.ws.close()
        except Exception: pass

def conecta(access, cuenta=None):
    """Conecta, autentica la app y una cuenta. Devuelve (conexión, cuenta, lista de cuentas)."""
    c = CTrader(live=False)
    c.pide(APP_AUTH, {"clientId": CLIENT_ID, "clientSecret": SECRET}, APP_AUTH_R)
    cuentas = c.pide(ACC_LIST, {"accessToken": access}, ACC_LIST_R).get("ctidTraderAccount", [])
    if not cuentas:
        raise RuntimeError("Tu cTrader ID no tiene ninguna cuenta autorizada para esta app")
    elegida = next((a for a in cuentas if str(a["ctidTraderAccountId"]) == str(cuenta)), None) if cuenta else None
    elegida = elegida or next((a for a in cuentas if not a.get("isLive")), cuentas[0])
    if elegida.get("isLive"):
        c.cierra(); c = CTrader(live=True)
        c.pide(APP_AUTH, {"clientId": CLIENT_ID, "clientSecret": SECRET}, APP_AUTH_R)
    c.pide(ACC_AUTH, {"ctidTraderAccountId": elegida["ctidTraderAccountId"], "accessToken": access}, ACC_AUTH_R)
    return c, elegida, cuentas

def simbolos(c, cuenta):
    r = c.pide(SYMBOLS, {"ctidTraderAccountId": cuenta["ctidTraderAccountId"]}, SYMBOLS_R)
    return {s.get("symbolName"): s.get("symbolId") for s in r.get("symbol", []) if s.get("enabled", True)}

def velas(c, cuenta, symbol_id, periodo, desde_ms, hasta_ms):
    """Velas [t_ms, open, high, low, close] entre dos fechas, pidiendo por tramos hacia atrás."""
    sal, hasta = {}, hasta_ms
    while hasta > desde_ms:
        r = c.pide(TRENDBARS, {"ctidTraderAccountId": cuenta["ctidTraderAccountId"], "symbolId": symbol_id,
                               "period": PERIODOS[periodo], "fromTimestamp": desde_ms, "toTimestamp": hasta,
                               "count": 4000}, TRENDBARS_R)
        tb = r.get("trendbar", [])
        if not tb: break
        for b in tb:
            low = b.get("low", 0)
            t = int(b["utcTimestampInMinutes"]) * 60000
            sal[t] = [t, (low + b.get("deltaOpen", 0)) / 1e5, (low + b.get("deltaHigh", 0)) / 1e5,
                      low / 1e5, (low + b.get("deltaClose", 0)) / 1e5]
        primera = min(int(b["utcTimestampInMinutes"]) * 60000 for b in tb)
        if primera >= hasta: break
        hasta = primera - 1
        time.sleep(0.3)   # para no pasar del límite de peticiones
    return [sal[k] for k in sorted(sal)]

if __name__ == "__main__":
    # Prueba: conectar, listar cuentas y descargar EUR/USD H1 de los últimos 3 años
    access, renovado = token()
    print("Token OK", "(renovado)" if renovado else "(guardado)")
    c, cuenta, cuentas = conecta(access)
    print("Cuentas:", [(a["ctidTraderAccountId"], "REAL" if a.get("isLive") else "DEMO", a.get("brokerTitleShort", "")) for a in cuentas])
    print("Uso la cuenta", cuenta["ctidTraderAccountId"], "REAL" if cuenta.get("isLive") else "DEMO", cuenta.get("brokerTitleShort", ""))
    sim = simbolos(c, cuenta)
    print(len(sim), "símbolos. Ejemplos:", sorted(sim)[:40])
    for nombre in ("EURUSD", "XAUUSD"):
        if nombre in sim:
            ahora = int(time.time() * 1000)
            for p, dias in (("H1", 3 * 365), ("M30", 365), ("M5", 90)):
                v = velas(c, cuenta, sim[nombre], p, ahora - dias * 86400000, ahora)
                if v:
                    print(f"{nombre} {p}: {len(v)} velas desde {time.strftime('%d/%m/%Y', time.gmtime(v[0][0]/1000))} · última {v[-1]}")
                else:
                    print(f"{nombre} {p}: sin velas")
    c.cierra()
