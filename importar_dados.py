import sqlite3
import csv
import os

DB_PATH = 'app.db'
CSV_PATH = os.path.join('data', 'alimentos.csv')

def importar_alimentos():
    # Conecta ao banco de dados (será criado se não existir)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Cria a tabela se ela ainda não existir
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

    with open(CSV_PATH, 'r', encoding='latin-1') as file:
        # Usa o delimitador de tabulação
        reader = csv.reader(file, delimiter='\t')
        
        # Pula a primeira linha (cabeçalho)
        next(reader)
        
        alimentos_a_inserir = []
        for row in reader:
            # Verifica se a linha tem o número de colunas esperado
            if len(row) == 5:
                alimento = (row[0], row[1], row[2], row[3], row[4])
                alimentos_a_inserir.append(alimento)
            else:
                # Loga a linha que causou o problema para depuração
                print(f"Linha ignorada por ter número de colunas inválido: {row}")

        try:
            # Usa o comando executemany para inserir todos de uma vez
            cursor.executemany('''
                INSERT OR IGNORE INTO alimentos (alimento, medida_caseira, peso, kcal, carbs)
                VALUES (?, ?, ?, ?, ?)
            ''', alimentos_a_inserir)
            conn.commit()
            print(f"Sucesso! {cursor.rowcount} alimentos foram importados para o banco de dados.")
        except sqlite3.Error as e:
            print(f"Erro ao importar dados: {e}")
        finally:
            conn.close()

if __name__ == '__main__':
    # Exclua o banco de dados antes de rodar o script
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"Banco de dados '{DB_PATH}' excluído para garantir uma nova importação.")
        
    importar_alimentos()