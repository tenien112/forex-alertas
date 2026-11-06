# BUSCAR VALOR, paso 1 (rápido): solo busca qué valores cumplen lo escrito y deja la lista en lista.json
# para que la app te deje elegir. No descarga velas (eso lo hace buscar.py con el que elijas).
# No necesita instalar nada: solo Python estándar.
import sys, json, time, urllib.request, urllib.parse
from catalogo import en_catalogo, divisa, TIPOS, rango

def yahoo(q):
    url = "https://query2.finance.yahoo.com/v1/finance/search?" + urllib.parse.urlencode(
        {"q": q, "quotesCount": 15, "newsCount": 0, "listsCount": 0, "enableFuzzyQuery": "false"})
    for intento in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            with urllib.request.urlopen(req, timeout=15) as r:
                d = json.load(r)
            sal = []
            for x in d.get("quotes", []):
                t = x.get("symbol")
                if not t or x.get("quoteType") in ("OPTION",): continue
                ti = TIPOS.get(x.get("quoteType", ""), x.get("quoteType", ""))
                sal.append({"ticker": t, "nombre": x.get("longname") or x.get("shortname") or t, "tipo": ti,
                            "bolsa": x.get("exchDisp") or x.get("exchange") or ""})
            return sal
        except Exception as ex:
            print("Yahoo falló:", ex); time.sleep(3)
    return []

def main():
    q = sys.argv[1] if len(sys.argv) > 1 else ""
    ident = sys.argv[2] if len(sys.argv) > 2 else ""
    lista, vistos = [], set()
    def mete(t, n, ti, b):
        if t in vistos: return
        vistos.add(t); lista.append({"ticker": t, "nombre": n, "tipo": ti, "bolsa": b})
    d = divisa(q)
    if d: mete(*d)
    for n, t, ti, b, _ in en_catalogo(q): mete(t, n, ti, b)
    ys = yahoo(q)
    ys.sort(key=lambda x: rango(x["bolsa"], x["ticker"], x["tipo"]))
    for x in ys: mete(x["ticker"], x["nombre"], x["tipo"], x["bolsa"])
    res = {"id": ident, "q": q, "hora": int(time.time()), "lista": lista[:20]}
    with open("lista.json", "w") as f:
        json.dump(res, f, ensure_ascii=False, separators=(",", ":"))
    print(len(lista), "valores:", [x["ticker"] for x in lista[:20]])

if __name__ == "__main__":
    main()
