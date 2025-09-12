# migrar_alimentos.py

import os
import csv
import json

# Define os caminhos dos arquivos
ALIMENTOS_CSV_FILE = os.path.join('data', 'alimentos.csv')
ALIMENTOS_JSON_FILE = os.path.join('data', 'alimentos.json')

def migrar_csv_para_json():
    """
    Lê os dados do arquivo CSV e salva em um arquivo JSON.
    """
    alimentos = []
    
    # 1. Lê os dados do arquivo CSV
    try:
        with open(ALIMENTOS_CSV_FILE, 'r', encoding='utf-8') as f:
            # Usa DictReader para ler cada linha como um dicionário
            reader = csv.DictReader(f, delimiter=';')
            for row in reader:
                # Transforma a linha do CSV em um dicionário mais limpo, se necessário.
                # Aqui, estamos mantendo a estrutura original.
                alimentos.append(row)
        print(f"Lidas {len(alimentos)} linhas do arquivo CSV.")
    except FileNotFoundError:
        print(f"Erro: O arquivo {ALIMENTOS_CSV_FILE} não foi encontrado.")
        return False
    
    # 2. Salva a lista de dicionários no arquivo JSON
    try:
        with open(ALIMENTOS_JSON_FILE, 'w', encoding='utf-8') as f:
            json.dump(alimentos, f, indent=4, ensure_ascii=False)
        print(f"Dados salvos com sucesso em {ALIMENTOS_JSON_FILE}.")
        return True
    except Exception as e:
        print(f"Erro ao salvar o arquivo JSON: {e}")
        return False

if __name__ == "__main__":
    migrar_csv_para_json()
