# main.py
import json
import logging
import re
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set

import requests
import spacy
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from rapidfuzz import fuzz
from spacy.matcher import Matcher, PhraseMatcher
from unidecode import unidecode

# --- Configuração Básica ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
app = FastAPI(title="API de Busca Inteligente de Veículos")

# --- Constantes e Variáveis Globais ---
FIPE_API_BASE_URL = "https://parallelum.com.br/fipe/api/v1/carros/marcas"
FIPE_DATABASE_FILE = Path("fipe_database.json")
DATABASE_EXPIRATION_DAYS = 7
FIPE_DATA = {}
SPACY_MATCHERS = {}

# Carregar modelo SpaCy
try:
    nlp = spacy.load("pt_core_news_lg")
except OSError:
    logging.error("Modelo 'pt_core_news_lg' não encontrado. Execute 'python -m spacy download pt_core_news_lg'")
    nlp = None

# --- Seção de Gerenciamento de Dados da FIPE (sem alterações) ---
# ... (a seção que busca dados da FIPE e os armazena em cache permanece a mesma) ...
def parse_vehicle_details(version_string: str) -> Dict[str, Set[str]]:
    details = {"motores": set(), "combustiveis": set()}
    text = version_string.lower()
    motor_matches = re.findall(r'(\d\.\d)', text)
    if motor_matches: details["motores"].update(motor_matches)
    known_engines = ["tsi", "thp", "v6", "v8", "mpi", "fire", "ecoboost"]
    for engine in known_engines:
        if engine in text: details["motores"].add(engine)
    known_fuels = ["flex", "gasolina", "etanol", "alcool", "diesel", "eletrico", "hibrido", "gnv"]
    for fuel in known_fuels:
        if fuel in text: details["combustiveis"].add(fuel)
    return details

def fetch_fipe_data() -> Dict[str, List[str]]:
    logging.info("Iniciando busca de dados na API da FIPE. Isso pode levar alguns minutos...")
    all_data = {"marcas": set(), "modelos": set(), "versoes": set(), "motores": set(), "combustiveis": set()}
    try:
        marcas_response = requests.get(FIPE_API_BASE_URL, timeout=30)
        marcas_response.raise_for_status()
        marcas = marcas_response.json()
        for marca in marcas:
            marca_nome = marca['nome'].lower()
            all_data["marcas"].add(marca_nome)
            logging.info(f"Buscando modelos para a marca: {marca_nome.title()}")
            try:
                modelos_response = requests.get(f"{FIPE_API_BASE_URL}/{marca['codigo']}/modelos", timeout=30)
                modelos_response.raise_for_status()
                modelos_data = modelos_response.json()['modelos']
                for modelo in modelos_data:
                    modelo_base = modelo['nome'].split(' ')[0].lower()
                    all_data["modelos"].add(modelo_base)
                    versao_completa = modelo['nome'].lower()
                    all_data["versoes"].add(versao_completa)
                    details = parse_vehicle_details(versao_completa)
                    all_data["motores"].update(details["motores"])
                    all_data["combustiveis"].update(details["combustiveis"])
            except requests.RequestException as e:
                logging.warning(f"Não foi possível buscar modelos para a marca {marca_nome}: {e}")
                continue
    except requests.RequestException as e:
        logging.error(f"Erro crítico ao buscar marcas da FIPE: {e}")
        return {}
    return {key: sorted(list(value)) for key, value in all_data.items()}

def get_or_update_fipe_data() -> Dict:
    if FIPE_DATABASE_FILE.exists():
        mod_time = datetime.fromtimestamp(FIPE_DATABASE_FILE.stat().st_mtime)
        if datetime.now() - mod_time < timedelta(days=DATABASE_EXPIRATION_DAYS):
            logging.info(f"Carregando dados da FIPE do cache local: {FIPE_DATABASE_FILE}")
            with open(FIPE_DATABASE_FILE, "r", encoding="utf-8") as f: return json.load(f)
    data = fetch_fipe_data()
    if data:
        logging.info(f"Salvando novos dados da FIPE em {FIPE_DATABASE_FILE}")
        with open(FIPE_DATABASE_FILE, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=2)
    return data


# --- Modelos Pydantic (ATUALIZADO) ---

class SearchParams(BaseModel):
    # Parâmetros de texto (podem ter múltiplos valores)
    marcas: Optional[List[str]] = None
    modelos: Optional[List[str]] = None
    versoes: Optional[List[str]] = None
    categorias: Optional[List[str]] = None
    cores: Optional[List[str]] = None
    combustiveis: Optional[List[str]] = None
    cambios: Optional[List[str]] = None
    motores: Optional[List[str]] = None
    opcionais: Optional[List[str]] = None
    
    # Parâmetros numéricos
    valor_max: Optional[float] = None
    valor_min: Optional[float] = None
    ano_max: Optional[int] = None
    ano_min: Optional[int] = None
    ano_fabricacao_max: Optional[int] = None
    ano_fabricacao_min: Optional[int] = None
    km_max: Optional[int] = None
    portas: Optional[int] = None

