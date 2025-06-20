# main.py
import json
import logging
import os
from typing import List, Dict, Optional

import spacy
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from rapidfuzz import fuzz
from spacy.matcher import Matcher, PhraseMatcher
from unidecode import unidecode
from apscheduler.schedulers.background import BackgroundScheduler

# Assumimos que este arquivo existe e contém a função fetch_and_convert_xml
from xml_fetcher import fetch_and_convert_xml

# --- CONFIGURAÇÃO BÁSICA ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
app = FastAPI(
    title="API de Busca Inteligente de Veículos",
    description="Busca em um inventário local atualizado por um feed XML, usando PLN com SpaCy."
)

# --- VARIÁVEIS GLOBAIS E CONSTANTES ---
VOCABULARY_FILE = "fipe_vocabulary.json"
INVENTORY_FILE = "dados.json"
SPACY_MATCHERS = {}
VEHICLE_INVENTORY = []
MAPEAMENTO_CATEGORIAS = {
    "gol": "Hatch", "uno": "Hatch", "palio": "Hatch", "celta": "Hatch", "ka": "Hatch",
    "fiesta": "Hatch", "march": "Hatch", "sandero": "Hatch", "onix": "Hatch", "hb20": "Hatch",
    "i30": "Hatch", "golf": "Hatch", "polo": "Hatch", "fox": "Hatch", "up": "Hatch",
    "fit": "Hatch", "city": "Hatch", "yaris": "Hatch", "etios": "Hatch", "clio": "Hatch",
    "corsa": "Hatch", "bravo": "Hatch", "punto": "Hatch", "208": "Hatch", "argo": "Hatch",
    "mobi": "Hatch", "c3": "Hatch", "picanto": "Hatch", "astra hatch": "Hatch", "stilo": "Hatch",
    "focus hatch": "Hatch", "206": "Hatch", "c4 vtr": "Hatch", "kwid": "Hatch", "soul": "Hatch",
    "agile": "Hatch", "sonic hatch": "Hatch", "fusca": "Hatch",
    "civic": "Sedan", "corolla": "Sedan", "sentra": "Sedan", "versa": "Sedan", "jetta": "Sedan",
    "prisma": "Sedan", "voyage": "Sedan", "siena": "Sedan", "grand siena": "Sedan", "cruze": "Sedan",
    "cobalt": "Sedan", "logan": "Sedan", "fluence": "Sedan", "cerato": "Sedan", "elantra": "Sedan",
    "virtus": "Sedan", "accord": "Sedan", "altima": "Sedan", "fusion": "Sedan", "mazda3": "Sedan",
    "mazda6": "Sedan", "passat": "Sedan", "city sedan": "Sedan", "astra sedan": "Sedan", "vectra sedan": "Sedan",
    "classic": "Sedan", "cronos": "Sedan", "linea": "Sedan", "focus sedan": "Sedan", "ka sedan": "Sedan",
    "408": "Sedan", "c4 pallas": "Sedan", "polo sedan": "Sedan", "bora": "Sedan", "hb20s": "Sedan",
    "lancer": "Sedan", "camry": "Sedan", "onix plus": "Sedan",
    "duster": "SUV", "ecosport": "SUV", "hrv": "SUV", "compass": "SUV", "renegade": "SUV",
    "tracker": "SUV", "kicks": "SUV", "captur": "SUV", "creta": "SUV", "tucson": "SUV",
    "santa fe": "SUV", "sorento": "SUV", "sportage": "SUV", "outlander": "SUV", "asx": "SUV",
    "pajero": "SUV", "tr4": "SUV", "aircross": "SUV", "tiguan": "SUV", "t-cross": "SUV",
    "rav4": "SUV", "cx5": "SUV", "forester": "SUV", "wrv": "SUV", "land cruiser": "SUV", 
    "cherokee": "SUV", "grand cherokee": "SUV", "xtrail": "SUV", "murano": "SUV", "cx9": "SUV",
    "edge": "SUV", "trailblazer": "SUV", "pulse": "SUV", "fastback": "SUV", "territory": "SUV",
    "bronco sport": "SUV", "2008": "SUV", "3008": "SUV", "c4 cactus": "SUV", "taos": "SUV",
    "cr-v": "SUV", "corolla cross": "SUV", "sw4": "SUV", "pajero sport": "SUV", "commander": "SUV",
    "xv": "SUV", "xc60": "SUV", "tiggo 5x": "SUV", "haval h6": "SUV", "nivus": "SUV"
}

