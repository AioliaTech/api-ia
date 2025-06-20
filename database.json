# update_vocabulary.py
import requests
import json
import logging
from typing import Dict, Set, Optional, Any, List

# Configura o logging para vermos o progresso
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

FIPE_API_BASE_URL = "https://parallelum.com.br/fipe/api/v1/carros/marcas"
OUTPUT_FILE_NAME = "fipe_vocabulary.json"

def get_from_fipe_api(url: str) -> Optional[Any]:
    """Faz uma requisição para a API FIPE, tratando possíveis erros."""
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()  # Lança um erro para status HTTP 4xx/5xx
        return response.json()
    except requests.RequestException as e:
        logging.error(f"Erro ao acessar a URL {url}: {e}")
        return None

def build_vocabulary():
    """Busca todas as marcas, modelos e versões da FIPE e salva em um arquivo JSON."""
    logging.info("Iniciando a criação do vocabulário para o SpaCy a partir da API FIPE.")
    
    # Usamos 'sets' para evitar duplicatas automaticamente
    vocabulary: Dict[str, Set[str]] = {
        "marcas": set(),
        "modelos": set(),
        "versoes": set()
    }
    
    marcas = get_from_fipe_api(FIPE_API_BASE_URL)
    if not marcas:
        logging.critical("Falha fatal ao buscar a lista de marcas. Abortando.")
        return

    total_marcas = len(marcas)
    for i, marca in enumerate(marcas):
        marca_nome = marca['nome']
        marca_codigo = marca['codigo']
        logging.info(f"Processando Marca {i+1}/{total_marcas}: {marca_nome}")
        
        # Adiciona a marca à nossa lista
        vocabulary["marcas"].add(marca_nome.lower())
        
        modelos_data = get_from_fipe_api(f"{FIPE_API_BASE_URL}/{marca_codigo}/modelos")
        
        # A API da FIPE é um pouco inconsistente. Precisamos verificar se os dados existem.
        if not modelos_data:
            logging.warning(f"Não foram encontrados modelos para a marca {marca_nome}.")
            continue
            
        # Extrai os MODELOS BASE (ex: "Onix", "HB20", "Mobi")
        if 'anos' in modelos_data:
            for modelo_base in modelos_data['anos']:
                vocabulary["modelos"].add(modelo_base['nome'].lower())

        # Extrai as VERSÕES COMPLETAS (ex: "ONIX HATCH LT 1.0 8V FLEXPOWER 5P MEC.")
        if 'modelos' in modelos_data:
            for versao_completa in modelos_data['modelos']:
                 vocabulary["versoes"].add(versao_completa['nome'].lower())
    
    # Converte os sets para listas ordenadas para um arquivo JSON limpo e consistente
    final_vocabulary: Dict[str, List[str]] = {
        key: sorted(list(value)) for key, value in vocabulary.items()
    }
    
    logging.info("Busca finalizada.")
    logging.info(f"Total de Marcas únicas: {len(final_vocabulary['marcas'])}")
    logging.info(f"Total de Modelos únicos: {len(final_vocabulary['modelos'])}")
    logging.info(f"Total de Versões únicas: {len(final_vocabulary['versoes'])}")
    
    logging.info(f"Salvando vocabulário no arquivo: {OUTPUT_FILE_NAME}")
    with open(OUTPUT_FILE_NAME, "w", encoding="utf-8") as f:
        json.dump(final_vocabulary, f, ensure_ascii=False, indent=2)
        
    logging.info("Processo de criação de vocabulário concluído com sucesso!")

if __name__ == "__main__":
    build_vocabulary()