# --- Funções de Lógica de Busca (ATUALIZADAS) ---

def normalizar(texto: str) -> str:
    return unidecode(str(texto)).lower().strip()

def extrair_parametros_com_spacy(query: str) -> SearchParams:
    if not nlp or not SPACY_MATCHERS:
        logging.warning("SpaCy ou os Matchers não foram inicializados. Extração limitada.")
        return SearchParams()

    doc = nlp(query.lower())
    params = SearchParams(marcas=[], modelos=[], versoes=[], categorias=[], cores=[], combustiveis=[], cambios=[], motores=[], opcionais=[])
    
    # Mapeamento de labels para listas de parâmetros
    param_field_map = {
        "MARCA": params.marcas, "MODELO": params.modelos, "VERSAO": params.versoes,
        "MOTOR": params.motores, "COMBUSTIVEL": params.combustiveis,
        "COR": params.cores, "CAMBIO": params.cambios,
        "CATEGORIA": params.categorias, "OPCIONAL": params.opcionais
    }

    # Usar PhraseMatcher
    phrase_matcher = SPACY_MATCHERS.get("phrase_matcher")
    matches = phrase_matcher(doc)
    for match_id, start, end in matches:
        entity_label = nlp.vocab.strings[match_id]
        entity_text = doc[start:end].text
        if entity_label in param_field_map and entity_text not in param_field_map[entity_label]:
            param_field_map[entity_label].append(entity_text)
            
    # Usar Matcher para padrões
    matcher = SPACY_MATCHERS.get("matcher")
    matches = matcher(doc)
    for match_id, start, end in matches:
        rule_id = nlp.vocab.strings[match_id]
        span = doc[start:end]
        num_token = next((token for token in span if token.like_num), None)
        if not num_token: continue
        
        valor_str = num_token.text.replace('.', '').replace(',', '')
        valor = int(valor_str)
        
        # Lógica para preços (valores altos ou com "mil")
        is_price = any(t.lower_ in ["mil", "k"] for t in span if t.i > num_token.i) or valor > 5000
        
        if rule_id in ["PRECO_MAX", "PRECO_MIN"] and is_price:
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
        elif rule_id == "PORTAS":
            params.portas = valor
    
    # Ajustar ranges de ano
    for prefix in ["ano", "ano_fabricacao"]:
        min_attr, max_attr = f"{prefix}_min", f"{prefix}_max"
        min_val, max_val = getattr(params, min_attr), getattr(params, max_attr)
        if min_val and max_val and min_val > max_val:
            setattr(params, min_attr, max_val), setattr(params, max_attr, min_val)
        if min_val and not max_val:
            setattr(params, max_attr, min_val)

    return params


def filtrar_veiculos_inteligente(vehicles: List[Dict], params: SearchParams) -> List[Dict]:
    filtered = list(vehicles)

    # Filtros de texto (fuzzy match)
    text_filters = {
        "marcas": "marca", "modelos": "modelo", "versoes": "titulo",
        "categorias": "categoria", "cores": "cor", "combustiveis": "combustivel",
        "cambios": "cambio", "motores": "titulo"
    }
    for param_name, field_name in text_filters.items():
        param_values = getattr(params, param_name)
        if param_values:
            filtered = [
                v for v in filtered if (val := v.get(field_name)) and any(
                    fuzz.partial_ratio(normalizar(p_val), normalizar(val)) >= 85 for p_val in param_values
                )
            ]

    # Filtro de opcionais (deve conter TODOS os solicitados)
    if params.opcionais:
        filtered = [
            v for v in filtered if (opts := v.get("opcionais")) and isinstance(opts, list) and all(
                any(fuzz.partial_ratio(normalizar(req_opt), normalizar(v_opt)) >= 90 for v_opt in opts)
                for req_opt in params.opcionais
            )
        ]

    # Filtros numéricos
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


# --- Eventos de Inicialização da Aplicação (ATUALIZADO) ---

