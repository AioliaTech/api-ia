from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from unidecode import unidecode
from rapidfuzz import fuzz
from apscheduler.schedulers.background import BackgroundScheduler
from xml_fetcher import fetch_and_convert_xml
import json, os, re
from typing import Dict, List, Optional, Any
from pydantic import BaseModel

app = FastAPI()

# Mapeamento de categorias (mantido do código original)
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

    # Caminhonete
    "hilux": "Caminhonete", "ranger": "Caminhonete", "s10": "Caminhonete", "l200": "Caminhonete", "triton": "Caminhonete",
    "saveiro": "Utilitário", "strada": "Utilitário", "montana": "Utilitário", "oroch": "Utilitário", 
    "toro": "Caminhonete", 
    "frontier": "Caminhonete", "amarok": "Caminhonete", "gladiator": "Caminhonete", "maverick": "Caminhonete", "colorado": "Caminhonete",
    "dakota": "Caminhonete", "montana (nova)": "Caminhonete", "f-250": "Caminhonete", "courier (pickup)": "Caminhonete", "hoggar": "Caminhonete",
    "ram 1500": "Caminhonete",

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

    # Off-road
    "wrangler": "Off-road", "troller": "Off-road", "defender": "Off-road", "bronco": "Off-road", "samurai": "Off-road",
    "jimny": "Off-road", "land cruiser": "Off-road", "grand vitara": "Off-road", "jimny sierra": "Off-road", "bandeirante (ate 2001)": "Off-road"
}

