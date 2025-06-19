from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from unidecode import unidecode
from rapidfuzz import fuzz
from apscheduler.schedulers.background import BackgroundScheduler
from xml_fetcher import fetch_and_convert_xml
import json, os, re
from typing import List, Optional
from pydantic import BaseModel

# --------------------------------------------------------------------------- #
# 0) HELPERS                                                                  #
# --------------------------------------------------------------------------- #

def normalizar(texto: str) -> str:
    """Remove acentos, deixa minúsculo e tira hífens/espços para facilitar match."""
    return unidecode(texto).lower().replace("-", "").replace(" ", "").strip()

# --------------------------------------------------------------------------- #
# 1) MAPEAMENTOS E LISTAS BASE                                                #
# --------------------------------------------------------------------------- #

MAPEAMENTO_CATEGORIAS = {
    # Hatch
    "gol": "Hatch", "uno": "Hatch", "palio": "Hatch", "celta": "Hatch", "ka": "Hatch",
    "fiesta": "Hatch", "march": "Hatch", "sandero": "Hatch", "onix": "Hatch", "hb20": "Hatch",
    "i30": "Hatch", "golf": "Hatch", "polo": "Hatch", "fox": "Hatch", "up": "Hatch",
    "fit": "Hatch", "city": "Hatch", "yaris": "Hatch", "etios": "Hatch", "clio": "Hatch",
    "corsa": "Hatch", "bravo": "Hatch", "punto": "Hatch", "208": "Hatch", "argo": "Hatch",
    "mobi": "Hatch", "c3": "Hatch", "picanto": "Hatch", "astra hatch": "Hatch", "stilo": "Hatch",
    "focus hatch": "Hatch", "206": "Hatch", "c4 vtr": "Hatch", "kwid": "Hatch", "soul": "Hatch",
    "agile": "Hatch", "sonic hatch": "Hatch", "fusca": "Hatch",

    # Sedan
    "civic": "Sedan", "corolla": "Sedan", "sentra": "Sedan", "versa": "Sedan", "jetta": "Sedan",
    "prisma": "Sedan", "voyage": "Sedan", "siena": "Sedan", "grand siena": "Sedan", "cruze": "Sedan",
    "cobalt": "Sedan", "logan": "Sedan", "fluence": "Sedan", "cerato": "Sedan", "elantra": "Sedan",
    "virtus": "Sedan", "accord": "Sedan", "altima": "Sedan", "fusion": "Sedan", "mazda3": "Sedan",
    "mazda6": "Sedan", "passat": "Sedan", "city sedan": "Sedan", "astra sedan": "Sedan", "vectra sedan": "Sedan",
    "classic": "Sedan", "cronos": "Sedan", "linea": "Sedan", "focus sedan": "Sedan", "ka sedan": "Sedan",
    "408": "Sedan", "c4 pallas": "Sedan", "polo sedan": "Sedan", "bora": "Sedan", "hb20s": "Sedan",
    "lancer": "Sedan", "camry": "Sedan", "onix plus": "Sedan",

    # SUV
    "duster": "SUV", "ecosport": "SUV", "hrv": "SUV", "compass": "SUV", "renegade": "SUV",
    "tracker": "SUV", "kicks": "SUV", "captur": "SUV", "creta": "SUV", "tucson": "SUV",
    "santa fe": "SUV", "sorento": "SUV", "sportage": "SUV", "outlander": "SUV", "asx": "SUV",
    "pajero": "SUV", "tr4": "SUV", "aircross": "SUV", "tiguan": "SUV", "t-cross": "SUV",
    "rav4": "SUV", "cx5": "SUV", "forester": "SUV", "wrv": "SUV", "land cruiser": "SUV",
    "cherokee": "SUV", "grand cherokee": "SUV", "xtrail": "SUV", "murano": "SUV", "cx9": "SUV",
    "edge": "SUV", "trailblazer": "SUV", "pulse": "SUV", "fastback": "SUV", "territory": "SUV",
    "bronco sport": "SUV", "2008": "SUV", "3008": "SUV", "c4 cactus": "SUV", "taos": "SUV",
    "cr-v": "SUV", "corolla cross": "SUV", "sw4": "SUV", "pajero sport": "SUV", "commander": "SUV",
    "xv": "SUV", "xc60": "SUV", "tiggo 5x": "SUV", "haval h6": "SUV", "nivus": "SUV",

    # Caminhonete / Utilitário
    "hilux": "Caminhonete", "ranger": "Caminhonete", "s10": "Caminhonete", "l200": "Caminhonete", "triton": "Caminhonete",
    "toro": "Caminhonete", "frontier": "Caminhonete", "amarok": "Caminhonete", "gladiator": "Caminhonete", "maverick": "Caminhonete", 
    "colorado": "Caminhonete", "dakota": "Caminhonete", "montana (nova)": "Caminhonete", "f-250": "Caminhonete", "courier (pickup)": "Caminhonete", 
    "hoggar": "Caminhonete", "ram 1500": "Caminhonete",
    "saveiro": "Utilitário", "strada": "Utilitário", "montana": "Utilitário", "oroch": "Utilitário",

    # Utilitário
    "kangoo": "Utilitário", "partner": "Utilitário", "doblo": "Utilitário", "fiorino": "Utilitário", "berlingo": "Utilitário",
    "express": "Utilitário", "combo": "Utilitário", "kombi": "Utilitário", "doblo cargo": "Utilitário", "kangoo express": "Utilitário",

    # Furgão
    "master": "Furgão", "sprinter": "Furgão", "ducato": "Furgão", "daily": "Furgão", "jumper": "Furgão",
    "boxer": "Furgão", "trafic": "Furgão", "transit": "Furgão", "vito": "Furgão", "expert (furgão)": "Furgão",
    "jumpy (furgão)": "Furgão", "scudo (furgão)": "Furgão",

    # Coupe
    "camaro": "Coupe", "mustang": "Coupe", "tt": "Coupe", "supra": "Coupe", "370z": "Coupe",
    "rx8": "Coupe", "challenger": "Coupe", "corvette": "Coupe", "veloster": "Coupe", "cerato koup": "Coupe",
    "clk coupe": "Coupe", "a5 coupe": "Coupe", "gt86": "Coupe", "rcz": "Coupe", "brz": "Coupe",

    # Conversível
    "z4": "Conversível", "boxster": "Conversível", "miata": "Conversível", "beetle cabriolet": "Conversível", "slk": "Conversível",
    "911 cabrio": "Conversível", "tt roadster": "Conversível", "a5 cabrio": "Conversível", "mini cabrio": "Conversível", "206 cc": "Conversível",
    "eos": "Conversível",

    # Minivan / Station Wagon
    "spin": "Minivan", "livina": "Minivan", "caravan": "Minivan", "touran": "Minivan", "parati": "Station Wagon",
    "quantum": "Station Wagon", "sharan": "Minivan", "zafira": "Minivan", "picasso": "Minivan", "grand c4": "Minivan",
    "meriva": "Minivan", "scenic": "Minivan", "xsara picasso": "Minivan", "carnival": "Minivan", "idea": "Minivan",
    "spacefox": "Station Wagon", "golf variant": "Station Wagon", "palio weekend": "Station Wagon", "astra sw": "Station Wagon", "206 sw": "Station Wagon",
    "a4 avant": "Station Wagon", "fielder": "Station Wagon",

    # Off‑road
    "wrangler": "Off-road", "troller": "Off-road", "defender": "Off-road", "bronco": "Off-road", "samurai": "Off-road",
    "jimny": "Off-road", "land cruiser": "Off-road", "grand vitara": "Off-road", "jimny sierra": "Off-road", "bandeirante (ate 2001)": "Off-road"
}