@app.on_event("startup")
def startup_event():
    global FIPE_DATA, SPACY_MATCHERS
    if not nlp: return

    FIPE_DATA = get_or_update_fipe_data()
    if not FIPE_DATA:
        logging.error("Não foi possível carregar os dados da FIPE. A busca inteligente será limitada.")
        return

    logging.info("Inicializando os matchers do SpaCy com os dados da FIPE e listas customizadas...")
    
    # --- Listas de Conhecimento Customizadas (EXPANDA AQUI) ---
    CATEGORIAS_CONHECIDAS = ["suv", "sedan", "hatch", "picape", "caminhonete", "utilitário", "esportivo", "conversível"]
    OPCIONAIS_CONHECIDOS = ["teto solar", "banco de couro", "bancos de couro", "ar condicionado", "direção hidraulica", "direção elétrica", "cambio automatico", "central multimidia", "piloto automático", "rodas de liga leve"]
    CORES_CONHECIDAS = ["branco", "preto", "prata", "cinza", "azul", "vermelho", "verde", "amarelo", "dourado", "marrom", "bege", "vinho"]
    CAMBIOS_CONHECIDOS = ["manual", "automatico", "automatica", "cvt", "tiptronic", "automatizado"]
    
    # Configurar PhraseMatcher
    phrase_matcher = PhraseMatcher(nlp.vocab, attr="LOWER")
    entity_map = {
        "MARCA": FIPE_DATA.get("marcas", []), "MODELO": FIPE_DATA.get("modelos", []),
        "VERSAO": FIPE_DATA.get("versoes", []), "MOTOR": FIPE_DATA.get("motores", []),
        "COMBUSTIVEL": FIPE_DATA.get("combustiveis", []), "CATEGORIA": CATEGORIAS_CONHECIDAS,
        "OPCIONAL": OPCIONAIS_CONHECIDOS, "COR": CORES_CONHECIDAS, "CAMBIO": CAMBIOS_CONHECIDOS
    }
    for label, terms in entity_map.items():
        if terms: phrase_matcher.add(label, [nlp.make_doc(term) for term in terms])
    SPACY_MATCHERS["phrase_matcher"] = phrase_matcher

    # Configurar Matcher (baseado em regras)
    matcher = Matcher(nlp.vocab)
    matcher.add("PRECO_MAX", [[{"LOWER": {"IN": ["ate", "maximo", "max", "teto", "abaixo de"]}}, {"IS_SPACE": True, "OP": "?"}, {"LIKE_NUM": True}]])
    matcher.add("PRECO_MIN", [[{"LOWER": {"IN": ["a partir de", "acima de", "minimo"]}}, {"IS_SPACE": True, "OP": "?"}, {"LIKE_NUM": True}]])
    matcher.add("ANO_MODELO", [[{"LOWER": "ano", "OP": "!"}, {"LOWER": "de", "OP": "!"}, {"LOWER": "fabricacao", "OP": "!"}, {"IS_DIGIT": True, "SHAPE": "dddd"}]])
    matcher.add("ANO_FABRICACAO", [[{"LOWER": {"IN": ["fabricado", "fabricacao"]}}, {"LOWER": "em", "OP": "?"}, {"LOWER": "de", "OP": "?"}, {"IS_DIGIT": True, "SHAPE": "dddd"}]])
    matcher.add("KM_MAX", [[{"LOWER": {"IN": ["ate", "maximo", "max", "teto", "abaixo de", "com"]}}, {"LIKE_NUM": True}, {"LOWER": {"IN": ["km", "mil km"]}}]])
    matcher.add("PORTAS", [[{"LIKE_NUM": True}, {"LOWER": {"IN": ["p", "portas"]}}]])
    SPACY_MATCHERS["matcher"] = matcher
    
    logging.info("Matchers do SpaCy prontos.")
    
    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(get_or_update_fipe_data, 'interval', days=DATABASE_EXPIRATION_DAYS)
    scheduler.start()
    logging.info(f"Agendada atualização dos dados da FIPE a cada {DATABASE_EXPIRATION_DAYS} dias.")

# --- Endpoints da API ---

@app.get("/", include_in_schema=False)
def root():
    return {"message": "API de Busca Inteligente de Veículos está operacional."}

@app.post("/api/search-smart")
async def search_smart(request: Request):
    request_data = await request.json()
    query = request_data.get("query")
    if not query: return JSONResponse(content={"error": "Query não informada"}, status_code=400)
    
    if not os.path.exists("data.json"): return JSONResponse(content={"error": "Arquivo de estoque (data.json) não encontrado"}, status_code=404)
    try:
        with open("data.json", "r", encoding="utf-8") as f:
            vehicles = json.load(f).get("veiculos", [])
    except (json.JSONDecodeError, KeyError):
        return JSONResponse(content={"error": "Erro ao ler o arquivo de estoque"}, status_code=500)

    params = extrair_parametros_com_spacy(query)
    resultados = filtrar_veiculos_inteligente(vehicles, params)
    
    response_data = {
        "query_original": query,
        "parametros_extraidos": params.dict(exclude_defaults=True),
        "total_encontrado": len(resultados),
        "resultados": resultados[:50]
    }
    return JSONResponse(content=response_data)