# Dicionários para extração inteligente de parâmetros
MARCAS_CONHECIDAS = [
    "toyota", "honda", "ford", "chevrolet", "volkswagen", "fiat", "nissan", "hyundai", 
    "jeep", "renault", "peugeot", "citroën", "mitsubishi", "kia", "mazda", "subaru",
    "suzuki", "audi", "bmw", "mercedes", "volvo", "land rover", "jaguar", "porsche",
    "ferrari", "lamborghini", "bentley", "rolls royce", "maserati", "bugatti",
    "tesla", "lexus", "infiniti", "acura", "cadillac", "lincoln", "buick", "gmc",
    "dodge", "chrysler", "ram", "isuzu", "daihatsu", "great wall", "haval", "byd",
    "chery", "geely", "mg", "jac", "lifan", "foton", "iveco", "scania", "volvo",
    "mercedes-benz", "vw"
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

class SearchParams(BaseModel):
    marca: Optional[str] = None
    modelo: Optional[str] = None
    ano: Optional[int] = None
    ano_fabricacao: Optional[int] = None
    ano_min: Optional[int] = None
    ano_max: Optional[int] = None
    km: Optional[float] = None
    km_max: Optional[float] = None
    cor: Optional[str] = None
    combustivel: Optional[str] = None
    cambio: Optional[str] = None
    transmissao: Optional[str] = None  # Corrigido
    motor: Optional[str] = None
    portas: Optional[int] = None
    categoria: Optional[str] = None
    preco: Optional[float] = None
    valor_max: Optional[float] = None  # Corrigido
    valor_min: Optional[float] = None  # Corrigido
    opcionais: Optional[str] = None

def normalizar(texto: str) -> str:
    """Função de normalização mantida do código original"""
    return unidecode(texto).lower().replace("-", "").replace(" ", "").strip()

def extrair_valores_numericos(texto: str) -> List[float]:
    """Extrai valores numéricos do texto, considerando formatos brasileiros"""
    # Padrões para valores em reais
    padroes_valores = [
        r'r\$\s*([\d,.]+)',  # R$ 150.000 ou R$ 150,000
        r'([\d,.]+)\s*reais?',  # 150000 reais
        r'([\d,.]+)\s*mil',  # 150 mil
        r'ate\s*([\d,.]+)',  # até 150000
        r'max\s*([\d,.]+)',  # max 150000
        r'maximo\s*([\d,.]+)',  # máximo 150000
        r'([\d,.]+)',  # qualquer número
    ]
    
    valores = []
    texto_lower = texto.lower()
    
    for padrao in padroes_valores:
        matches = re.findall(padrao, texto_lower)
        for match in matches:
            try:
                # Remove pontos e vírgulas, converte para float
                valor_str = match.replace(',', '').replace('.', '')
                valor = float(valor_str)
                
                # Se encontrou "mil" no contexto, multiplica por 1000
                if 'mil' in texto_lower:
                    valor *= 1000
                
                valores.append(valor)
            except ValueError:
                continue
    
    return sorted(set(valores), reverse=True)

def extrair_anos(texto: str) -> List[int]:
    """Extrai anos do texto"""
    padroes_ano = [
        r'(20\d{2})',  # 2020, 2021, etc.
        r'(19\d{2})',  # 1999, 1998, etc.
        r'ano\s*(20\d{2})',
        r'modelo\s*(20\d{2})',
    ]
    
    anos = []
    for padrao in padroes_ano:
        matches = re.findall(padrao, texto.lower())
        for match in matches:
            try:
                ano = int(match)
                if 1980 <= ano <= 2030:  # Anos válidos para veículos
                    anos.append(ano)
            except ValueError:
                continue
    
    return sorted(set(anos))

def encontrar_melhor_match(texto: str, lista_opcoes: List[str], threshold: int = 70) -> Optional[str]:
    """Encontra a melhor correspondência usando fuzzy matching"""
    texto_norm = normalizar(texto)
    melhor_score = 0
    melhor_match = None
    
    for opcao in lista_opcoes:
        opcao_norm = normalizar(opcao)
        score = fuzz.partial_ratio(texto_norm, opcao_norm)
        if score > melhor_score and score >= threshold:
            melhor_score = score
            melhor_match = opcao
    
    return melhor_match

def extrair_parametros_inteligente(query: str) -> SearchParams:
    """Extrai APENAS os parâmetros explicitamente mencionados na query"""
    query_lower = query.lower()
    params = SearchParams()
    
    # Extrair preço/valor
    padroes_preco = [
        r'(?:ate|até|max|maximo|máximo|teto|limite)?\s*r?\$?\s*([\d,.]+)\s*(?:mil|k|reais?|r\$)?',
        r'preco\s*(?:ate|até|max|maximo|máximo)?\s*r?\$?\s*([\d,.]+)',
        r'valor\s*(?:ate|até|max|maximo|máximo)?\s*r?\$?\s*([\d,.]+)'
    ]
    
    for padrao in padroes_preco:
        matches = re.findall(padrao, query_lower)
        if matches and any(word in query_lower for word in ['ate', 'até', 'max', 'maximo', 'máximo', 'teto', 'limite', 'preco', 'valor']):
            try:
                valor_str = matches[0].replace(',', '').replace('.', '')
                valor = float(valor_str)
                if 'mil' in query_lower or 'k' in query_lower:
                    if valor < 1000:  # Se for menor que 1000, provavelmente já está em milhares
                        valor *= 1000
                params.preco = valor
                params.valor_max = valor  # Adiciona também valor_max
                break
            except ValueError:
                continue
    
    # Extrair ano - APENAS se explicitamente mencionado
    if 'ano' in query_lower or re.search(r'\b(20\d{2}|19\d{2})\b', query_lower):
        anos = re.findall(r'\b(20\d{2}|19\d{2})\b', query_lower)
        if anos:
            params.ano = int(anos[0])
    
    # Extrair ano de fabricação - APENAS se explicitamente mencionado
    if 'fabricacao' in query_lower or 'fabricação' in query_lower:
        anos = re.findall(r'fabricac[aã]o\s*(\d{4})', query_lower)
        if anos:
            params.ano_fabricacao = int(anos[0])
    
    # Extrair km - APENAS se explicitamente mencionado
    if 'km' in query_lower:
        km_patterns = [
            r'(\d+)\.?(\d*)\s*k?m?\s*km',
            r'(\d+)\s*mil\s*km',
            r'km\s*(\d+)',
            r'(\d+)\s*k\s*km'
        ]
        
        for pattern in km_patterns:
            matches = re.findall(pattern, query_lower)
            if matches:
                try:
                    if isinstance(matches[0], tuple):
                        km = float(matches[0][0])
                    else:
                        km = float(matches[0])
                    if km < 1000 and 'mil' in query_lower:
                        km *= 1000
                    params.km = km
                    params.km_max = km  # Adiciona também km_max
                    break
                except ValueError:
                    continue
    
    # Extrair cor - APENAS se explicitamente mencionada
    cores_encontradas = []
    for cor in CORES_CONHECIDAS:
        if cor in query_lower:
            cores_encontradas.append(cor)
    
    if cores_encontradas:
        # Pega a cor mais específica (mais longa)
        params.cor = max(cores_encontradas, key=len)
    
    # Extrair combustível - APENAS se explicitamente mencionado
    for combustivel in COMBUSTIVEIS_CONHECIDOS:
        if combustivel in query_lower:
            params.combustivel = combustivel
            break
    
    # Extrair câmbio/transmissão - APENAS se explicitamente mencionado
    cambios = ['manual', 'automatico', 'automatica', 'cvt', 'semi-automatico', 'semi-automatica', 'tiptronic']
    for cambio in cambios:
        if cambio in query_lower:
            params.cambio = cambio
            params.transmissao = cambio  # Preenche ambos os campos
            break
    
    # Extrair motor - APENAS se explicitamente mencionado
    if 'motor' in query_lower:
        motor_patterns = [
            r'motor\s*(\d+\.?\d*)',
            r'(\d+\.?\d*)\s*(?:litros?|l)\s*motor',
            r'(\d+\.?\d*)\s*motor'
        ]
        
        for pattern in motor_patterns:
            matches = re.findall(pattern, query_lower)
            if matches:
                params.motor = matches[0]
                break
    
    # Extrair portas - APENAS se explicitamente mencionado
    if 'porta' in query_lower:
        portas_patterns = [
            r'(\d+)\s*porta',
            r'porta\s*(\d+)'
        ]
        
        for pattern in portas_patterns:
            matches = re.findall(pattern, query_lower)
            if matches:
                try:
                    params.portas = int(matches[0])
                    break
                except ValueError:
                    continue
    
    # Extrair categoria - APENAS se explicitamente mencionada
    categorias_possiveis = ['hatch', 'sedan', 'suv', 'caminhonete', 'utilitario', 'utilitário', 'furgao', 'furgão', 
                           'coupe', 'coupé', 'conversivel', 'conversível', 'minivan', 'station wagon', 'off-road']
    
    for categoria in categorias_possiveis:
        if categoria in query_lower:
            # Mapear para formato padrão
            if categoria in ['suv']:
                params.categoria = 'SUV'
            elif categoria in ['utilitario', 'utilitário']:
                params.categoria = 'Utilitário'
            elif categoria in ['furgao', 'furgão']:
                params.categoria = 'Furgão'
            elif categoria in ['coupe', 'coupé']:
                params.categoria = 'Coupe'
            elif categoria in ['conversivel', 'conversível']:
                params.categoria = 'Conversível'
            else:
                params.categoria = categoria.title()
            break
    
    # Extrair marca - APENAS se explicitamente mencionada
    # Busca por marcas que aparecem como palavras completas na query
    palavras_query = query_lower.split()
    for palavra in palavras_query:
        palavra_limpa = re.sub(r'[^\w]', '', palavra)
        for marca in MARCAS_CONHECIDAS:
            if palavra_limpa == marca.lower():
                params.marca = marca.title()
                break
        if params.marca:
            break
    
    # Extrair modelo - APENAS se explicitamente mencionado
    # Busca por modelos que aparecem como palavras na query
    modelos_conhecidos = list(MAPEAMENTO_CATEGORIAS.keys())
    for palavra in palavras_query:
        palavra_limpa = re.sub(r'[^\w]', '', palavra)
        for modelo in modelos_conhecidos:
            if palavra_limpa == modelo.lower():
                params.modelo = modelo
                break
        if params.modelo:
            break
    
    # Extrair opcionais - busca por palavras relacionadas
    opcionais_keywords = ['ar', 'arcondicionado', 'direcao', 'direção', 'eletrica', 'elétrica', 'vidro', 'eletrico', 'elétrico', 
                         'trava', 'alarme', 'airbag', 'abs', 'cd', 'mp3', 'bluetooth', 'gps', 'navegador']
    
    opcionais_encontrados = []
    for opcional in opcionais_keywords:
        if opcional in query_lower:
            opcionais_encontrados.append(opcional)
    
    if opcionais_encontrados:
        params.opcionais = ', '.join(opcionais_encontrados)
    
    return params

def converter_preco(valor_str):
    """Função mantida do código original"""
    try:
        return float(str(valor_str).replace(",", "").replace("R$", "").strip())
    except (ValueError, TypeError):
        return None

def get_price_for_sort(price_val):
    """Função mantida do código original"""
    converted = converter_preco(price_val)
    return converted if converted is not None else float('-inf')

def inferir_categoria_por_modelo(modelo_buscado):
    """Função mantida do código original"""
    modelo_norm = normalizar(modelo_buscado)
    return MAPEAMENTO_CATEGORIAS.get(modelo_norm)

def filtrar_veiculos_inteligente(vehicles: List[Dict], params: SearchParams) -> List[Dict]:
    """Versão aprimorada da função de filtro usando os parâmetros extraídos"""
    vehicles_processados = list(vehicles)
    
    # Inicializa scores de relevância
    for v in vehicles_processados:
        v['_relevance_score'] = 0.0
        v['_matched_criteria'] = 0
    
    # Filtros básicos (marca, modelo, categoria)
    if params.marca:
        vehicles_temp = []
        for v in vehicles_processados:
            marca_veiculo = normalizar(str(v.get("marca", "")))
            marca_busca = normalizar(params.marca)
            
            if marca_busca in marca_veiculo or fuzz.partial_ratio(marca_veiculo, marca_busca) >= 80:
                v['_relevance_score'] += 100
                v['_matched_criteria'] += 1
                vehicles_temp.append(v)
        vehicles_processados = vehicles_temp
    
    if params.modelo:
        vehicles_temp = []
        for v in vehicles_processados:
            modelo_veiculo = normalizar(str(v.get("modelo", "")))
            titulo_veiculo = normalizar(str(v.get("titulo", "")))
            modelo_busca = normalizar(params.modelo)
            
            score_modelo = max(
                fuzz.partial_ratio(modelo_veiculo, modelo_busca),
                fuzz.partial_ratio(titulo_veiculo, modelo_busca)
            )
            
            if modelo_busca in modelo_veiculo or modelo_busca in titulo_veiculo or score_modelo >= 75:
                v['_relevance_score'] += score_modelo
                v['_matched_criteria'] += 1
                vehicles_temp.append(v)
        vehicles_processados = vehicles_temp
    
    if params.categoria:
        vehicles_temp = []
        for v in vehicles_processados:
            categoria_veiculo = normalizar(str(v.get("categoria", "")))
            categoria_busca = normalizar(params.categoria)
            
            if categoria_busca == categoria_veiculo:
                v['_relevance_score'] += 80
                v['_matched_criteria'] += 1
                vehicles_temp.append(v)
        vehicles_processados = vehicles_temp
    
    # Filtros adicionais (cor, combustível, transmissão, etc.)
    filtros_adicionais = [
        (params.cor, "cor"),
        (params.combustivel, "combustivel"),
        (params.transmissao, "transmissao")
    ]
    
    for param_value, field_name in filtros_adicionais:
        if param_value:
            for v in vehicles_processados:
                field_value = normalizar(str(v.get(field_name, "")))
                param_norm = normalizar(param_value)
                
                if param_norm in field_value or fuzz.partial_ratio(field_value, param_norm) >= 80:
                    v['_relevance_score'] += 50
                    v['_matched_criteria'] += 1
    
    # Filtros de valor
    if params.valor_max:
        vehicles_temp = []
        for v in vehicles_processados:
            preco = converter_preco(v.get("preco"))
            if preco is not None and preco <= params.valor_max * 1.3:  # Margem de 30%
                vehicles_temp.append(v)
        vehicles_processados = vehicles_temp
    
    if params.valor_min:
        vehicles_temp = []
        for v in vehicles_processados:
            preco = converter_preco(v.get("preco"))
            if preco is not None and preco >= params.valor_min:
                vehicles_temp.append(v)
        vehicles_processados = vehicles_temp
    
    # Filtros de ano
    if params.ano_min:
        vehicles_temp = []
        for v in vehicles_processados:
            try:
                ano = int(v.get("ano", 0))
                if ano >= params.ano_min:
                    vehicles_temp.append(v)
            except (ValueError, TypeError):
                continue
        vehicles_processados = vehicles_temp
    
    if params.ano_max:
        vehicles_temp = []
        for v in vehicles_processados:
            try:
                ano = int(v.get("ano", 0))
                if ano <= params.ano_max:
                    vehicles_temp.append(v)
            except (ValueError, TypeError):
                continue
        vehicles_processados = vehicles_temp
    
    # Filtro de quilometragem
    if params.km_max:
        vehicles_temp = []
        for v in vehicles_processados:
            try:
                km = float(str(v.get("km", "0")).replace(",", "").replace(".", ""))
                if km <= params.km_max:
                    vehicles_temp.append(v)
            except (ValueError, TypeError):
                continue
        vehicles_processados = vehicles_temp
    
    # Ordenação por relevância e preço
    vehicles_processados.sort(
        key=lambda v: (
            v['_matched_criteria'],
            v['_relevance_score'],
            get_price_for_sort(v.get("preco"))
        ),
        reverse=True
    )
    
    # Remove campos temporários
    for v in vehicles_processados:
        v.pop('_relevance_score', None)
        v.pop('_matched_criteria', None)
    
    return vehicles_processados

@app.on_event("startup")
def agendar_tarefas():
    """Função mantida do código original"""
    scheduler = BackgroundScheduler(timezone="America/Sao_Paulo")
    scheduler.add_job(fetch_and_convert_xml, "cron", hour="0,12")
    scheduler.start()
    fetch_and_convert_xml()

@app.post("/api/search-smart")
def search_smart(request_data: dict):
    """Nova endpoint para busca inteligente"""
    query = request_data.get("query", "")
    
    if not query:
        return JSONResponse(
            content={"error": "Query não informada", "resultados": [], "total_encontrado": 0},
            status_code=400
        )
    
    # Carrega dados
    if not os.path.exists("data.json"):
        return JSONResponse(
            content={"error": "Nenhum dado disponível", "resultados": [], "total_encontrado": 0},
            status_