# --- MODELOS PYDANTIC ---
class SearchParams(BaseModel):
    marcas: Optional[List[str]] = None; modelos: Optional[List[str]] = None; versoes: Optional[List[str]] = None
    categorias: Optional[List[str]] = None; cores: Optional[List[str]] = None; combustiveis: Optional[List[str]] = None
    cambios: Optional[List[str]] = None; motores: Optional[List[str]] = None; opcionais: Optional[List[str]] = None
    valor_max: Optional[float]] = None; valor_min: Optional[float]] = None; ano_max: Optional[int] = None
    ano_min: Optional[int] = None; ano_fabricacao_max: Optional[int] = None; ano_fabricacao_min: Optional[int] = None
    km_max: Optional[int] = None; portas: Optional[int] = None

# --- FUNÇÕES DE LÓGICA ---

def normalizar(texto: str) -> str:
    return unidecode(str(texto)).lower().strip()

def extrair_parametros_com_spacy(query: str) -> SearchParams:
    nlp = SPACY_MATCHERS.get("nlp")
    if not nlp: return SearchParams()
    doc = nlp(query.lower())
    params = SearchParams(marcas=[], modelos=[], versoes=[], categorias=[], cores=[], combustiveis=[], cambios=[], motores=[], opcionais=[])
    
    param_field_map = {"MARCA": params.marcas, "MODELO": params.modelos, "VERSAO": params.versoes}
    if "phrase_matcher" in SPACY_MATCHERS:
        for match_id, start, end in SPACY_MATCHERS["phrase_matcher"](doc):
            entity_label, entity_text = nlp.vocab.strings[match_id], doc[start:end].text
            if entity_label in param_field_map and entity_text not in param_field_map[entity_label]:
                param_field_map[entity_label].append(entity_text)
    
    if not params.categorias and params.modelos:
        for modelo in params.modelos:
            categoria = MAPEAMENTO_CATEGORIAS.get(normalizar(modelo))
            if categoria and categoria not in params.categorias: params.categorias.append(categoria)

    if "matcher" in SPACY_MATCHERS:
        for match_id, start, end in SPACY_MATCHERS["matcher"](doc):
            rule_id, span = nlp.vocab.strings[match_id], doc[start:end]
            num_token = next((token for token in span if token.like_num), None)
            if not num_token: continue
            valor_str = num_token.text.replace('.', '').replace(',', '')
            valor = int(valor_str) if valor_str.isdigit() else 0
            is_price = any(t.lower_ in ["mil", "k", "reais"] for t in span) or valor > 5000
            if rule_id.startswith("PRECO") and is_price:
                if "mil" in span.text or "k" in span.text: valor *= 1000
                if rule_id == "PRECO_MAX": params.valor_max = float(valor)
                if rule_id == "PRECO_MIN": params.valor_min = float(valor)
            elif rule_id == "ANO_MODELO" and 1950 < valor < 2050:
                if params.ano_min is None: params.ano_min = valor
                else: params.ano_max = valor
            elif rule_id == "ANO_FABRICACAO" and 1950 < valor < 2050:
                if params.ano_fabricacao_min is None: params.ano_fabricacao_min = valor
                else: params.ano_fabricacao_max = valor
            elif rule_id == "KM_MAX":
                if "mil" in span.text or "k" in span.text: valor *= 1000
                params.km_max = valor
            elif rule_id == "PORTAS": params.portas = valor
    
    for p in ["ano", "ano_fabricacao"]:
        min_attr, max_attr, min_val, max_val = f"{p}_min", f"{p}_max", getattr(params, f"{p}_min"), getattr(params, f"{p}_max")
        if min_val and max_val and min_val > max_val: setattr(params, min_attr, max_val), setattr(params, max_attr, min_val)
        if min_val and not max_val: setattr(params, max_attr, min_val)
    return params

