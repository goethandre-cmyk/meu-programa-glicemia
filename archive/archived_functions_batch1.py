# Arquivo gerado automaticamente: cópias de funções marcadas como candidatas a remoção
# Data: 2026-04-11
# Conteúdo arquivado (não importado automaticamente). Mantido para revisão manual antes de remoção.

# --- Trechos de logica.py (AppCore) ---
import os
import json

class AppCore_Archived:
    def _carregar_alimentos_json(self):
        """Carrega os dados de alimentos de um arquivo JSON."""
        filepath = 'data/alimentos.json'

        print(f"DEBUG: Procurando o arquivo em: {os.path.abspath(filepath)}")

        if not os.path.exists(filepath):
            print(f"AVISO: O arquivo '{filepath}' NÃO foi encontrado. A busca por alimentos não funcionará.")
            return {"alimentos": []}

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                dados = json.load(f)

                # Se o arquivo JSON for uma lista, o envolvemos em um dicionário
                if isinstance(dados, list):
                    print(f"INFO: O arquivo '{filepath}' foi carregado com sucesso. Total de registros: {len(dados)}")
                    return {"alimentos": dados}
                # Se já for um dicionário com a chave 'alimentos', retorna-o
                elif isinstance(dados, dict) and "alimentos" in dados:
                    print(f"INFO: O arquivo '{filepath}' foi carregado com sucesso. Total de registros: {len(dados['alimentos'])}")
                    return dados
                else:
                    # Se não for uma lista ou um dicionário válido, o formato está incorreto.
                    print(f"ERRO: O arquivo '{filepath}' tem um formato inesperado. Esperada uma lista de alimentos ou um dicionário com a chave 'alimentos'.")
                    return {"alimentos": []}

        except (IOError, json.JSONDecodeError) as e:
            print(f"ERRO: Não foi possível ler o arquivo '{filepath}'. Ele pode estar corrompido ou com formato inválido. Erro: {e}")
            return {"alimentos": []}

    def salvar_alimento_json(self, novo_alimento):
        """Salva um novo alimento no arquivo JSON."""
        # Verifica se o alimento já existe
        for alimento in self.alimentos_db["alimentos"]:
            if alimento["ALIMENTO"].lower() == novo_alimento["ALIMENTO"].lower():
                return False  # Alimento já existe, não salva

        self.alimentos_db["alimentos"].append(novo_alimento)
        try:
            # Salva no arquivo original
            with open('data/alimentos.json', 'w', encoding='utf-8') as f:
                json.dump(self.alimentos_db, f, ensure_ascii=False, indent=4)
            return True
        except IOError:
            return False

# --- Trechos de database_manager.py ---
import os
import json

def _load_json_data_archived(db_path):
    """Carrega os dados de um arquivo JSON (modelo antigo) para migração."""
    json_path = os.path.join(os.path.dirname(db_path), 'data.json')
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print("Aviso: Arquivo data.json está corrompido ou vazio.")
            return {}
    return {}


def _migrate_json_to_sqlite_archived(db_manager):
    json_data = _load_json_data_archived(db_manager.db_path)
    if not json_data:
        return

    print("Iniciando a migração dos dados do JSON para o SQLite...")

    with db_manager.get_db_connection() as conn:
        cursor = conn.cursor()

        # Migrar usuários (AJUSTADO para TODAS as 17 colunas)
        users_migrated_count = 0
        for user in json_data.get('users', []):
            try:
                cursor.execute("SELECT id FROM users WHERE username = ?", (user['username'],))
                if cursor.fetchone():
                    continue
            except Exception:
                pass

# Fim do arquivo arquivado
