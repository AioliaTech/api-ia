from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from unidecode import unidecode
from rapidfuzz import fuzz
from apscheduler.schedulers.background import BackgroundScheduler
from xml_fetcher import fetch_and_convert_xml
import json, os, spacy, re

app = FastAPI()

# Carregar modelo spaCy
nlp = spacy.load("pt_core_news_sm")

# Lista de marcas e modelos (exemplo, pode ser enriquecido com database.json)
with open("database.json", "r", encoding="utf-8") as f:
    db = json.load(f)
    MARCAS = [m.lower() for m in db.get("marcas", [])]
    MODELOS = [m.lower() for m in db.get("modelos", [])]

# Campos que podem ser extraídos
CAMPOS_EXTRAIVEIS = [
    "modelo", "marca", "categoria", "cor", "combustivel",
    "cambio", "motor", "portas", "ano", "ano_fabricacao", "preco", "opcionais", "ValorMax", "AnoMax"
]

# Mapeamento de categorias (mantido)
MAPEAMENTO_CATEGORIAS = {...}  # MANTER COMO ESTAVA

# Normalização

def normalizar(texto: str) -> str:
    return unidecode(texto).lower().replace("-", "").replace(" ", "").strip()

def converter_preco(valor_str):
    try:
        return float(str(valor_str).replace(",", "").replace("R$", "").strip())
    except (ValueError, TypeError):
        return None

# Função para extrair campos da mensagem natural com spaCy

def extrair_filtros_nlp(frase: str):
    doc = nlp(frase)
    filtros = {}
    frase_lower = frase.lower()

    # Marca
    for marca in MARCAS:
        if marca in frase_lower:
            filtros["marca"] = marca
            break

    # Modelo
    for modelo in MODELOS:
        if modelo in frase_lower:
            filtros["modelo"] = modelo
            break

    # Cor
    cores = ["branco", "preto", "vermelho", "prata", "azul", "cinza", "verde", "amarelo", "marrom", "bege"]
    for cor in cores:
        if cor in frase_lower:
            filtros["cor"] = cor
            break

    # Combustível
    for c in ["gasolina", "etanol", "flex", "diesel", "elétrico", "híbrido"]:
        if c in frase_lower:
            filtros["combustivel"] = c
            break

    # Câmbio
    for c in ["manual", "automático", "automatico"]:
        if c in frase_lower:
            filtros["cambio"] = "automático" if "auto" in c else "manual"
            break

    # Motor (regex para 1.0, 1.6 etc)
    motor_match = re.search(r"\b([1-9]\.[0-9])\b", frase)
    if motor_match:
        filtros["motor"] = motor_match.group(1)

    # Portas (regex)
    portas_match = re.search(r"(\d)\s*portas", frase_lower)
    if portas_match:
        filtros["portas"] = portas_match.group(1)

    # ValorMax
    val_match = re.search(r"(\d{2,3}\.?\d{0,3})\s*(mil|k)?\s*(reais|r\$)?", frase_lower)
    if val_match:
        valor = val_match.group(1).replace(".", "")
        filtros["ValorMax"] = valor

    # AnoMax
    ano_match = re.search(r"(20\d{2}|19\d{2})", frase_lower)
    if ano_match:
        filtros["AnoMax"] = ano_match.group(1)

    return filtros

# Todas as demais funções (filtrar_veiculos, inferir_categoria, etc) PERMANECEM IGUAIS
# Você só vai alterar o endpoint abaixo:

@app.get("/api/data")
def get_data(request: Request):
    if not os.path.exists("data.json"):
        return JSONResponse(content={"error": "Nenhum dado disponível", "resultados": [], "total_encontrado": 0}, status_code=404)

    try:
        with open("data.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        vehicles = data["veiculos"]
    except:
        return JSONResponse(content={"error": "Erro ao ler dados"}, status_code=500)

    # Se vier 'mensagem', usa spaCy para extrair
    mensagem = request.query_params.get("mensagem")
    filtros = extrair_filtros_nlp(mensagem) if mensagem else {}

    # ValorMax separado para lógica de teto
    valormax = filtros.pop("ValorMax", None)

    filtros_ativos = {k: v for k, v in filtros.items() if k in CAMPOS_EXTRAIVEIS}

    resultado = filtrar_veiculos(vehicles, filtros_ativos, valormax)

    if resultado:
        return JSONResponse(content={
            "resultados": resultado,
            "total_encontrado": len(resultado),
            "filtros_usados": filtros_ativos
        })

    # Lógica alternativa mantida (inferência por categoria, etc)
    # ... copiar a lógica já existente

    return JSONResponse(content={
        "resultados": [],
        "total_encontrado": 0,
        "instrucao_ia": "Não encontramos veículos com os parâmetros informados."
    })

@app.on_event("startup")
def agendar_tarefas():
    scheduler = BackgroundScheduler(timezone="America/Sao_Paulo")
    scheduler.add_job(fetch_and_convert_xml, "cron", hour="0,12")
    scheduler.start()
    fetch_and_convert_xml()
