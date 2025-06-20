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
    # Cole aqui o seu MAPEAMENTO_CATEGORIAS completo
    "gol": "Hatch", "onix": "Hatch", "hb20": "Hatch", "duster": "SUV", "civic": "Sedan",
    "corolla": "Sedan", "compass": "SUV", "renegade": "SUV", "hilux": "Caminhonete",
    # etc...
}


# --- MODELOS PYDANTIC ---
class SearchParams(BaseModel):
    marcas: Optional[List[str]] = None
    modelos: Optional[List[str]] = None
    versoes: Optional[List[str]] = None
    categorias: Optional[List[str]] = None
    cores: Optional[List[str]] = None
    combustiveis: Optional[List[str]] = None
    cambios: Optional[List[str]] = None
    motores: Optional[List[str]] = None
    opcionais: Optional[List[str]] = None
    valor_max: Optional[float] = None
    valor_min: Optional[float] = None
    ano_max: Optional[int] = None
    ano_min: Optional[int] = None
    ano_fabricacao_max: Optional[int] = None
    ano_fabricacao_min: Optional[int] = None
    km_max: Optional[int] = None
    portas: Optional[int] = None

# --- FUNÇÕES AUXILIARES E DE LÓGICA ---

def normalizar(texto: str) -> str:
    return unidecode(str(texto)).lower().strip()

def extrair_parametros_com_spacy(query: str) -> SearchParams:
    nlp = SPACY_MATCHERS.get("nlp")
    if not nlp:
        return SearchParams()
    doc = nlp(query.lower())
    params = SearchParams(marcas=[], modelos=[], versoes=[], categorias=[], cores=[], combustiveis=[], cambios=[], motores=[], opcionais=[])
    
    # PhraseMatcher para vocabulário
    if "phrase_matcher" in SPACY_MATCHERS:
        phrase_matcher = SPACY_MATCHERS["phrase_matcher"]
        matches = phrase_matcher(doc)
        param_field_map = {
            "MARCA": params.marcas, "MODELO": params.modelos, "VERSAO": params.versoes,
        }
        for match_id, start, end in matches:
            entity_label = nlp.vocab.strings[match_id]
            entity_text = doc[start:end].text
            if entity_label in param_field_map and entity_text not in param_field_map[entity_label]:
                param_field_map[entity_label].append(entity_text)

    # Adicionar extração de categoria por inferência, se não encontrada
    if not params.categorias and params.modelos:
        for modelo in params.modelos:
            categoria = MAPEAMENTO_CATEGORIAS.get(normalizar(modelo))
            if categoria and categoria not in params.categorias:
                params.categorias.append(categoria)

    # Matcher para padrões (preço, ano, etc.)
    if "matcher" in SPACY_MATCHERS:
        matcher = SPACY_MATCHERS["matcher"]
        matches = matcher(doc)
        # ... (código da função extrair_parametros... para PRECO, ANO, KM, etc)
        # (Omitido por brevidade, mas cole aqui a lógica da resposta anterior)
        
    return params

def filtrar_veiculos_inteligente(vehicles: List[Dict], params: SearchParams) -> List[Dict]:
    filtered = list(vehicles)
    # ... (código da função filtrar_veiculos_inteligente... da resposta anterior)
    # (Omitido por brevidade, mas cole aqui a lógica da resposta anterior)
    return filtered


def load_inventory_from_file():
    """Carrega ou recarrega o inventário do arquivo dados.json para a memória."""
    global VEHICLE_INVENTORY
    if os.path.exists(INVENTORY_FILE):
        logging.info(f"Carregando/recarregando inventário de '{INVENTORY_FILE}'...")
        try:
            with open(INVENTORY_FILE, "r", encoding="utf-8") as f:
                VEHICLE_INVENTORY = json.load(f).get("veiculos", [])
            logging.info(f"{len(VEHICLE_INVENTORY)} veículos carregados na memória.")
        except (json.JSONDecodeError, AttributeError) as e:
            logging.error(f"Erro ao ler o arquivo JSON do inventário: {e}")
            VEHICLE_INVENTORY = []
    else:
        logging.warning(f"Arquivo de inventário '{INVENTORY_FILE}' não encontrado.")
        VEHICLE_INVENTORY = []

