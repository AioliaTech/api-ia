from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from unidecode import unidecode
from apscheduler.schedulers.background import BackgroundScheduler
from xml_fetcher import fetch_and_convert_xml
import json, os, spacy
from spacy.matcher import PhraseMatcher
from rapidfuzz import fuzz

app = FastAPI()

# Load spaCy model
nlp = spacy.load("pt_core_news_sm")

# Dados internos para matcher
# 🔧 Você pode editar ou expandir essas listas diretamente aqui
db = {
    "marca": ["chevrolet", "volkswagen", "fiat", "ford"],
    "modelo": ["onix", "gol", "fiesta", "hb20", "corolla"],
    "cor": ["branco", "preto", "vermelho", "azul", "prata"],
    "combustivel": ["gasolina", "etanol", "flex", "diesel"],
    "motor": ["1.0", "1.6", "2.0", "turbo"],
    "cambio": ["manual", "automático"],
    "portas": ["2", "4"],
    "categoria": ["sedan", "hatch", "suv", "pickup"]
}

matcher = PhraseMatcher(nlp.vocab, attr="LOWER")

for campo, termos in db.items():
    patterns = [nlp.make_doc(t.lower()) for t in termos]
    matcher.add(campo, patterns)


def normalizar(texto):
    return unidecode(texto).lower().strip()

def extrair_parametros(mensagem):
    doc = nlp(mensagem)
    matches = matcher(doc)
    resultado = {"modelo": None, "marca": None, "cor": None, "motor": None, "cambio": None, "combustivel": None, "portas": None, "categoria": None, "ValorMax": None, "AnoMax": None}

    for match_id, start, end in matches:
        campo = nlp.vocab.strings[match_id]
        resultado[campo] = doc[start:end].text

    for token in doc:
        texto_limpo = token.text.replace(".", "").replace(",", "")
        if texto_limpo.isdigit():
            valor = int(texto_limpo)
            if 1900 < valor < 2100:
                resultado["AnoMax"] = valor
            elif 1000 < valor < 500000:
                resultado["ValorMax"] = valor

    return resultado

def converter_preco(valor_str):
    try:
        return float(str(valor_str).replace(",", "").replace("R$", "").strip())
    except:
        return None

def get_price_for_sort(price_val):
    converted = converter_preco(price_val)
    return converted if converted is not None else float('-inf')

def filtrar_veiculos(vehicles, filtros, valormax=None, ano_max=None):
    campos_fuzzy = ["modelo", "titulo"]
    vehicles_processados = list(vehicles)

    for v in vehicles_processados:
        v['_relevance_score'] = 0.0
        v['_matched_word_count'] = 0

    active_fuzzy_filter_applied = False

    for chave_filtro, valor_filtro in filtros.items():
        if not valor_filtro:
            continue

        veiculos_que_passaram_nesta_chave = []

        if chave_filtro in campos_fuzzy:
            active_fuzzy_filter_applied = True
            palavras_query = [normalizar(p) for p in valor_filtro.split() if p.strip()]

            for v in vehicles_processados:
                score = 0.0
                match_count = 0
                for palavra in palavras_query:
                    for campo in campos_fuzzy:
                        conteudo = normalizar(str(v.get(campo, "")))
                        if palavra in conteudo:
                            score += 100
                            match_count += 1
                        else:
                            fuzzy_score = fuzz.partial_ratio(conteudo, palavra)
                            if fuzzy_score > 75:
                                score += fuzzy_score
                                match_count += 1
                if match_count:
                    v['_relevance_score'] += score
                    v['_matched_word_count'] += match_count
                    veiculos_que_passaram_nesta_chave.append(v)
        else:
            termo = normalizar(valor_filtro)
            for v in vehicles_processados:
                if normalizar(str(v.get(chave_filtro, ""))) == termo:
                    veiculos_que_passaram_nesta_chave.append(v)

        vehicles_processados = veiculos_que_passaram_nesta_chave
        if not vehicles_processados:
            break

    if active_fuzzy_filter_applied:
        vehicles_processados = [v for v in vehicles_processados if v['_matched_word_count'] > 0]

    if valormax:
        try:
            teto = float(valormax)
            max_price_limit = teto * 1.3
            vehicles_processados = [v for v in vehicles_processados if converter_preco(v.get("preco")) <= max_price_limit]
        except:
            pass

    if ano_max:
        try:
            ano_max = int(ano_max)
            vehicles_processados = [v for v in vehicles_processados if int(v.get("ano")) <= ano_max]
        except:
            pass

    for v in vehicles_processados:
        v.pop('_relevance_score', None)
        v.pop('_matched_word_count', None)

    return vehicles_processados

@app.on_event("startup")
def agendar_tarefas():
    scheduler = BackgroundScheduler(timezone="America/Sao_Paulo")
    scheduler.add_job(fetch_and_convert_xml, "cron", hour="0,12")
    scheduler.start()
    fetch_and_convert_xml()

@app.get("/api/data")
def get_data(request: Request):
    if not os.path.exists("data.json"):
        return JSONResponse(content={"erro": "Base de dados ausente."}, status_code=500)

    with open("data.json", encoding="utf-8") as f:
        vehicles = json.load(f)["veiculos"]

    mensagem = request.query_params.get("mensagem")
    filtros_extraidos = extrair_parametros(mensagem or "")

    filtros = {k: v for k, v in filtros_extraidos.items() if k not in ["ValorMax", "AnoMax"] and v}
    valormax = filtros_extraidos.get("ValorMax")
    ano_max = filtros_extraidos.get("AnoMax")

    resultado = filtrar_veiculos(vehicles, filtros, valormax, ano_max)

    return JSONResponse({
        "resultados": resultado,
        "total_encontrado": len(resultado)
    })