MARCAS_CONHECIDAS = [
    "toyota", "honda", "ford", "chevrolet", "volkswagen", "fiat", "nissan", "hyundai",
    "jeep", "renault", "peugeot", "citroën", "mitsubishi", "kia", "mazda", "subaru",
    "suzuki", "audi", "bmw", "mercedes", "volvo", "land rover", "jaguar", "porsche",
    "ferrari", "lamborghini", "bentley", "rolls royce", "maserati", "bugatti",
    "tesla", "lexus", "infiniti", "acura", "cadillac", "lincoln", "buick", "gmc",
    "dodge", "chrysler", "ram", "isuzu", "daihatsu", "great wall", "haval", "byd",
    "chery", "geely", "mg", "jac", "lifan", "foton", "iveco", "scania", "vw"
]

CORES_CONHECIDAS = [
    "branco", "branca", "preto", "preta", "prata", "cinza", "azul", "vermelho", "vermelha",
    "verde", "amarelo", "amarela", "dourado", "dourada", "marrom", "bege", "laranja",
    "rosa", "roxo", "roxa", "violeta", "turquesa", "vinho", "bordô", "bronze",
    "champagne", "grafite", "chumbo", "off-white", "perolado", "perolada", "metalico", "metalica"
]

COMBUSTIVEIS_CONHECIDOS = [
    "flex", "gasolina", "etanol", "alcool", "diesel", "eletrico", "hibrido", "gnv", "gas"
]

