# Catálogo de valores conocidos para BUSCAR VALOR (app BOLSA-LORENCITO).
# Cada entrada: (nombre que se muestra, ticker de Yahoo, tipo, bolsa, otros nombres con los que se puede buscar)
# Lo usan buscar.py y lista.py, y se copia como catalogo.json a la app para dar opciones al instante.
import unicodedata

C = [
    # --- Materias primas ---
    ("Oro", "GC=F", "Materia prima", "", ["GOLD", "XAUUSD", "XAU"]),
    ("Plata", "SI=F", "Materia prima", "", ["SILVER", "XAGUSD", "XAG"]),
    ("Platino", "PL=F", "Materia prima", "", ["PLATINUM"]),
    ("Paladio", "PA=F", "Materia prima", "", ["PALLADIUM"]),
    ("Petróleo WTI", "CL=F", "Materia prima", "", ["PETROLEO", "WTI", "CRUDO", "OIL", "USOIL"]),
    ("Petróleo Brent", "BZ=F", "Materia prima", "", ["BRENT", "UKOIL"]),
    ("Gas natural", "NG=F", "Materia prima", "", ["NATURAL GAS", "GAS"]),
    ("Cobre", "HG=F", "Materia prima", "", ["COPPER"]),
    # --- Cripto ---
    ("Bitcoin", "BTC-USD", "Cripto", "", ["BTC", "BTCUSD"]),
    ("Ethereum", "ETH-USD", "Cripto", "", ["ETH", "ETHUSD", "ETHER"]),
    ("Solana", "SOL-USD", "Cripto", "", ["SOL"]),
    ("XRP (Ripple)", "XRP-USD", "Cripto", "", ["RIPPLE"]),
    ("Cardano", "ADA-USD", "Cripto", "", ["ADA"]),
    ("Dogecoin", "DOGE-USD", "Cripto", "", ["DOGE"]),
    # --- Índices ---
    ("IBEX 35", "^IBEX", "Índice", "Madrid", ["IBEX", "IBEX35"]),
    ("S&P 500", "^GSPC", "Índice", "EE. UU.", ["SP500", "S&P500", "SP 500", "SPX", "US500"]),
    ("Nasdaq 100", "^NDX", "Índice", "EE. UU.", ["NASDAQ", "NDX", "US100", "USTEC"]),
    ("Dow Jones", "^DJI", "Índice", "EE. UU.", ["DOW", "US30", "DJI"]),
    ("DAX", "^GDAXI", "Índice", "Alemania", ["DAX 40", "DE40", "GER40"]),
    ("CAC 40", "^FCHI", "Índice", "Francia", ["CAC", "FRA40"]),
    ("Euro Stoxx 50", "^STOXX50E", "Índice", "Europa", ["EUROSTOXX", "EU50", "STOXX"]),
    ("FTSE 100", "^FTSE", "Índice", "Reino Unido", ["FTSE", "UK100"]),
    ("Nikkei 225", "^N225", "Índice", "Japón", ["NIKKEI", "JP225"]),
    ("VIX (volatilidad)", "^VIX", "Índice", "EE. UU.", ["VIX"]),
    # --- IBEX 35 y mercado continuo (Madrid) ---
    ("Acciona", "ANA.MC", "Acción", "Madrid", []),
    ("Acciona Energía", "ANE.MC", "Acción", "Madrid", []),
    ("Acerinox", "ACX.MC", "Acción", "Madrid", []),
    ("ACS", "ACS.MC", "Acción", "Madrid", []),
    ("Aena", "AENA.MC", "Acción", "Madrid", []),
    ("Amadeus", "AMS.MC", "Acción", "Madrid", []),
    ("ArcelorMittal", "MTS.MC", "Acción", "Madrid", []),
    ("Banco Sabadell", "SAB.MC", "Acción", "Madrid", ["SABADELL"]),
    ("Banco Santander", "SAN.MC", "Acción", "Madrid", ["SANTANDER"]),
    ("Bankinter", "BKT.MC", "Acción", "Madrid", []),
    ("BBVA", "BBVA.MC", "Acción", "Madrid", ["BANCO BILBAO"]),
    ("CaixaBank", "CABK.MC", "Acción", "Madrid", ["CAIXA", "LA CAIXA"]),
    ("Cellnex", "CLNX.MC", "Acción", "Madrid", []),
    ("Enagás", "ENG.MC", "Acción", "Madrid", ["ENAGAS"]),
    ("Endesa", "ELE.MC", "Acción", "Madrid", []),
    ("Ferrovial", "FER.MC", "Acción", "Madrid", []),
    ("Fluidra", "FDR.MC", "Acción", "Madrid", []),
    ("Grifols", "GRF.MC", "Acción", "Madrid", []),
    ("IAG (Iberia, British Airways)", "IAG.MC", "Acción", "Madrid", ["IBERIA"]),
    ("Iberdrola", "IBE.MC", "Acción", "Madrid", []),
    ("Inditex (Zara)", "ITX.MC", "Acción", "Madrid", ["INDITEX", "ZARA"]),
    ("Indra", "IDR.MC", "Acción", "Madrid", []),
    ("Inmobiliaria Colonial", "COL.MC", "Acción", "Madrid", ["COLONIAL"]),
    ("Logista", "LOG.MC", "Acción", "Madrid", []),
    ("Mapfre", "MAP.MC", "Acción", "Madrid", []),
    ("Meliá Hotels", "MEL.MC", "Acción", "Madrid", ["MELIA"]),
    ("Merlin Properties", "MRL.MC", "Acción", "Madrid", ["MERLIN"]),
    ("Naturgy", "NTGY.MC", "Acción", "Madrid", []),
    ("Puig", "PUIG.MC", "Acción", "Madrid", []),
    ("Redeia (Red Eléctrica)", "RED.MC", "Acción", "Madrid", ["REDEIA", "RED ELECTRICA"]),
    ("Repsol", "REP.MC", "Acción", "Madrid", []),
    ("Rovi", "ROVI.MC", "Acción", "Madrid", []),
    ("Sacyr", "SCYR.MC", "Acción", "Madrid", []),
    ("Solaria", "SLR.MC", "Acción", "Madrid", []),
    ("Telefónica", "TEF.MC", "Acción", "Madrid", ["TELEFONICA", "MOVISTAR"]),
    ("Unicaja", "UNI.MC", "Acción", "Madrid", []),
    ("DIA (Supermercados DIA)", "DIA.MC", "Acción", "Madrid", ["DIA", "SUPERMERCADOS DIA", "DISTRIBUIDORA INTERNACIONAL"]),
    ("Atresmedia (Antena 3)", "A3M.MC", "Acción", "Madrid", ["ATRESMEDIA", "ANTENA 3"]),
    ("Mediaset España (Telecinco)", "TL5.MC", "Acción", "Madrid", ["MEDIASET", "TELECINCO"]),
    ("Ebro Foods", "EBRO.MC", "Acción", "Madrid", ["EBRO"]),
    ("Viscofan", "VIS.MC", "Acción", "Madrid", []),
    ("Pharma Mar", "PHM.MC", "Acción", "Madrid", ["PHARMAMAR"]),
    ("Almirall", "ALM.MC", "Acción", "Madrid", []),
    ("Faes Farma", "FAE.MC", "Acción", "Madrid", ["FAES"]),
    ("CAF (Construcciones y Auxiliar de Ferrocarriles)", "CAF.MC", "Acción", "Madrid", ["CAF"]),
    ("Talgo", "TLGO.MC", "Acción", "Madrid", []),
    ("CIE Automotive", "CIE.MC", "Acción", "Madrid", ["CIE"]),
    ("Gestamp", "GEST.MC", "Acción", "Madrid", []),
    ("Técnicas Reunidas", "TRE.MC", "Acción", "Madrid", ["TECNICAS REUNIDAS"]),
    ("OHLA", "OHLA.MC", "Acción", "Madrid", ["OHL"]),
    ("Prosegur", "PSG.MC", "Acción", "Madrid", []),
    ("Ence", "ENC.MC", "Acción", "Madrid", []),
    ("Ercros", "ECR.MC", "Acción", "Madrid", []),
    ("Tubacex", "TUB.MC", "Acción", "Madrid", []),
    ("Applus", "APPS.MC", "Acción", "Madrid", []),
    ("NH Hotel Group", "NHH.MC", "Acción", "Madrid", ["NH HOTELES", "NH"]),
    ("Línea Directa", "LDA.MC", "Acción", "Madrid", ["LINEA DIRECTA"]),
    ("Grenergy", "GRE.MC", "Acción", "Madrid", []),
    ("Audax Renovables", "ADX.MC", "Acción", "Madrid", ["AUDAX"]),
    ("Neinor Homes", "HOME.MC", "Acción", "Madrid", ["NEINOR"]),
    ("Metrovacesa", "MVC.MC", "Acción", "Madrid", []),
    ("Vidrala", "VID.MC", "Acción", "Madrid", []),
    # --- Grandes de EE. UU. ---
    ("Apple", "AAPL", "Acción", "NASDAQ", ["AAPL"]),
    ("Microsoft", "MSFT", "Acción", "NASDAQ", ["MSFT"]),
    ("NVIDIA", "NVDA", "Acción", "NASDAQ", ["NVDA"]),
    ("Amazon", "AMZN", "Acción", "NASDAQ", ["AMZN"]),
    ("Alphabet (Google)", "GOOGL", "Acción", "NASDAQ", ["GOOGLE", "GOOGL"]),
    ("Meta (Facebook)", "META", "Acción", "NASDAQ", ["FACEBOOK"]),
    ("Tesla", "TSLA", "Acción", "NASDAQ", ["TSLA"]),
    ("Netflix", "NFLX", "Acción", "NASDAQ", ["NFLX"]),
    ("AMD", "AMD", "Acción", "NASDAQ", []),
    ("Intel", "INTC", "Acción", "NASDAQ", ["INTC"]),
    ("Coca-Cola", "KO", "Acción", "NYSE", ["COCA COLA"]),
    ("McDonald's", "MCD", "Acción", "NYSE", ["MCDONALDS"]),
    ("Boeing", "BA", "Acción", "NYSE", []),
    ("JPMorgan", "JPM", "Acción", "NYSE", ["JP MORGAN"]),
    ("Berkshire Hathaway", "BRK-B", "Acción", "NYSE", ["BERKSHIRE"]),
    ("Visa", "V", "Acción", "NYSE", []),
    ("Walmart", "WMT", "Acción", "NYSE", []),
    ("Disney", "DIS", "Acción", "NYSE", []),
    ("Exxon Mobil", "XOM", "Acción", "NYSE", ["EXXON"]),
    ("Pfizer", "PFE", "Acción", "NYSE", []),
]
DIVISAS = "EUR USD GBP JPY CHF CAD AUD NZD CNH CNY MXN SEK NOK DKK PLN TRY ZAR HKD SGD".split()
TIPOS = {"EQUITY": "Acción", "ETF": "ETF", "INDEX": "Índice", "CURRENCY": "Divisa", "CRYPTOCURRENCY": "Cripto",
         "FUTURE": "Futuro", "MUTUALFUND": "Fondo"}

