from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from unidecode import unidecode
from rapidfuzz import fuzz
from apscheduler.schedulers.background import BackgroundScheduler
from xml_fetcher import fetch_and_convert_xml
import json, os, re
from typing import List, Optional
from pydantic import BaseModel

app = FastAPI()

def normalizar(texto: str) -> str:
    return unidecode(texto).lower().replace("-", "").replace(" ", "").strip()

class SearchParams(BaseModel):
    marca: Optional[str] = None
    modelo: Optional[str] = None
    categoria: Optional[str] = None
    cor: Optional[str] = None
    combustivel: Optional[str] = None
    cambio: Optional[str] = None
    motor: Optional[str] = None
    portas: Optional[int] = None
    preco: Optional[float] = None
    ano: Optional[int] = None
    ano_fabricacao: Optional[int] = None
    km: Optional[float] = None
    opcionais: Optional[str] = None
    ValorMax: Optional[float] = None

    @property
    def transmissao(self) -> Optional[str]:
        return self.cambio

def converter_preco(valor_str):
    try:
        return float(str(valor_str).replace(",", "").replace("R$", "").strip())
    except (ValueError, TypeError):
        return None

def get_price_for_sort(price_val):
    converted = converter_preco(price_val)
    return converted if converted is not None else float("-inf")

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

    def filtrar(veiculos):
        resultado = []
        for v in veiculos:
            if params.marca and normalizar(params.marca) not in normalizar(str(v.get("marca", ""))):
                continue
            if params.modelo and normalizar(params.modelo) not in normalizar(str(v.get("modelo", ""))):
                continue
            if params.categoria and normalizar(params.categoria) != normalizar(str(v.get("categoria", ""))):
                continue
            if params.cor and normalizar(params.cor) not in normalizar(str(v.get("cor", ""))):
                continue
            if params.combustivel and normalizar(params.combustivel) not in normalizar(str(v.get("combustivel", ""))):
                continue
            if params.cambio and normalizar(params.cambio) not in normalizar(str(v.get("cambio", ""))):
                continue
            if params.motor and normalizar(params.motor) not in normalizar(str(v.get("motor", ""))):
                continue
            if params.portas and int(v.get("portas", 0)) != params.portas:
                continue
            if params.ano and int(v.get("ano", 0)) != params.ano:
                continue
            if params.ano_fabricacao and int(v.get("ano_fabricacao", 0)) != params.ano_fabricacao:
                continue
            if params.km and float(str(v.get("km", "0")).replace(",", "").replace(".", "")) > params.km:
                continue
            if params.preco and converter_preco(v.get("preco")) != params.preco:
                continue
            if params.ValorMax and converter_preco(v.get("preco")) > params.ValorMax:
                continue
            resultado.append(v)
        return resultado

    resultados = filtrar(vehicles)

    for v in resultados:
        v.pop('_relevance_score', None)
        v.pop('_matched_word_count', None)

    return JSONResponse({
        "query_original": query,
        "parametros_extraidos": params.dict(exclude_none=True),
        "resultados": resultados[:50],
        "total_encontrado": len(resultados)
    })