def update_and_reload_inventory():
    """Função que o agendador chamará: busca os dados e recarrega na memória."""
    logging.info("Tarefa agendada: iniciando atualização do inventário.")
    fetch_and_convert_xml()  # Seu script que cria o dados.json
    load_inventory_from_file() # Recarrega os novos dados para a memória da API
    logging.info("Tarefa agendada: atualização do inventário concluída.")

# --- EVENTO DE STARTUP DA API ---

@app.on_event("startup")
def startup_event():
    """Configura tudo quando a aplicação inicia."""
    # 1. Configurar SpaCy com o vocabulário da FIPE
    try:
        nlp = spacy.load("pt_core_news_lg")
        SPACY_MATCHERS["nlp"] = nlp
        if os.path.exists(VOCABULARY_FILE):
            logging.info(f"Carregando vocabulário de '{VOCABULARY_FILE}'...")
            with open(VOCABULARY_FILE, "r", encoding="utf-8") as f:
                fipe_vocabulary = json.load(f)
            
            phrase_matcher = PhraseMatcher(nlp.vocab, attr="LOWER")
            entity_map = { "MARCA": fipe_vocabulary.get("marcas", []), "MODELO": fipe_vocabulary.get("modelos", []), "VERSAO": fipe_vocabulary.get("versoes", []) }
            for label, terms in entity_map.items():
                if terms:
                    patterns = [nlp.make_doc(term) for term in terms]
                    phrase_matcher.add(label, patterns)
            SPACY_MATCHERS["phrase_matcher"] = phrase_matcher
            logging.info("PhraseMatcher do SpaCy configurado.")
        else:
            logging.warning(f"Arquivo de vocabulário '{VOCABULARY_FILE}' não encontrado.")
            
        matcher = Matcher(nlp.vocab)
        # Adicione aqui as regras do matcher para preço, ano, km, etc.
        SPACY_MATCHERS["matcher"] = matcher

    except OSError:
        logging.error("Modelo 'pt_core_news_lg' não encontrado. Execute 'python -m spacy download pt_core_news_lg'")
    
    # 2. Executar a busca de dados inicial e carregar o inventário
    logging.info("Executando a busca inicial de dados do inventário...")
    update_and_reload_inventory()

    # 3. Agendar as atualizações futuras
    logging.info("Agendando tarefas de atualização em background...")
    scheduler = BackgroundScheduler(timezone="America/Sao_Paulo")
    scheduler.add_job(update_and_reload_inventory, "cron", hour="0,12", minute=5) # Executa às 00:05 e 12:05
    scheduler.start()
    logging.info("Aplicação iniciada e pronta.")


# --- ENDPOINT DA API ---

@app.post("/api/search")
async def search_smart(request: Request):
    """Recebe uma query em linguagem natural e busca no inventário local de veículos."""
    if not VEHICLE_INVENTORY:
        return JSONResponse(
            content={"error": "O inventário de veículos não está carregado ou está vazio. Tente novamente em alguns minutos."},
            status_code=503
        )
        
    request_data = await request.json()
    query = request_data.get("query")
    if not query:
        return JSONResponse(content={"error": "Query não informada"}, status_code=400)

    # 1. Extrair parâmetros com SpaCy
    # params = extrair_parametros_com_spacy(query)
    
    # 2. Filtrar o inventário em memória
    # resultados = filtrar_veiculos_inteligente(VEHICLE_INVENTORY, params)
    
    # Resposta de exemplo para demonstração. Substitua pelas duas linhas acima.
    params = SearchParams(modelos=["Exemplo"])
    resultados = [v for v in VEHICLE_INVENTORY if "nivus" in v.get("titulo", "").lower()] if VEHICLE_INVENTORY else []

    response_data = {
        "query_original": query,
        "parametros_extraidos": params.dict(exclude_defaults=True),
        "total_encontrado": len(resultados),
        "resultados": resultados[:50]
    }
    
    return JSONResponse(content=response_data)