TRANSMISSOES_CONHECIDAS = [
    "manual", "automatico", "automatica", "cvt", "semi-automatico", "semi-automatica", "tiptronic"
]

# --------------------------------------------------------------------------- #
# 2) MODELO DE PARAMETROS                                                    #
# --------------------------------------------------------------------------- #

class SearchParams(BaseModel):
    marca: Optional[str] = None
    modelo: Optional[str] = None
    categoria: Optional[str] = None
    cor: Optional[str] = None
    combustivel: Optional[str] = None
    cambio: Optional[str] = None              # campo oficial
    motor: Optional[str] = None
    portas: Optional[int] = None
    preco_max: Optional[float] = None         # teto de preço
    preco_min: Optional[float] = None
    ano_min: Optional[int] = None
    ano_max: Optional[int] = None
    km_max: Optional[float] = None
    opcionais: Optional[str] = None

    # Alias para compatibilidade com antiguidades que usam "transmissao"
    @property
    def transmissao(self) -> Optional[str]:
        return self.cambio

# --------------------------------------------------------------------------- #
# 3) EXTRAÇÃO INTELIGENTE                                                    #
# --------------------------------------------------------------------------- #

def extrair_parametros_inteligente(query: str) -> SearchParams:
    q_lower = query.lower()
    params = SearchParams()

    # ------- preço máximo -------------------------------------------------- #
    padroes_preco = [
        r"(?:ate|até|max|maximo|máximo|teto|limite)?\s*r?\$?\s*([\d,.]+)\s*(?:mil|k|reais?|r\$)?",
        r"pre[cç]o\s*(?:ate|até|max|maximo|máximo)?\s*r?\$?\s*([\d,.]+)",
        r"valor\s*(?:ate|até|max|maximo|máximo)?\s*r?\$?\s*([\d,.]+)"
    ]
    for pad in padroes_preco:
        m = re.search(pad, q_lower)
        if m:
            valor = float(m.group(1).replace(".", "").replace(",", ""))
            if "mil" in q_lower or "k" in q_lower:
                if valor < 1000:
                    valor *= 1000
            params.preco_max = valor
            break

    # ------- ano ----------------------------------------------------------- #
    anos = re.findall(r"\b(20\d{2}|19\d{2})\b", q_lower)
    if anos:
        params.ano_min = int(anos[0])

    # ------- km ------------------------------------------------------------ #
    km_match = re.search(r"(\d+[\.\d]*)\s*(?:mil\s*)?km", q_lower)
    if km_match:
        km_val = float(km_match.group(1).replace(".", ""))
        if "mil" in q_lower and km_val < 1000:
            km_val *= 1000
        params.km_max = km_val

    # ------- cor ----------------------------------------------------------- #
    params.cor = next((c for c in CORES_CONHECIDAS if c in q_lower), None)

    # ------- combustível --------------------------------------------------- #
    params.combustivel = next((c for c in COMBUSTIVEIS_CONHECIDOS if c in q_lower), None)

    # ------- transmissão --------------------------------------------------- #
    params.cambio = next((t for t in TRANSMISSOES_CONHECIDAS if t in q_lower), None)

    # ------- categoria ----------------------------------------------------- #
    for cat in ["hatch", "sedan", "suv", "caminhonete", "utilitario", "utilitário", "furgao", "furgão",
                "coupe", "coupé", "conversivel", "conversível", "minivan", "station wagon", "off-road"]:
        if cat in q_lower:
            mapa = {
                "utilitario": "Utilitário", "utilitário": "Utilitário",
                "furgao": "Furgão", "furgão": "Furgão",
                "coupe": "Coupe", "coupé": "Coupe",
                "conversivel": "Conversível", "conversível": "Conversível"
            }
            params.categoria = mapa.get(cat, cat.upper() if cat == "suv" else cat.title())
            break

    # ------- marca --------------------------------------------------------- #
    for palavra in q_lower.split():
        if palavra.strip(".,;:!?()") in MARCAS_CONHECIDAS:
            params.marca = palavra.title()
            break

    # ------- modelo -------------------------------------------------------- #
    modelos_known = list(MAPEAMENTO_CATEGORIAS.keys())
    for palavra in q_lower.split():
        if palavra in modelos_known:
            params.modelo = palavra
            break

    # ------- opcionais ----------------------------------------------------- #
    opc_keywords = ["ar", "arcondicionado", "direcao", "direção", "eletrica", "elétrica", "vidro",
                    "eletrico", "elétrico", "trava", "alarme", "airbag", "abs", "cd", "mp3", "bluetooth",
                    "gps", "navegador"]
    encontrados = [o for o in opc_keywords if o in q_lower]
    if encontrados:
        params.opcionais = ", ".join(encontrados)

    return params

