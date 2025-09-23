import sqlite3
import csv
import os

# Define o caminho absoluto para o banco de dados e para o arquivo CSV
base_dir = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(base_dir, 'data', 'glicemia.db')
CSV_PATH = os.path.join(base_dir, 'data', 'alimentos_id.csv')

def importar_alimentos():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS alimentos (
            id INTEGER PRIMARY KEY,
            alimento TEXT UNIQUE NOT NULL,
            medida_caseira TEXT,
            peso REAL,
            kcal REAL,
            carbs REAL
        )
    ''')
    conn.commit()

    if not os.path.exists(CSV_PATH):
        print(f"Erro: O arquivo '{CSV_PATH}' não foi encontrado.")
        conn.close()
        return

    try:
        # Tente ler com a codificação correta
        with open(CSV_PATH, 'r', encoding='latin-1') as file:
            # Usa o delimitador de ponto e vírgula
            reader = csv.reader(file, delimiter=';', quotechar='"')
            
            # Pula a primeira linha (cabeçalho)
            next(reader)
            
            alimentos_a_inserir = []
            for row in reader:
                # Agora o script aceita linhas com 5 ou mais colunas
                if len(row) >= 6: # Agora o script espera pelo menos 6 colunas
                    try:
                        # Converte os valores numéricos para float
                        alimento_dados = (
                            row[1], # Nome do alimento
                            row[2], # Medida caseira
                            float(row[3].replace(',', '.').replace('-', '0') if row[3] else 0), # Peso
                            float(row[4].replace(',', '.').replace('-', '0') if row[4] else 0), # Kcal
                            float(row[5].replace(',', '.').replace('-', '0') if row[5] else 0)  # Carbs
                        )
                        alimentos_a_inserir.append(alimento_dados)
                    except (ValueError, IndexError) as e:
                        print(f"Erro de conversão de dados na linha: {row}. Erro: {e}")
                else:
                    print(f"Linha ignorada por ter número de colunas inválido: {row}")


            # Usa o comando executemany para inserir todos de uma vez
            cursor.executemany('''
                INSERT OR IGNORE INTO alimentos (alimento, medida_caseira, peso, kcal, carbs)
                VALUES (?, ?, ?, ?, ?)
            ''', alimentos_a_inserir)
            
            conn.commit()
            print(f"Sucesso! {cursor.rowcount} alimentos foram importados para o banco de dados.")

    except sqlite3.Error as e:
        print(f"Erro ao importar dados: {e}")
    except IOError as e:
        print(f"Erro de leitura do arquivo: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    # Apaga o banco de dados existente antes de criar um novo
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"Banco de dados '{DB_PATH}' excluído para garantir uma nova importação.")
        
    importar_alimentos()