def filtrar_veiculos_inteligente(vehicles: List[Dict], params: SearchParams) -> List[Dict]:
    filtered = list(vehicles)
    text_filters = {"marcas": "marca", "modelos": "modelo", "versoes": "titulo", "categorias": "categoria", "cores": "cor", "combustiveis": "combustivel", "cambios": "cambio", "motores": "titulo"}
    for param_name, field_name in text_filters.items():
        if p_vals := getattr(params, param_name):
            filtered = [v for v in filtered if (val := v.get(field_name)) and any(fuzz.partial_ratio(normalizar(p_val), normalizar(val)) >= 85 for p_val in p_vals)]
    if params.opcionais:
        filtered = [v for v in filtered if (opts := v.get("opcionais")) and isinstance(opts, list) and all(any(fuzz.partial_ratio(normalizar(req_opt), normalizar(v_opt)) >= 90 for v_opt in opts) for req_opt in params.opcionais)]
    def to_float(p): return float(str(p).replace(",", "").strip("R$ ")) if p else None
    if params.valor_max: filtered = [v for v in filtered if (p := to_float(v.get("preco"))) and p <= params.valor_max]
    if params.valor_min: filtered = [v for v in filtered if (p := to_float(v.get("preco"))) and p >= params.valor_min]
    if params.ano_max: filtered = [v for v in filtered if (a := v.get("ano")) and int(a) <= params.ano_max]
    if params.ano_min: filtered = [v for v in filtered if (a := v.get("ano")) and int(a) >= params.ano_min]
    if params.ano_fabricacao_max: filtered = [v for v in filtered if (a := v.get("ano_fabricacao")) and int(a) <= params.ano_fabricacao_max]
    if params.ano_fabricacao_min: filtered = [v for v in filtered if (a := v.get("ano_fabricacao")) and int(a) >= params.ano_fabricacao_min]
    if params.km_max: filtered = [v for v in filtered if (k := v.get("km")) and int(k) <= params.km_max]
    if params.portas: filtered = [v for v in filtered if (p := v.get("portas")) and int(p) == params.portas]
    filtered.sort(key=lambda v: to_float(v.get("preco")) or 0, reverse=True)
    return filtered

def load_inventory_from_file():
    global VEHICLE_INVENTORY
    if os.path.exists(INVENTORY_FILE):
        logging.info(f"Carregando/recarregando inventário de '{INVENTORY_FILE}'...")
        try:
            with open(INVENTORY_FILE, "r", encoding="utf-8") as f: VEHICLE_INVENTORY = json.load(f).get("veiculos", [])
            logging.info(f"{len(VEHICLE_INVENTORY)} veículos carregados na memória.")
        except (json.JSONDecodeError, AttributeError) as e:
            logging.error(f"Erro ao ler o arquivo JSON do inventário: {e}")
            VEHICLE_INVENTORY = []
    else:
        logging.warning(f"Arquivo de inventário '{INVENTORY_FILE}' não encontrado.")
        VEHICLE_INVENTORY = []

def update_and_reload_inventory():
    logging.info("Tarefa agendada: iniciando atualização do inventário.")
    try:
        fetch_and_convert_xml()
        load_inventory_from_file()
        logging.info("Tarefa agendada: atualização do inventário concluída.")
    except Exception as e:
        logging.error(f"Falha na tarefa agendada de atualização: {e}")