# --------------------------------------------------------------------------- #
# 4) FUNÇÕES DE APOIO DE PREÇO/ANO                                           #
# --------------------------------------------------------------------------- #

def converter_preco(valor_str):
    try:
        return float(str(valor_str).replace(",", "").replace("R$", "").strip())
    except (ValueError, TypeError):
        return None

def get_price_for_sort(price_val):
    converted = converter_preco(price_val)
    return converted if converted is not None else float("-inf")

def inferir_categoria_por_modelo(modelo_buscado):
    return MAPEAMENTO_CATEGORIAS.get(normalizar(modelo_buscado))

# --------------------------------------------------------------------------- #
# 5) FILTRO PRINCIPAL (SMART)                                                #
# --------------------------------------------------------------------------- #

def filtrar_veiculos_inteligente(vehicles: List[dict], params: SearchParams) -> List[dict]:
    veics = list(vehicles)
    for v in veics:
        v["_relevance"] = 0
        v["_matched"] = 0

    # Marca -----------------------------------------------------------------
    if params.marca:
        temp = []
        busc_norm = normalizar(params.marca)
        for v in veics:
            if fuzz.partial_ratio(normalizar(v.get("marca", "")), busc_norm) >= 80:
                v["_relevance"] += 100
                v["_matched"] += 1
                temp.append(v)
        veics = temp

    # Modelo ----------------------------------------------------------------
    if params.modelo:
        temp = []
        busc_norm = normalizar(params.modelo)
        for v in veics:
            score = max(
                fuzz.partial_ratio(normalizar(v.get("modelo", "")), busc_norm),
                fuzz.partial_ratio(normalizar(v.get("titulo", "")), busc_norm)
            )
            if score >= 75:
                v["_relevance"] += score
                v["_matched"] += 1
                temp.append(v)
        veics = temp

    # Categoria -------------------------------------------------------------
    if params.categoria:
        temp = [v for v in veics if normalizar(v.get("categoria", "")) == normalizar(params.categoria)]
        for v in temp:
            v["_relevance"] += 80
            v["_matched"] += 1
        veics = temp

    # Campos simples --------------------------------------------------------
    for p_val, field in [
        (params.cor, "cor"),
        (params.combustivel, "combustivel"),
        (params.cambio, "cambio")]:
        if p_val:
            norm = normalizar(p_val)
            for v in veics:
                if fuzz.partial_ratio(normalizar(v.get(field, "")), norm) >= 80:
                    v["_relevance"] += 50
                    v["_matched"] += 1

    # Preço -----------------------------------------------------------------
    if params.preco_max:
        veics = [v for v in veics if (p := converter_preco(v.get("preco"))) is not None and p <= params.preco_max * 1.3]

    # Ano -------------------------------------------------------------------
    if params.ano_min:
        veics = [v for v in veics if int(v.get("ano", 0)) >= params.ano_min]
    if params.ano_max:
        veics = [v for v in veics if int(v.get("ano", 0)) <= params.ano_max]

    # KM --------------------------------------------------------------------
    if params.km_max:
        veics = [v for v in veics if float(str(v.get("km", "0")).replace(",", "").replace(".", "")) <= params.km_max]

    # Ordena -----------------------------------------------------------------
    veics.sort(key=lambda v: (v["_matched"], v["_relevance"], get_price_for_sort(v.get("preco"))), reverse=True)
    for v in veics:
        v.pop("_matched", None)
        v.pop("_relevance", None)
    return veics

# --------------------------------------------------------------------------- #
# 6) LEGACY FILTRO (SEM ALTERAÇÃO)                                           #
# --------------------------------------------------------------------------- #

def filtrar_veiculos(vehicles, filtros, valormax=None):
    campos_fuzzy = ["modelo", "titulo"]
    veics = list(vehicles)
    for v in veics:
        v["_relevance"] = 0
        v["_matched"] = 0

    active_fuzzy = False
    for chave, valor in filtros.items():
        if not valor:
            continue
        passou = []
        if chave in campos_fuzzy:
            active_fuzzy = True
            palavras = [normalizar(p) for p in valor.split() if p]
            for v in veics:
                score_sum = 0
                matched = 0
                for p in palavras:
                    best = max(
                        fuzz.partial_ratio(normalizar(v.get("modelo", "")), p),
                        fuzz.partial_ratio(normalizar(v.get("titulo", "")), p)
                    )
                    if best >= 75:
                        score_sum += best
                        matched += 1
                if matched:
                    v["_relevance"] += score_sum
                    v["_matched"] += matched
                    passou.append(v)
        else:
            termo = normalizar(valor)
            for v in veics:
                if normalizar(str(v.get(chave, ""))) == termo:
                    passou.append(v)
        veics = passou
        if not veics:
            break

    if active_fuzzy:
        veics.sort(key=lambda v: (v["_matched"], v["_relevance"], get_price_for_sort(v.get("preco"))), reverse=True)
    else:
        veics.sort(key=lambda v: get_price_for_sort(v.get("preco")), reverse=True)

    if valormax:
        try:
            teto = float(valormax)
            veics = [v for v in veics if (p := converter_preco(v.get("preco"))) is not None and p <= teto * 1.3]
        except ValueError:
            return []

    for v in veics:
        v.pop("_matched", None)
        v.pop("_relevance", None)
    return veics