def sin_acentos(t):
    return "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")

def norm(t):
    return " ".join(sin_acentos(t).upper().replace("-", " ").replace("/", " ").split())

def palabras(e):
    """Textos con los que se puede encontrar una entrada del catálogo."""
    n, t, ti, b, al = e
    return [norm(n), norm(t.replace(".MC", "").replace("^", "").replace("=F", "").replace("-USD", ""))] + [norm(a) for a in al]

def en_catalogo(q):
    """Entradas cuyo nombre, ticker u otro nombre empieza por lo buscado (o lo contiene como palabra)."""
    u = norm(q)
    if not u: return []
    exactos, empiezan, contienen, vistos = [], [], [], set()
    for e in C:
        if e[1] in vistos: continue
        ps = palabras(e)
        if any(p == u for p in ps): exactos.append(e)
        elif any(p.startswith(u) for p in ps): empiezan.append(e)
        elif any((" " + u) in (" " + p) for p in ps): contienen.append(e)
        else: continue
        vistos.add(e[1])
    return exactos + empiezan + contienen

def divisa(q):
    import re
    u = norm(q).replace(" ", "")
    m = re.fullmatch(r"([A-Z]{3})([A-Z]{3})", u)
    if m and m.group(1) in DIVISAS and m.group(2) in DIVISAS:
        a, b = m.groups()
        return ("CNH=X" if (a, b) == ("USD", "CNH") else f"{a}{b}=X", f"{a}/{b}", "Divisa", "")
    return None

PREF = ["Madrid", "NASDAQ", "NYSE", "NYSEArca", "NYSE American", "XETRA", "Paris", "Amsterdam", "London", "Milan"]
def rango(bolsa, ticker, tipo):
    if tipo == "Futuro" or ticker.endswith("=F"): return 50
    for i, p in enumerate(PREF):
        if (bolsa or "").startswith(p): return i
    return 20
