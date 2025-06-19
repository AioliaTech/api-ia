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
    modelo: Optional[str] = None
    marca: Optional[str] = None
    categoria: Optional[str] = None
    cor: Optional[str] = None
    combustivel: Optional[str] = None
    transmissao: Optional[str] = None
    valor_max: Optional[float] = None
    valor_min: Optional[float] = None
    ano_min: Optional[int] = None
    ano_max: Optional[int] = None
    km_max: Optional[float] = None

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
    """Extrai parâmetros de busca automaticamente da query em linguagem natural"""
    query_lower = query.lower()
    params = SearchParams()
    
    # Extrair valores monetários
    valores = extrair_valores_numericos(query)
    if valores:
        # Assume que o maior valor é o máximo desejado
        if any(word in query_lower for word in ['ate', 'max', 'maximo', 'teto', 'limite']):
            params.valor_max = valores[0]
        else:
            params.valor_max = valores[0]
    
    # Extrair anos
    anos = extrair_anos(query)
    if anos:
        if len(anos) == 1:
            params.ano_min = anos[0]
        else:
            params.ano_min = min(anos)
            params.ano_max = max(anos)
    
    # Extrair categoria (SUV, sedan, hatch, etc.)
    categorias_possiveis = list(set(MAPEAMENTO_CATEGORIAS.values()))
    for categoria in categorias_possiveis:
        if categoria.lower() in query_lower:
            params.categoria = categoria
            break
    
    # Extrair marca
    palavras = query_lower.split()
    for palavra in palavras:
        marca_encontrada = encontrar_melhor_match(palavra, MARCAS_CONHECIDAS)
        if marca_encontrada:
            params.marca = marca_encontrada.title()
            break
    
    # Extrair modelo (busca por palavras que podem ser modelos)
    modelos_conhecidos = list(MAPEAMENTO_CATEGORIAS.keys())
    for palavra in palavras:
        modelo_encontrado = encontrar_melhor_match(palavra, modelos_conhecidos)
        if modelo_encontrado:
            params.modelo = modelo_encontrado
            # Se encontrou modelo, pode inferir categoria
            if not params.categoria:
                params.categoria = MAPEAMENTO_CATEGORIAS.get(modelo_encontrado)
            break
    
    # Se não encontrou modelo específico, tenta busca mais ampla
    if not params.modelo:
        query_sem_stopwords = re.sub(r'\b(busco|quero|preciso|ate|cor|ano|km|automatico|manual)\b', '', query_lower)
        palavras_relevantes = [p for p in query_sem_stopwords.split() if len(p) > 2]
        
        for palavra in palavras_relevantes:
            modelo_encontrado = encontrar_melhor_match(palavra, modelos_conhecidos, threshold=60)
            if modelo_encontrado:
                params.modelo = modelo_encontrado
                if not params.categoria:
                    params.categoria = MAPEAMENTO_CATEGORIAS.get(modelo_encontrado)
                break
    
    # Extrair cor
    for cor in CORES_CONHECIDAS:
        if cor in query_lower:
            params.cor = cor
            break
    
    # Extrair combustível
    for combustivel in COMBUSTIVEIS_CONHECIDOS:
        if combustivel in query_lower:
            params.combustivel = combustivel
            break
    
    # Extrair transmissão
    for transmissao in TRANSMISSOES_CONHECIDAS:
        if transmissao in query_lower:
            params.transmissao = transmissao
            break
    
    # Extrair quilometragem
    km_patterns = [
        r'(\d+)k?m\s*km',
        r'(\d+)\s*mil\s*km',
        r'km\s*(\d+)',
        r'(\d+)\s*k\s*km'
    ]
    
    for pattern in km_patterns:
        matches = re.findall(pattern, query_lower)
        if matches:
            try:
                km = float(matches[0])
                if km < 1000:  # Provavelmente em milhares
                    km *= 1000
                params.km_max = km
                break
            except ValueError:
                continue
    
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
            status_code=404
        )
    
    try:
        with open("data.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        vehicles = data["veiculos"]
    except (json.JSONDecodeError, KeyError):
        return JSONResponse(
            content={"error": "Erro ao ler os dados", "resultados": [], "total_encontrado": 0},
            status_code=500
        )
    
    # Extrai parâmetros da query
    params = extrair_parametros_inteligente(query)
    
    # Realiza a busca
    resultados = filtrar_veiculos_inteligente(vehicles, params)
    
    # Prepara resposta
    response_data = {
        "query_original": query,
        "parametros_extraidos": params.dict(exclude_none=True),
        "resultados": resultados[:50],  # Limita a 50 resultados
        "total_encontrado": len(resultados)
    }
    
    # Se não encontrou resultados, tenta busca mais ampla
    if not resultados:
        # Busca apenas por categoria se foi identificada
        if params.categoria:
            params_ampla = SearchParams(categoria=params.categoria, valor_max=params.valor_max)
            resultados_amplos = filtrar_veiculos_inteligente(vehicles, params_ampla)
            
            if resultados_amplos:
                response_data["resultados_alternativos"] = resultados_amplos[:10]
                response_data["total_alternativos"] = len(resultados_amplos)
                response_data["sugestao"] = f"Não encontramos veículos exatos, mas temos {len(resultados_amplos)} opções na categoria {params.categoria}"
    
    return JSONResponse(content=response_data)

@app.get("/api/data")
def get_data(request: Request):
    """Endpoint original mantida para compatibilidade"""
    if not os.path.exists("data.json"):
        return JSONResponse(content={"error": "Nenhum dado disponível", "resultados": [], "total_encontrado": 0}, status_code=404)

    try:
        with open("data.json", "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError:
        return JSONResponse(content={"error": "Erro ao ler os dados (JSON inválido)", "resultados": [], "total_encontrado": 0}, status_code=500)

    try:
        vehicles = data["veiculos"]
        if not isinstance(vehicles, list):
             return JSONResponse(content={"error": "Formato de dados inválido (veiculos não é uma lista)", "resultados": [], "total_encontrado": 0}, status_code=500)
    except KeyError:
        return JSONResponse(content={"error": "Formato de dados inválido (chave 'veiculos' não encontrada)", "resultados": [], "total_encontrado": 0}, status_code=500)

    query_params = dict(request.query_params)
    valormax = query_params.pop("ValorMax", None)

    filtros_originais = {
        "modelo": query_params.get("modelo"),
        "marca": query_params.get("marca"),
        "categoria": query_params.get("categoria")
    }
    filtros_ativos = {k: v for k, v in filtros_originais.items() if v}

    # Usar a função original para manter compatibilidade
    resultado = filtrar_veiculos(vehicles, filtros_ativos, valormax)

    if resultado:
        return JSONResponse(content={
            "resultados": resultado,
            "total_encontrado": len(resultado)
        })

    # Lógica de busca alternativa (mantida do código original)
    alternativas = []
    filtros_alternativa1 = {k: v for k, v in filtros_originais.items() if v}
    
    alt1 = filtrar_veiculos(vehicles, filtros_alternativa1)
    if alt1:
        alternativas = alt1
    else:
        if filtros_originais.get("modelo"):
            filtros_so_modelo = {"modelo": filtros_originais["modelo"]}
            alt2 = filtrar_veiculos(vehicles, filtros_so_modelo, valormax)
            if alt2:
                alternativas = alt2
            else:
                modelo_para_inferencia = filtros_originais.get("modelo")
                if modelo_para_inferencia:
                    categoria_inferida = inferir_categoria_por_modelo(modelo_para_inferencia)
                    if categoria_inferida:
                        filtros_categoria_inferida = {"categoria": categoria_inferida}
                        alt3 = filtrar_veiculos(vehicles, filtros_categoria_inferida, valormax)
                        if alt3:
                            alternativas = alt3
                        else:
                            alt4 = filtrar_veiculos(vehicles, filtros_categoria_inferida)
                            if alt4:
                                alternativas = alt4
    
    if alternativas:
        alternativas_formatadas = [
            {"titulo": v.get("titulo", ""), "preco": v.get("preco", "")}
            for v in alternativas[:10] 
        ]
        return JSONResponse(content={
            "resultados": [],
            "total_encontrado": 0,
            "instrucao_ia": "Não encontramos veículos com os parâmetros informados dentro do valor desejado. Seguem as opções mais próximas.",
            "alternativa": {
                "resultados": alternativas_formatadas,
                "total_encontrado": len(alternativas_formatadas) 
            }
        })

    return JSONResponse(content={
        "resultados": [],
        "total_encontrado": 0,
        "instrucao_ia": "Não encontramos veículos com os parâmetros informados e também não encontramos opções próximas."
    })

# Função original mantida para compatibilidade
def filtrar_veiculos(vehicles, filtros, valormax=None):
    """Função original mantida para compatibilidade com endpoints existentes"""
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
            palavras_query_originais = valor_filtro.split()
            palavras_query_normalizadas = [normalizar(p) for p in palavras_query_originais if p.strip()]
            palavras_query_normalizadas = [p for p in palavras_query_normalizadas if p]

            if not palavras_query_normalizadas:
                vehicles_processados = [] 
                break 

            for v in vehicles_processados:
                vehicle_score_for_this_filter = 0.0
                vehicle_matched_words_for_this_filter = 0

                for palavra_q_norm in palavras_query_normalizadas:
                    if not palavra_q_norm: 
                        continue
                    
                    best_score_for_this_q_word_in_vehicle = 0.0
                    
                    for nome_campo_fuzzy_veiculo in campos_fuzzy: 
                        conteudo_original_campo_veiculo = v.get(nome_campo_fuzzy_veiculo, "")
                        if not conteudo_original_campo_veiculo: 
                            continue
                        texto_normalizado_campo_veiculo = normalizar(str(conteudo_original_campo_veiculo))
                        if not texto_normalizado_campo_veiculo: 
                            continue

                        current_field_match_score = 0.0
                        if palavra_q_norm in texto_normalizado_campo_veiculo:
                            current_field_match_score = 100.0
                        elif len(palavra_q_norm) >= 4:
                            score_partial = fuzz.partial_ratio(texto_normalizado_campo_veiculo, palavra_q_norm)
                            score_ratio = fuzz.ratio(texto_normalizado_campo_veiculo, palavra_q_norm)
                            
                            achieved_score = max(score_partial, score_ratio)
                            if achieved_score >= 75:
                                current_field_match_score = achieved_score
                        
                        if current_field_match_score > best_score_for_this_q_word_in_vehicle:
                            best_score_for_this_q_word_in_vehicle = current_field_match_score
                    
                    if best_score_for_this_q_word_in_vehicle > 0:
                        vehicle_score_for_this_filter += best_score_for_this_q_word_in_vehicle
                        vehicle_matched_words_for_this_filter += 1
                
                if vehicle_matched_words_for_this_filter > 0:
                    v['_relevance_score'] += vehicle_score_for_this_filter
                    v['_matched_word_count'] += vehicle_matched_words_for_this_filter
                    veiculos_que_passaram_nesta_chave.append(v)
        
        else:
            termo_normalizado_para_comparacao = normalizar(valor_filtro)
            for v in vehicles_processados:
                valor_campo_veiculo = v.get(chave_filtro, "")
                if normalizar(str(valor_campo_veiculo)) == termo_normalizado_para_comparacao:
                    veiculos_que_passaram_nesta_chave.append(v)
        
        vehicles_processados = veiculos_que_passaram_nesta_chave
        if not vehicles_processados:
            break

    if active_fuzzy_filter_applied:
        vehicles_processados = [v for v in vehicles_processados if v['_matched_word_count'] > 0]

    if active_fuzzy_filter_applied:
        vehicles_processados.sort(
            key=lambda v: (
                v['_matched_word_count'], 
                v['_relevance_score'],
                get_price_for_sort(v.get("preco")) 
            ),
            reverse=True
        )
    else:
        vehicles_processados.sort(
            key=lambda v: get_price_for_sort(v.get("preco")),
            reverse=True
        )
    
    if valormax:
        try:
            teto = float(valormax)
            max_price_limit = teto * 1.3 
            
            vehicles_filtrados_preco = []
            for v_dict in vehicles_processados:
                price = converter_preco(v_dict.get("preco"))
                if price is not None and price <= max_price_limit:
                    vehicles_filtrados_preco.append(v_dict)
            vehicles_processados = vehicles_filtrados_preco
        except ValueError:
            return [] 

    for v in vehicles_processados:
        v.pop('_relevance_score', None)
        v.pop('_matched_word_count', None)

    return vehicles_processados