# --- EVENTO DE STARTUP DA API ---
@app.on_event("startup")
def startup_event():
    try:
        nlp = spacy.load("pt_core_news_lg")
        SPACY_MATCHERS["nlp"] = nlp
        if os.path.exists(VOCABULARY_FILE):
            logging.info(f"Carregando vocabulário de '{VOCABULARY_FILE}'...")
            with open(VOCABULARY_FILE, "r", encoding="utf-8") as f: fipe_vocabulary = json.load(f)
            phrase_matcher = PhraseMatcher(nlp.vocab, attr="LOWER")
            entity_map = { "MARCA": fipe_vocabulary.get("marcas", []), "MODELO": fipe_vocabulary.get("modelos", []), "VERSAO": fipe_vocabulary.get("versoes", []) }
            for label, terms in entity_map.items():
                if terms: phrase_matcher.add(label, [nlp.make_doc(term) for term in terms])
            SPACY_MATCHERS["phrase_matcher"] = phrase_matcher
            logging.info("PhraseMatcher do SpaCy configurado.")
        else: logging.warning(f"Arquivo de vocabulário '{VOCABULARY_FILE}' não encontrado.")
        matcher = Matcher(nlp.vocab)
        matcher.add("PRECO_MAX", [[{"LOWER": {"IN": ["ate", "maximo", "max", "teto", "abaixo de"]}}, {"IS_SPACE": True, "OP": "?"}, {"LIKE_NUM": True}]])
        matcher.add("PRECO_MIN", [[{"LOWER": {"IN": ["a partir de", "acima de", "minimo"]}}, {"IS_SPACE": True, "OP": "?"}, {"LIKE_NUM": True}]])
        matcher.add("ANO_MODELO", [[{"LOWER": {"IN": ["ano", "modelo"]}}, {"IS_DIGIT": True, "SHAPE": "dddd"}]])
        matcher.add("ANO_FABRICACAO", [[{"LOWER": {"IN": ["fabricado", "fabricacao"]}}, {"LOWER": {"IN": ["em", "de"]}, "OP": "?"}, {"IS_DIGIT": True, "SHAPE": "dddd"}]])
        matcher.add("KM_MAX", [[{"LOWER": {"IN": ["ate", "com", "maximo"]}}, {"LIKE_NUM": True}, {"LOWER": {"IN": ["km", "mil km"]}}]])
        matcher.add("PORTAS", [[{"LIKE_NUM": True}, {"LOWER": {"IN": ["p", "portas"]}}]])
        SPACY_MATCHERS["matcher"] = matcher
    except OSError: logging.error("Modelo 'pt_core_news_lg' não encontrado. Execute 'python -m spacy download pt_core_news_lg'")
    
    logging.info("Executando a busca inicial de dados do inventário...")
    update_and_reload_inventory()

    logging.info("Agendando tarefas de atualização em background...")
    scheduler = BackgroundScheduler(timezone="America/Sao_Paulo")
    scheduler.add_job(update_and_reload_inventory, "cron", hour="0,12", minute=5)
    scheduler.start()
    logging.info("Aplicação iniciada e pronta.")

# --- ENDPOINT DA API ---
@app.post("/api/search")
async def search_smart(request: Request):
    if not VEHICLE_INVENTORY:
        return JSONResponse(content={"error": "O inventário de veículos não está carregado ou está vazio."}, status_code=503)
    request_data = await request.json()
    query = request_data.get("query")
    if not query: return JSONResponse(content={"error": "Query não informada"}, status_code=400)
    params = extrair_parametros_com_spacy(query)
    resultados = filtrar_veiculos_inteligente(VEHICLE_INVENTORY, params)
    return JSONResponse(content={"query_original": query, "parametros_extraidos": params.dict(exclude_defaults=True), "total_encontrado": len(resultados), "resultados": resultados[:50]})