# --------------------------------------------------------------------------- #
# 7) FASTAPI APP                                                             #
# --------------------------------------------------------------------------- #

app = FastAPI()

@app.on_event("startup")
def agendar_tarefas():
    scheduler = BackgroundScheduler(timezone="America/Sao_Paulo")
    scheduler.add_job(fetch_and_convert_xml, "cron", hour="0,12")
    scheduler.start()
    fetch_and_convert_xml()

@app.post("/api/search-smart")
def search_smart(request_data: dict):
    query = request_data.get("query", "")
    if not query:
        return JSONResponse({"error": "Query não informada", "resultados": [], "total_encontrado": 0}, status_code=400)

    if not os.path.exists("data.json"):
        return JSONResponse({"error": "Nenhum dado disponível", "resultados": [], "total_encontrado": 0}, status_code=404)

    try:
        with open("data.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        vehicles = data["veiculos"]
    except Exception:
        return JSONResponse({"error": "Erro ao ler os dados", "resultados": [], "total_encontrado": 0}, status_code=500)

    params = extrair_parametros_inteligente(query)
    resultados = filtrar_veiculos_inteligente(vehicles, params)

    response_data = {
        "query_original": query,
        "parametros_extraidos": params.dict(exclude_none=True),
        "resultados": resultados[:50],
        "total_encontrado": len(resultados)
    }

    if not resultados and params.categoria:
        params_ampla = SearchParams(categoria=params.categoria, preco_max=params.preco_max)
        alternativos = filtrar_veiculos_inteligente(vehicles, params_ampla)
        if alternativos:
            response_data["resultados_alternativos"] = alternativos[:10]
            response_data["total_alternativos"] = len(alternativos)
            response_data["sugestao"] = f"Não encontramos veículos exatos, mas temos {len(alternativos)} opções na categoria {params.categoria}"

    return JSONResponse(response_data)

@app.get("/api/data")
def get_data(request: Request):
    if not os.path.exists("data.json"):
        return JSONResponse({"error": "Nenhum dado disponível", "resultados": [], "total_encontrado": 0}, status_code=404)
    try:
        with open("data.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        vehicles = data["veiculos"]
    except Exception:
        return JSONResponse({"error": "Erro ao ler os dados", "resultados": [], "total_encontrado": 0}, status_code=500)

    query_params = dict(request.query_params)
    valormax = query_params.pop("ValorMax", None)
    filtros = {k: query_params.get(k) for k in ["modelo", "marca", "categoria"] if query_params.get(k)}
    resultado = filtrar_veiculos(vehicles, filtros, valormax)

    if resultado:
        return JSONResponse({"resultados": resultado, "total_encontrado": len(resultado)})

    # Fallbacks mantidos do legado (sem alterações)
    alternativas = []
    if filtros.get("modelo"):
        alt = filtrar_veiculos(vehicles, {"modelo": filtros["modelo"]}, valormax)
        if alt:
            alternativas = alt
        else:
            cat = inferir_categoria_por_modelo(filtros["modelo"])
            if cat:
                alternativas = filtrar_veiculos(vehicles, {"categoria": cat}, valormax) or filtrar_veiculos(vehicles, {"categoria": cat})

    if alternativas:
        alt_format = [{"titulo": v.get("titulo", ""), "preco": v.get("preco", "") } for v in alternativas[:10]]
        return JSONResponse({
            "resultados": [],
            "total_encontrado": 0,
            "instrucao_ia": "Não encontramos veículos com os parâmetros informados dentro do valor desejado. Seguem as opções mais próximas.",
            "alternativa": {"resultados": alt_format, "total_encontrado": len(alt_format)}
        })

    return JSONResponse({"resultados": [], "total_encontrado": 0, "instrucao_ia": "Não encontramos veículos com os parâmetros informados."})
