from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from unidecode import unidecode
from rapidfuzz import fuzz
from spacy.matcher import PhraseMatcher, Matcher
import spacy, json, os

app = FastAPI()
nlp = spacy.load("pt_core_news_sm")

# Carrega database.json com marcas e modelos
with open("database.json", "r", encoding="utf-8") as f:
    db = json.load(f)

FRASES_MODELOS = [nlp.make_doc(modelo.lower()) for modelo in db.get("modelos", [])]
FRASES_MARCAS = [nlp.make_doc(marca.lower()) for marca in db.get("marcas", [])]

phrase_matcher_modelos = PhraseMatcher(nlp.vocab, attr="LOWER")
phrase_matcher_modelos.add("MODELO", FRASES_MODELOS)
phrase_matcher_marcas = PhraseMatcher(nlp.vocab, attr="LOWER")
phrase_matcher_marcas.add("MARCA", FRASES_MARCAS)

CORES = ["branco", "preto", "prata", "vermelho", "azul", "cinza", "verde", "amarelo"]


def normalizar(texto):
    return unidecode(texto).lower().strip().replace("-", "").replace(" ", "")

def converter_preco(valor_str):
    try:
        return float(str(valor_str).replace("R$", "").replace(",", "").strip())
    except:
        return None

def parse_natural_query(texto):
    doc = nlp(texto.lower())
    filtros = {
        "modelo": None, "marca": None, "cor": None,
        "ValorMax": None, "AnoMax": None
    }

    for match_id, start, end in phrase_matcher_modelos(doc):
        filtros["modelo"] = doc[start:end].text
        break

    for match_id, start, end in phrase_matcher_marcas(doc):
        filtros["marca"] = doc[start:end].text
        break

    for token in doc:
        if token.text in CORES:
            filtros["cor"] = token.text
            break

    matcher = Matcher(nlp.vocab)
    matcher.add("VALOR", [[{"LIKE_NUM": True}, {"LOWER": {"IN": ["mil", "reais", "k"]}}]])
    matches = matcher(doc)
    for _, start, end in matches:
        span = doc[start:end]
        for tok in span:
            if tok.like_num:
                val = float(tok.text.replace(",", "."))
                if "mil" in span.text: val *= 1000
                filtros["ValorMax"] = str(int(val))
                break

    for token in doc:
        if token.like_num and int(token.text) > 1980 and int(token.text) <= 2025:
            filtros["AnoMax"] = token.text
            break

    return {k: v for k, v in filtros.items() if v}

def filtrar_veiculos(lista, filtros):
    resultados = []
    valormax = float(filtros.get("ValorMax", 1e10))
    anomax = int(filtros.get("AnoMax", 2100))

    for v in lista:
        preco = converter_preco(v.get("preco")) or 0
        ano = int(v.get("ano") or 0)

        if preco > valormax or ano > anomax:
            continue

        match = True
        for campo in ["modelo", "marca", "cor"]:
            if campo in filtros and filtros[campo]:
                if normalizar(filtros[campo]) not in normalizar(str(v.get(campo, ""))):
                    match = False
                    break

        if match:
            resultados.append({
                "id": v.get("id"),
                "titulo": v.get("titulo"),
                "marca": v.get("marca"),
                "modelo": v.get("modelo"),
                "ano": v.get("ano"),
                "ano_fabricacao": v.get("ano_fabricacao"),
                "km": v.get("km"),
                "cor": v.get("cor"),
                "combustivel": v.get("combustivel"),
                "cambio": v.get("cambio"),
                "motor": v.get("motor"),
                "portas": v.get("portas"),
                "categoria": v.get("categoria"),
                "preco": v.get("preco"),
                "opcionais": v.get("opcionais"),
                "fotos": {
                    "url_fotos": v.get("fotos", {}).get("url_fotos")
                }
            })

    return resultados

@app.get("/api/data")
def buscar(request: Request):
    if not os.path.exists("data.json"):
        return JSONResponse({"erro": "Base de dados ausente."}, status_code=404)

    with open("data.json", "r", encoding="utf-8") as f:
        dados = json.load(f)

    mensagem = request.query_params.get("mensagem")
    filtros = parse_natural_query(mensagem) if mensagem else {}

    resultados = filtrar_veiculos(dados.get("veiculos", []), filtros)

    return JSONResponse({
        "resultados": resultados,
        "total_encontrado": len(resultados),
        "filtros_usados": filtros
    })
