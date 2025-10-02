import os
import sqlite3
import json
from sqlite3 import Row 
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta 
LIMITE_HIPO = 70
LIMITE_HIPER = 180
class DatabaseManager:
    def __init__(self, db_path='glicemia.db'):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        db_folder = os.path.join(base_dir, 'data')
        os.makedirs(db_folder, exist_ok=True)
        self.db_path = os.path.join(db_folder, db_path)
        
        # Chamadas agora devem funcionar:
        self.inicializar_db() 
        self.add_new_columns() # Certifique-se que esta função também esteja dentro da classe.
        self._migrate_json_to_sqlite() # Certifique-se que esta função também esteja dentro da classe.

    def get_db_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.row_factory = sqlite3.Row
        return conn
        
    def _load_json_data(self) -> dict:
        """Carrega os dados de um arquivo JSON (modelo antigo) para migração."""
        json_path = os.path.join(os.path.dirname(self.db_path), 'data.json')
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                print("Aviso: Arquivo data.json está corrompido ou vazio.")
                return {}
        return {}

    # 🚨 CORREÇÃO CRÍTICA: ESTE MÉTODO DEVE ESTAR DENTRO DA CLASSE
    def inicializar_db(self): 
        """Cria as tabelas do banco de dados se elas não existirem."""
        
        with sqlite3.connect(self.db_path) as conn: 
            cursor = conn.cursor()
            
            # --- 1. Tabela de Usuários (usuarios) ---
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    email TEXT,
                    role TEXT NOT NULL DEFAULT 'simples',
                    data_nascimento TEXT,
                    sexo TEXT,
                    razao_ic REAL,
                    fator_sensibilidade REAL,
                    meta_glicemia REAL,
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # --- 2. Tabela de Registros (registros) ---
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS registros (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    data_hora TIMESTAMP NOT NULL,
                    tipo TEXT,
                    valor REAL,
                    carboidratos REAL,
                    observacoes TEXT,
                    alimentos_refeicao TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                );
            """)
            
            # --- 3. Outras Tabelas (log_acoes, fichas_medicas, agendamentos) ---
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS log_acoes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    acao TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS fichas_medicas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    paciente_id INTEGER NOT NULL UNIQUE,
                    condicao_atual TEXT,
                    alergias TEXT,
                    historico_familiar TEXT,
                    medicamentos_uso TEXT,
                    FOREIGN KEY (paciente_id) REFERENCES users(id)
                );
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS agendamentos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    paciente_id INTEGER NOT NULL,
                    medico_id INTEGER NOT NULL,
                    data_hora TEXT NOT NULL,
                    observacoes TEXT,
                    status TEXT NOT NULL DEFAULT 'agendado',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (paciente_id) REFERENCES users(id),
                    FOREIGN KEY (medico_id) REFERENCES users(id)
                );
            """)
            
            conn.commit()



    def add_new_columns(self):
        """Adiciona novas colunas necessárias ao esquema do DB (migration)."""
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        # Lista de colunas a tentar adicionar: (coluna, tipo)
        columns_to_add = [
            ('nome_completo', 'TEXT'),
            ('telefone', 'TEXT'),
            ('medico_id', 'INTEGER')
        ]
        
        for col_name, col_type in columns_to_add:
            try:
                cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type};")
                print(f"Coluna '{col_name}' adicionada à tabela users.")
            except sqlite3.OperationalError as e:
                if 'duplicate column name' in str(e):
                    pass # Coluna já existe, ignora
                else:
                    raise 
                    
        conn.commit()
        conn.close()

    def _migrate_json_to_sqlite(self):
        json_data = self._load_json_data()
        if not json_data:
            return

        print("Iniciando a migração dos dados do JSON para o SQLite...")
        
        # Certifique-se de importar o módulo 'json' e 'datetime' se ainda não o fez.
        # import json
        # from datetime import datetime 
        
        with self.get_db_connection() as conn:
            cursor = conn.cursor()

            # Migrar usuários (AJUSTADO para TODAS as 17 colunas)
            users_migrated_count = 0
            for user in json_data.get('users', []):
                # O bloco try/except é sugerido para capturar erros de integridade (e.g., username duplicado)
                try:
                    cursor.execute("SELECT id FROM users WHERE username = ?", (user['username'],))
                    if cursor.fetchone():
                        continue
                    
                    # 1. Ajuste a lista de colunas para incluir TODAS as 17 colunas
                    cursor.execute("""
                        INSERT INTO users (
                            id, username, password_hash, role, email, nome_completo, 
                            razao_ic, fator_sensibilidade, data_nascimento, sexo, 
                            telefone, medico_id, meta_glicemia, documento, 
                            crm, cns, especialidade
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        # 2. Forneça 17 valores na ORDEM EXATA
                        user['id'], 
                        user['username'], 
                        user['password_hash'], 
                        user.get('role', 'paciente'), 
                        user.get('email'), 
                        user.get('nome'), # Mapeia 'nome' do JSON para 'nome_completo'
                        user.get('razao_ic'), 
                        user.get('fator_sensibilidade'), 
                        user.get('data_nascimento'), 
                        user.get('sexo'),
                        user.get('telefone'), 
                        user.get('medico_id'), 
                        # Novos campos, preenchidos com None se não estiverem no JSON
                        user.get('meta_glicemia'), 
                        user.get('documento'),
                        user.get('crm'),
                        user.get('cns'),
                        user.get('especialidade') 
                    ))
                    users_migrated_count += 1
                except sqlite3.Error as e:
                    print(f"Erro ao migrar usuário {user.get('username')}: {e}")
            
            # Migrar registros (Sem alteração, está correto)
            registros_migrated_count = 0
            # ... (O restante da sua lógica de migração de registros está correta e inalterada)
            for registro in json_data.get('registros_glicemia_refeicao', []):
                cursor.execute("SELECT id FROM registros WHERE id = ?", (registro.get('id',-1),))
                if cursor.fetchone():
                    continue
                
                # Importação de datetime e json é necessária aqui se o código estiver fora do escopo
                try:
                    from datetime import datetime
                except ImportError:
                    pass # Assumindo que já está importado ou não é estritamente necessário para o exemplo.

                data_hora = registro.get('data_hora') or datetime.now().isoformat()
                tipo = registro.get('tipo') or 'Desconhecido'

                alimentos_json_str = json.dumps(registro.get('alimentos')) if registro.get('alimentos') else None
                
                cursor.execute("""
                    INSERT INTO registros (id, user_id, data_hora, tipo, valor, observacoes, alimentos_json, total_calorias, total_carbs)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (registro.get('id'), registro['user_id'], data_hora, tipo, registro.get('valor'), registro.get('observacoes'), alimentos_json_str, registro.get('total_calorias'), registro.get('total_carbs')))
                registros_migrated_count += 1

            conn.commit()
            print(f"Migração concluída! {users_migrated_count} usuários e {registros_migrated_count} registros migrados.")

    def criar_paciente_e_ficha_inicial(self, paciente_data, medico_id, anamnese_data):
        """
        Cria um novo paciente na tabela users e a primeira ficha médica (anamnese)
        em uma única transação, vinculando ao médico.
        """
        conn = self.get_db_connection()
        try:
            # 1. Tentar inserir o paciente
            cursor = conn.execute(
                """
                INSERT INTO users (
                    username, password_hash, role, email, nome_completo, data_nascimento, 
                    sexo, medico_id, telefone, razao_ic, fator_sensibilidade
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    paciente_data['username'],
                    paciente_data['password_hash'],
                    'paciente', # Forçando o role
                    paciente_data.get('email'),
                    paciente_data.get('nome_completo'),
                    paciente_data.get('data_nascimento'),
                    paciente_data.get('sexo'),
                    medico_id, # O ID do médico logado
                    paciente_data.get('telefone'),
                    paciente_data.get('razao_ic', 1.0),
                    paciente_data.get('fator_sensibilidade', 1.0)
                )
            )
            paciente_id = cursor.lastrowid

            # 2. Inserir a primeira ficha médica (Anamnese)
            conn.execute(
                """
                INSERT INTO ficha_medica (
                    user_id, medico_id, data_registro, tipo_diabetes, data_diagnostico,
                    historico_familiar, outras_comorbidades
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    paciente_id,
                    medico_id,
                    datetime.now().isoformat(),
                    anamnese_data.get('tipo_diabetes'),
                    anamnese_data.get('data_diagnostico'),
                    anamnese_data.get('historico_familiar'),
                    anamnese_data.get('outras_comorbidades')
                )
            )
            
            # 3. Criar o vínculo na tabela de vinculos_medico_paciente (Melhoria de robustez)
            conn.execute(
                "INSERT OR IGNORE INTO vinculos_medico_paciente (medico_id, paciente_id) VALUES (?, ?)",
                (medico_id, paciente_id)
            )
            
            conn.commit()
            return True
        
        except sqlite3.IntegrityError as e:
            # Username já existe ou outro erro de integridade (ex: Foreign Key falha)
            conn.rollback()
            print(f"Integrity Error: {e}")
            return False
        except Exception as e:
            # Erro genérico
            conn.rollback()
            print(f"Erro ao criar paciente e ficha: {e}")
            return False
        finally:
            conn.close()

    def carregar_usuario(self, username):
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
            user_data = cursor.fetchone()
            return dict(user_data) if user_data else None
        
    def carregar_usuario_por_username(self, username):
        """Busca um usuário pelo nome de usuário e retorna um objeto User."""
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        # 1. Busca o usuário pelo username
        cursor.execute("SELECT id, username, password_hash, role FROM usuarios WHERE username = ?", (username,))
        user_data = cursor.fetchone()
        conn.close()
        
        if user_data:
            # 2. Desempacota os dados
            id, username, password_hash, role = user_data
            
            # 3. Retorna um objeto da sua classe User
            # É crucial que este objeto User seja compatível com o Flask-Login
            # Substitua 'User' pela sua classe real de usuário, se for diferente.
            # Exemplo simplificado:
            from models import User # Se sua classe User estiver em models.py
            return User(id=id, username=username, password_hash=password_hash, role=role)
        
        return None

    def carregar_usuario_por_id(self, user_id):
        conn = self.get_db_connection()
        user_data = conn.execute(
            "SELECT id, username, role, email, nome_completo, razao_ic, fator_sensibilidade, data_nascimento, sexo, telefone, medico_id FROM users WHERE id = ?", 
            (user_id,)
        ).fetchone()
        conn.close()
        return dict(user_data) if user_data else None
            
    def carregar_todos_os_usuarios(self, perfil=None):
        conn = self.get_db_connection()
        cursor = conn.cursor()
        query = "SELECT id, username, role FROM users"
        params = ()
        if perfil:
            query += " WHERE role = ?" # Corrigi para 'role' ao invés de 'perfil'
            params = (perfil,)
        
        cursor.execute(query, params)
        usuarios = cursor.fetchall()
        conn.close()
        return [{'id': row['id'], 'username': row['username'], 'role': row['role']} for row in usuarios]

    def salvar_log_acao(self, acao, usuario):
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO logs_acao (data_hora, acao, usuario) VALUES (?, ?, ?)", 
                            (datetime.now().isoformat(), acao, usuario))
            conn.commit()
            return True

    def get_user_id_by_username(self, username):
        conn = self.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
        user_id = cursor.fetchone()
        conn.close()
        return user_id[0] if user_id else None

    def salvar_usuario(self, user_data):
        if self.carregar_usuario(user_data['username']):
            return False
        
        # O valor do medico_id será None se não estiver presente (ex: para um Admin ou Médico novo)
        medico_id_value = user_data.get('medico_id')
        
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO users (
                    username, password_hash, role, email, nome_completo, 
                    razao_ic, fator_sensibilidade, data_nascimento, sexo, 
                    telefone, medico_id  -- <<< CAMPO ADICIONADO AQUI
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) -- <<< UM '?' A MAIS AQUI
            """, (
                user_data['username'], 
                user_data['password_hash'], 
                user_data.get('role', 'paciente'), 
                user_data.get('email'), 
                user_data.get('nome_completo'), 
                user_data.get('razao_ic'), 
                user_data.get('fator_sensibilidade'), 
                user_data.get('data_nascimento'), 
                user_data.get('sexo'), 
                user_data.get('telefone'),
                medico_id_value # <<< VALOR ADICIONADO AQUI
            ))
            conn.commit()
            return True

    def atualizar_usuario(self, user_data):
        # CRÍTICO: O password_hash DEVE ser carregado/calculado no Flask (app.py) 
        # e estar presente no user_data para que esta função o use.
        
        # Lista de colunas a serem atualizadas (Removi o 'username'!)
        # Adicionei 'password_hash' na primeira posição após 'email'
        colunas_set = [
            'email', 'password_hash', 'nome_completo', 'role', 
            'data_nascimento', 'sexo', 'telefone', 
            'razao_ic', 'fator_sensibilidade', 'meta_glicemia', 
            'documento', 'crm', 'cns', 'especialidade',
            'medico_id' # <<< CORREÇÃO: COLUNA 'medico_id' ADICIONADA AQUI
        ]
        
        # 1. Ajuste a QUERY para refletir as colunas corretas (Sem username, Com password_hash)
        set_clauses = ', '.join([f"{c} = ?" for c in colunas_set])
        query = f"""UPDATE users SET {set_clauses} WHERE id = ?"""
        
        # Agora, set_clauses terá 15 colunas, e a query terá 15 `?` + 1 `?` (do WHERE).
        
        # 2. Monte a tupla de valores na ORDEM EXATA das colunas_set
        valores = (
            # Valores na ordem de colunas_set (15 valores):
            user_data.get('email'), 
            user_data.get('password_hash'), 
            user_data.get('nome_completo'),
            user_data.get('role'),
            user_data.get('data_nascimento'), 
            user_data.get('sexo'), 
            user_data.get('telefone'), 
            user_data.get('razao_ic'), 
            user_data.get('fator_sensibilidade'),
            user_data.get('meta_glicemia'),
            user_data.get('documento'),
            user_data.get('crm'),
            user_data.get('cns'),
            user_data.get('especialidade'),
            user_data.get('medico_id'), # <<< VALOR CORRESPONDENTE A COLUNA ADICIONADA
            
            # Condição WHERE (1 valor):
            user_data.get('id')
        )
        
        # O número total de valores (16) agora corresponde ao número total de `?` na query (16).
        
        # 3. Execução da Query
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, valores) 
                conn.commit()
                return cursor.rowcount > 0 # Retorna True se a linha foi atualizada
                
        except sqlite3.IntegrityError as e:
            # Erro de integridade ainda ocorrerá se o EMAIL for alterado 
            # para um email de outro usuário, mas não mais pelo username!
            print(f"Erro de Integridade (UNIQUE Constraint) ao atualizar: {e}")
            return False
            
        except Exception as e:
            print(f"Erro geral de DB ao atualizar usuário: {e}")
            return False
        
        def excluir_usuario(self, username):
            """Exclui um usuário e seus dados associados do banco de dados pelo username."""
            
            # ⚠️ IMPORTANTE: Dependendo da sua lógica, você pode precisar excluir 
            # todos os registros relacionados (glicemia, agendamentos, etc.) primeiro.
            # Excluir apenas da tabela 'users' pode violar restrições de chave estrangeira!
            
            # Se você não tem FKs definidos, ou se tem 'ON DELETE CASCADE', 
            # esta query é suficiente para a tabela 'users'.
            
            query = "DELETE FROM users WHERE username = ?"
            
            try:
                with self.get_db_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(query, (username,))
                    conn.commit()
                    
                    # Verifica se alguma linha foi realmente excluída
                    if cursor.rowcount > 0:
                        return True
                    return False
                    
            except Exception as e:
                # Se ocorrer um erro (ex: FK constraint), ele será capturado aqui.
                print(f"Erro ao excluir usuário '{username}': {e}")
                return False

# No seu database_manager.py, adicione:

    import sqlite3 # Certifique-se de importar o sqlite3

    def excluir_usuario_e_dados(self, username):
        """
        Exclui um usuário e TODOS os seus dados relacionados em uma transação segura.
        """
        # 1. Obter o ID do usuário primeiro
        user_data = self.carregar_usuario(username)
        if not user_data:
            return False
        user_id = user_data['id']
        
        # 2. Inicia a transação
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            try:
                # Lista de todas as operações de exclusão necessárias:
                
                # A. Excluir Registros de Glicemia
                cursor.execute("DELETE FROM registros_glicemia WHERE user_id = ?", (user_id,))
                
                # B. Excluir Fichas Médicas e Exames (se o usuário for um Paciente)
                cursor.execute("DELETE FROM fichas_medicas WHERE paciente_id = ?", (user_id,))
                cursor.execute("DELETE FROM exames_laboratoriais WHERE paciente_id = ?", (user_id,))

                # C. Excluir Vínculos (onde o usuário é o Paciente, Médico ou Cuidador)
                # Se for Paciente, remove todos os vínculos a ele
                cursor.execute("DELETE FROM vinculos_cuidador_paciente WHERE paciente_id = ?", (user_id,))
                cursor.execute("DELETE FROM vinculos_medico_paciente WHERE paciente_id = ?", (user_id,))
                
                # Se for Médico/Cuidador, remove os vínculos que ele criou
                cursor.execute("DELETE FROM vinculos_cuidador_paciente WHERE cuidador_id = ?", (user_id,))
                cursor.execute("DELETE FROM vinculos_medico_paciente WHERE medico_id = ?", (user_id,))
                
                # D. Excluir Agendamentos
                # Agendamentos criados pelo Paciente, ou Agendamentos onde ele é o Médico
                cursor.execute("DELETE FROM agendamentos WHERE paciente_id = ? OR medico_id = ?", (user_id, user_id))
                
                # E. Finalmente, excluir o próprio usuário
                cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
                
                # 3. Se tudo correu bem, confirma as alterações
                conn.commit()
                return True
                
            except Exception as e:
                # Se algo falhar (ex: erro de integridade de outra tabela), desfaz tudo
                print(f"Erro CRÍTICO na exclusão em cascata do usuário {username}: {e}")
                conn.rollback() 
                return False
    
    def carregar_resumo_geral(self):
        """Carrega as métricas gerais do sistema (Admin/Secretário)."""
        conn = self.get_db_connection()
        cursor = conn.cursor()
        resumo = {
            'total_pacientes': 0,
            'registros_hoje': 0,
            'media_glicemia_geral': 'N/A',
            'total_medicos': 0
        }
        
        # Use o formato de data/hora correto para a sua base de dados (ex: SQLite usa '%Y-%m-%d')
        hoje = datetime.now().strftime('%Y-%m-%d')

        try:
            # 1. Total de Pacientes e Médicos
            cursor.execute("SELECT COUNT(id) FROM usuarios WHERE role = 'paciente'")
            resumo['total_pacientes'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(id) FROM usuarios WHERE role = 'medico'")
            resumo['total_medicos'] = cursor.fetchone()[0]

            # 2. Registros de Glicemia Hoje
            cursor.execute("""
                SELECT COUNT(id) 
                FROM registros 
                WHERE DATE(data_hora) = ?
            """, (hoje,))
            resumo['registros_hoje'] = cursor.fetchone()[0]

            # 3. Média Global de Glicemia (de todos os registros)
            cursor.execute("SELECT AVG(valor) FROM registros")
            media = cursor.fetchone()[0]
            
            if media is not None:
                resumo['media_glicemia_geral'] = f"{media:.1f}"

        except Exception as e:
            print(f"Erro ao carregar resumo geral: {e}")

        finally:
            conn.close()
            
        return resumo
    def carregar_alimentos(self):
        """Carrega todos os alimentos da tabela 'alimentos'. (Presumindo que essa tabela exista, embora não esteja no CREATE TABLE)"""
        try:
             with self.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM alimentos ORDER BY alimento ASC")
                alimentos = cursor.fetchall()
                return [dict(row) for row in alimentos]
        except sqlite3.OperationalError:
            # Caso a tabela 'alimentos' ainda não tenha sido criada
            return []
        
    def salvar_alimento(self, alimento_data):
        """Salva um novo alimento no banco de dados. (Presumindo a tabela 'alimentos')"""
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO alimentos (alimento, medida_caseira, peso, kcal, carbs)
                    VALUES (?, ?, ?, ?, ?)
                """, (alimento_data['alimento'], alimento_data['medida_caseira'], alimento_data['peso'], alimento_data['kcal'], alimento_data['carbs']))
                conn.commit()
                return True
        except Exception as e:
            return False
    def buscar_alimentos_por_nome(self, termo):
            try:
                with self.get_db_connection() as conn:
                    cursor = conn.cursor()
                    
                    # A ORDEM É CRÍTICA: As colunas devem seguir a ordem que o Python espera
                    # 0: id, 1: ALIMENTO, 2: MEDIDA CASEIRA, 3: PESO (g/ml), 4: Kcal, 5: CHO (g)
                    cursor.execute(
                        """
                        SELECT 
                            id, 
                            ALIMENTO, 
                            MEDIDA_CASEIRA, 
                            PESO,    
                            Kcal, 
                            CARBS        -- ESTE É O ÍNDICE 5 QUE O PYTHON VAI LER
                        FROM alimentos 
                        WHERE ALIMENTO LIKE ? 
                        ORDER BY ALIMENTO ASC
                        """,
                        ('%' + termo + '%',)
                    )
                    alimentos_tuplas = cursor.fetchall()
                    
                    # Mapeamento do índice do SQL para a chave do Python:
                    alimentos_dict = []
                    for item in alimentos_tuplas:
                        # Garantindo que o 'cho' lê o valor do índice 5 (CHO (g))
                        alimentos_dict.append({
                            'id': item[0],                 
                            'alimento': item[1],           
                            'medida_caseira': item[2],     
                            'peso': item[3],               
                            'kcal': item[4],               
                            'carbs': item[5]                 
                        })
                    
                    return alimentos_dict
            except Exception as e:
                print(f"Erro CRÍTICO na busca de alimentos: {e}")
                return []
    def salvar_registro(self, registro_data):
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO registros (user_id, data_hora, tipo, valor, observacoes, alimentos_json, total_calorias, total_carbs)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (registro_data['user_id'], registro_data['data_hora'], registro_data['tipo'], registro_data.get('valor'), registro_data.get('observacoes'), registro_data.get('alimentos_json'), registro_data.get('total_calorias'), registro_data.get('total_carbs')))
                conn.commit()
                return True
        except sqlite3.Error as e:
            print(f"ERRO DE SQL NO SALVAMENTO: {e}") # <-- Adicione esta linha!
            return False
    def carregar_registros(self, user_id):
        """
        Carrega todos os registros (glicemia e refeição) do usuário
        a partir da tabela unificada 'registros'.
        """
        # 🚨 CORREÇÃO: Buscar apenas na tabela 'registros'
        sql = """
            SELECT 
            id, 
            data_hora, 
            tipo, 
            valor, 
            observacoes, 
            alimentos_json,  /* 🚨 CORRIGIDO */
            total_calorias,
            total_carbs      /* 🚨 NOME CORRETO PARA CARBOIDRATOS */
        FROM registros 
        WHERE user_id = ?
        ORDER BY data_hora DESC
    """
        with self.get_db_connection() as conn:
        # Nota: Você não precisa redefinir conn.row_factory aqui se já o fez em get_db_connection
            cursor = conn.cursor() 
        try:
            cursor.execute(sql, (user_id,)) 
            registros = cursor.fetchall()
            
            # Retorna a lista de dicionários
            return [dict(row) for row in registros]
            
        except sqlite3.OperationalError as e:
            # Captura erros como 'no such column' se o esquema do DB estiver desatualizado
            print(f"Erro ao carregar registros: {e}")
            return []
        
    # No database_manager.py, dentro da class DatabaseManager

    def salvar_glicemia(self, user_id, valor, data_hora, tipo, observacao):
        print(f"--- INICIANDO SALVAMENTO PARA USER ID: {user_id} ---") 
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        # DEBUG: Confirmação do ID do usuário.
        print(f"DEBUG DB: user_id atual: {user_id}")
        if user_id is None:
            print("ALERTA: user_id é None.")
            return False

        sql = """
            INSERT INTO registros 
            (user_id, data_hora, tipo, valor, observacoes, alimentos_json, total_calorias, total_carbs)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        try:
            cursor.execute(sql, (
                user_id, 
                data_hora, 
                tipo, 
                valor, 
                observacao, 
                None,        
                None,        
                None         
            ))
            
            # 🚨 O PROBLEMA ESTÁ NESTE PONTO (commit falha)
            conn.commit() 
            print(f"DEBUG DB: INSERT BEM-SUCEDIDO. User ID: {user_id}")
            return True 
            
        except sqlite3.Error as e:
            conn.rollback()
            # 🚨 Se o erro for capturado, ele nos dará a resposta
            print(f"ERRO SQLITE REAL: {e}") 
            return False
        finally:
            conn.close()
    def encontrar_registo(self, registo_id): # <-- Parâmetro: registo_id
        """Busca um registro (glicemia/refeição) pelo seu ID."""
        try:
            # Usando 'with' para garantir que a conexão seja fechada automaticamente
            with self.get_db_connection() as conn:
                # Garante que os resultados possam ser acessados por nome da coluna
                conn.row_factory = sqlite3.Row 
                cursor = conn.cursor()
                
                # A tabela 'registros' está correta. A variável agora está corrigida.
                sql = "SELECT * FROM registros WHERE id = ?"
                
                # 🚨 CORREÇÃO AQUI: Mudança de (registos_id,) para (registo_id,)
                cursor.execute(sql, (registo_id,)) 
                
                registro = cursor.fetchone()
                
                return dict(registro) if registro else None
        
        except Exception as e:
            # Use a variável de parâmetro aqui se precisar depurar, ou apenas uma string
            print(f"ERRO DB ao encontrar registo: {e}") 
            return None
                
    def atualizar_registo(self, registro_data):
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE registros SET data_hora = ?, tipo = ?, valor = ?, observacoes = ?, alimentos_json = ?, total_calorias = ?, total_carbs = ?
                WHERE id = ?
            """, (registro_data['data_hora'], registro_data['tipo'], registro_data.get('valor'), registro_data.get('observacoes'), registro_data.get('alimentos_json'), registro_data.get('total_calorias'), registro_data.get('total_carbs'), registro_data['id']))
            conn.commit()
            return True
    # NO database_manager.py, DENTRO da classe DatabaseManager

    def atualizar_registro(self, registro_data):
        """
        Atualiza um registro existente no banco de dados com base no seu tipo (Glicemia ou Refeição).
        O parâmetro registro_data é um dicionário contendo 'id' e 'tipo'.
        """
        conn = None
        try:
            conn = self.get_db_connection() # Abre a conexão
            cursor = conn.cursor()
            registro_id = registro_data.get('id')
            tipo_principal = registro_data.get('tipo')

            if not registro_id or not tipo_principal:
                print("ERRO DB: ID ou Tipo principal ausente para atualização.")
                return False

            if tipo_principal == 'Glicemia':
                # Atualiza APENAS os campos de Glicemia + Comuns
                sql = """
                    UPDATE registros SET 
                        data_hora = ?, 
                        observacoes = ?, 
                        valor = ?,
                        tipo = ?,
                        tipo_medicao = ? 
                    WHERE id = ?
                """
                params = (
                    registro_data.get('data_hora'),
                    registro_data.get('observacoes'),
                    registro_data.get('valor'),
                    registro_data.get('tipo'),        # 'Glicemia'
                    registro_data.get('tipo_medicao'),# Adicione se for um campo que você usa
                    registro_id
                )
            
            elif tipo_principal == 'Refeição':
                # Atualiza APENAS os campos de Refeição + Comuns
                sql = """
                    UPDATE registros SET 
                        data_hora = ?, 
                        observacoes = ?, 
                        tipo = ?,
                        alimentos_json = ?, 
                        total_carbs = ?, 
                        total_calorias = ?,
                        tipo_refeicao = ? 
                    WHERE id = ?
                """
                params = (
                    registro_data.get('data_hora'),
                    registro_data.get('observacoes'),
                    registro_data.get('tipo'),        # 'Refeição'
                    registro_data.get('alimentos_json'),
                    registro_data.get('total_carbs'),
                    registro_data.get('total_calorias'),
                    registro_data.get('tipo_refeicao'), # O campo de dropdown
                    registro_id
                )
            else:
                print(f"ERRO DB: Tipo de registro desconhecido: {tipo_principal}")
                return False
                
            cursor.execute(sql, params)
            conn.commit()
            return cursor.rowcount > 0

        except Exception as e:
            print(f"ERRO DB ao atualizar registro {registro_id}: {e}")
            if conn:
                conn.rollback() # Reverte em caso de erro
            return False
        finally:
            if conn:
                conn.close() # Garante que a conexão seja fechada    

    def excluir_registro(self, registro_id):
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM registros WHERE id = ?", (registro_id,))
            conn.commit()
            return cursor.rowcount > 0

    def medico_tem_acesso_a_paciente(self, medico_id, paciente_id):
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            # Verifica se o paciente foi criado por esse médico ou se há um vínculo manual
            cursor.execute("""
                SELECT 1 FROM users WHERE id = ? AND medico_id = ?
                UNION
                SELECT 1 FROM vinculos_medico_paciente WHERE medico_id = ? AND paciente_id = ?
            """, (paciente_id, medico_id, medico_id, paciente_id))
            return cursor.fetchone() is not None
        
    def salvar_exame_laboratorial(self, ficha_exame: dict) -> bool:
        conn = self.get_db_connection()
        try:
            hb_a1c = float(ficha_exame.get('hb_a1c')) if ficha_exame.get('hb_a1c') else None
            glicose_jejum = int(ficha_exame.get('glicose_jejum')) if ficha_exame.get('glicose_jejum') else None
            colesterol_total = int(ficha_exame.get('colesterol_total')) if ficha_exame.get('colesterol_total') else None
            hdl = int(ficha_exame.get('hdl')) if ficha_exame.get('hdl') else None
            ldl = int(ficha_exame.get('ldl')) if ficha_exame.get('ldl') else None
            triglicerides = int(ficha_exame.get('triglicerides')) if ficha_exame.get('triglicerides') else None
            tsh = float(ficha_exame.get('tsh')) if ficha_exame.get('tsh') else None
            
            conn.execute("""
                INSERT INTO exames_laboratoriais (
                    paciente_id, data_exame, hb_a1c, glicose_jejum, colesterol_total, 
                    hdl, ldl, triglicerides, tsh, obs_medico
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ficha_exame.get('paciente_id'),
                ficha_exame.get('data_exame'), 
                hb_a1c, glicose_jejum, colesterol_total, hdl, ldl, triglicerides, tsh,
                ficha_exame.get('obs_medico')
            ))
            conn.commit()
            return True
        except Exception as e:
            print(f"Erro SQLite ao salvar exame laboratorial: {e}")
            return False
        finally:
            conn.close()

    def buscar_exames_paciente(self, paciente_id: int) -> list:
        conn = self.get_db_connection()
        exames = conn.execute("""
            SELECT * FROM exames_laboratoriais
            WHERE paciente_id = ?
            ORDER BY data_exame DESC
        """, (paciente_id,)).fetchall()
        
        result = [dict(row) for row in exames]
        conn.close()
        
        for exame in result:
            try:
                exame['data_exame'] = datetime.strptime(exame['data_exame'], '%Y-%m-%d')
            except (ValueError, TypeError):
                pass

        return result
    
    # Esta função está depreciada pela ficha_medica, mas mantida por compatibilidade
    # db_manager.py

    def salvar_ficha_medica(self, ficha_data):
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Mapeamento: Formulário HTML (ficha_data.get()) -> Coluna SQL
            historico_clinico = ficha_data.get('condicao_atual')
            medicacoes_atuais = ficha_data.get('medicamentos_uso')
            alergias = ficha_data.get('alergias')
            observacoes_medicas = ficha_data.get('historico_familiar')
            paciente_id = ficha_data['paciente_id']

            # UPDATE:
            cursor.execute("""
                UPDATE fichas_medicas 
                SET historico_clinico = ?, medicacoes_atuais = ?, alergias = ?, observacoes_medicas = ? 
                WHERE paciente_id = ?
                """,
                (historico_clinico, medicacoes_atuais, alergias, observacoes_medicas, paciente_id))
            
            # INSERT (se a linha não existir):
            if cursor.rowcount == 0:
                cursor.execute("""
                    INSERT INTO fichas_medicas (paciente_id, historico_clinico, medicacoes_atuais, alergias, observacoes_medicas) 
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (paciente_id, historico_clinico, medicacoes_atuais, alergias, observacoes_medicas))
            
            conn.commit()
            return True

    def carregar_ficha_medica(self, paciente_id):
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Seleciona as colunas na ordem correta
            cursor.execute("""
                SELECT historico_clinico, medicacoes_atuais, alergias, observacoes_medicas 
                FROM fichas_medicas 
                WHERE paciente_id = ?
            """, (paciente_id,))
            
            ficha = cursor.fetchone()
            
            if ficha:
                # 2. Retorna um dicionário mapeando os índices para os nomes do template
                return {
                    'condicao_atual': ficha[0],          # Mapeia para historico_clinico
                    'medicamentos_uso': ficha[1],        # Mapeia para medicacoes_atuais
                    'alergias': ficha[2],
                    'historico_familiar': ficha[3],      # Mapeia para observacoes_medicas
                }
            return None
            
    # Funções de Agendamento, Vínculos, etc. (Mantidas como no código original)
    def carregar_agendamentos_medico(self, medico_id):
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM agendamentos WHERE medico_id = ? ORDER BY data_hora", (medico_id,))
            agendamentos = cursor.fetchall()
            return [dict(row) for row in agendamentos]

    def carregar_agendamentos_paciente(self, paciente_id):
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM agendamentos WHERE paciente_id = ? ORDER BY data_hora", (paciente_id,))
            agendamentos = cursor.fetchall()
            return [dict(row) for row in agendamentos]
            
    def carregar_medicos(self):
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE role = 'medico'")
            medicos = cursor.fetchall()
            return [dict(row) for row in medicos]

    def salvar_agendamento(self, agendamento_data):
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO agendamentos (paciente_id, medico_id, data_hora, status)
                VALUES (?, ?, ?, ?)
            """, (agendamento_data['paciente_id'], agendamento_data['medico_id'], agendamento_data['data_hora'], agendamento_data['status']))
            conn.commit()
            return True

    def carregar_cuidadores(self):
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE role = 'cuidador'")
            cuidadores = cursor.fetchall()
            return [dict(row) for row in cuidadores]

    def vincular_cuidador_paciente(self, cuidador_id, paciente_id):
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("INSERT INTO vinculos_cuidador_paciente (cuidador_id, paciente_id) VALUES (?, ?)", (cuidador_id, paciente_id))
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False
            # db_manager.py (Dentro de class DatabaseManager:)

    def obter_pacientes_por_cuidador(self, cuidador_id):
        """
        Busca todos os pacientes monitorados por um cuidador específico
        usando a tabela de vínculos.
        """
        conn = self.get_db_connection()
        cursor = conn.cursor()
        pacientes = []
        
        try:
            # AQUI USAMOS JOIN:
            # 1. Selecionamos os dados do paciente (u)
            # 2. Fazemos JOIN com a tabela de vínculos (v)
            # 3. Filtramos pelo ID do cuidador logado
            cursor.execute("""
                SELECT 
                    u.id, 
                    u.nome_completo, 
                    u.email, 
                    u.data_nascimento 
                FROM usuarios u
                INNER JOIN vinculos_cuidador_paciente v ON u.id = v.paciente_id
                WHERE v.cuidador_id = ?
            """, (cuidador_id,))
            
            resultados = cursor.fetchall()
            
            # Converte os resultados em uma lista de dicionários
            # 🚨 OBS: Ajuste as chaves ('id', 'nome_completo', etc.) se forem diferentes no seu DB.
            for row in resultados:
                pacientes.append({
                    'id': row[0],
                    'nome_completo': row[1],
                    'email': row[2],
                    'data_nascimento': row[3],
                })

        except Exception as e:
            print(f"Erro ao obter pacientes por cuidador: {e}")
            
        finally:
            conn.close()
            
        return pacientes

    def vincular_paciente_medico(self, paciente_id, medico_id):
        """
        Atualiza o campo medico_id do paciente na tabela users.
        (Esta é a única fonte de verdade para o filtro de pacientes do médico).
        """
        # medico_id_value será o ID ou None, caso o medico_id passado seja 0 ou vazio
        medico_id_value = medico_id if medico_id and medico_id != 0 else None
        
        with self.get_db_connection() as conn:
            try:
                # 1. Atualiza o campo principal na tabela users
                cursor = conn.execute(
                    "UPDATE users SET medico_id = ? WHERE id = ? AND role = 'paciente'",
                    (medico_id_value, paciente_id)
                )
                
                conn.commit()
                return cursor.rowcount > 0
                
            except Exception as e:
                print(f"Erro ao vincular paciente {paciente_id} ao médico {medico_id}: {e}")
                conn.rollback()
                return False

    def buscar_agendamentos_paciente(self, user_id):
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT a.id, a.data_hora, a.status, a.observacoes, m.username as medico_username
            FROM agendamentos a
            JOIN users m ON a.medico_id = m.id
            WHERE a.paciente_id = ?
            ORDER BY a.data_hora DESC
        """, (user_id,))
        
        agendamentos = [
            {'id': row[0], 
             'data_hora': row[1], 
             'status': row[2], 
             'observacoes': row[3], 
             'medico_username': row[4]} 
            for row in cursor.fetchall()
        ]
        conn.close()
        return agendamentos
    
# No seu database_manager.py, adicione:

    def buscar_agendamentos_por_medico(self, medico_id):
        """
        Busca agendamentos vinculados a um médico específico.
        Usado para Médicos (medico_id = id do próprio) e Secretários 
        (medico_id = id do seu mestre).
        """
        query = """
        SELECT 
            a.id, a.data_hora, a.status, 
            p.nome_completo AS paciente_nome,
            m.nome_completo AS medico_nome
        FROM agendamentos a
        JOIN users p ON a.paciente_id = p.id
        JOIN users m ON a.medico_id = m.id
        WHERE a.medico_id = ?
        ORDER BY a.data_hora DESC
        """
        try:
            with self.get_db_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(query, (medico_id,))
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Erro ao buscar agendamentos por médico: {e}")
            return []
        
    # No seu database_manager.py, adicione:

    def medico_tem_acesso_a_paciente(self, medico_id, paciente_id):
        """Verifica se um paciente específico pertence ao médico, usando o vínculo."""
        query = """
        SELECT 1 FROM users u
        WHERE u.id = ? AND (
            u.medico_id = ? OR u.id IN (
                SELECT paciente_id FROM vinculos_medico_paciente WHERE medico_id = ?
            )
        )
        """
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                # Passa o ID do Paciente (u.id=?) e o ID do Médico (duas vezes)
                cursor.execute(query, (paciente_id, medico_id, medico_id))
                # Se encontrar uma linha, significa que o acesso é permitido (retorna True)
                return cursor.fetchone() is not None
        except Exception as e:
            print(f"Erro na verificação de acesso do médico: {e}")
            return False    

    def atualizar_status_agendamento(self, agendamento_id, novo_status):
            conn = self.get_db_connection()
            cursor = conn.cursor()
            try:
                cursor.execute("UPDATE agendamentos SET status = ? WHERE id = ?", (novo_status, agendamento_id))
                conn.commit()
                return True
            except Exception as e:
                print(f"Erro ao atualizar status: {e}")
                return False
            finally:
                conn.close()

    # No seu database_manager.py:

    def buscar_todos_agendamentos(self):
        """Busca todos os agendamentos (Apenas para Admin)."""
        query = """
        SELECT 
            a.id, a.data_hora, a.status, 
            p.nome_completo AS paciente_nome,
            m.nome_completo AS medico_nome
        FROM agendamentos a
        JOIN users p ON a.paciente_id = p.id
        JOIN users m ON a.medico_id = m.id
        ORDER BY a.data_hora DESC
        """
        try:
            with self.get_db_connection() as conn:
                # Garante que as colunas sejam acessíveis por nome (paciente_nome, medico_nome)
                conn.row_factory = sqlite3.Row 
                cursor = conn.cursor()
                cursor.execute(query)
                # Retorna uma lista de dicionários, mais fácil de manipular no Flask
                return [dict(row) for row in cursor.fetchall()] 
        except Exception as e:
            print(f"Erro ao buscar todos os agendamentos: {e}")
            return []
    
    def obter_pacientes_por_medico(self, medico_id):
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT u.* FROM users u
                    WHERE u.medico_id = ? OR u.id IN (
                        SELECT paciente_id FROM vinculos_medico_paciente WHERE medico_id = ?
                    )
                """, (medico_id, medico_id))
                pacientes = cursor.fetchall()
                return [dict(row) for row in pacientes]
            # database_manager.py (Dentro da sua classe DatabaseManager)

    def carregar_registros_glicemia_nutricao(self, paciente_id, limit=20):
            """
            Carrega os últimos N registros de glicemia, carboidratos e calorias 
            para um paciente, ordenados por data e hora.
            """
            conn = self.get_db_connection() # <--- CORRIGIDO
            cursor = conn.cursor()
            
            try:
                # SUPOSTA TABELA: Assumindo que você tem uma tabela 'registros' com estes campos.
                # Ajuste o nome da tabela e dos campos se eles forem diferentes!
                query = """
                SELECT 
                    data_hora, 
                    valor AS valor_glicemia, 
                    carbos, 
                    kcal
                FROM 
                    registros
                WHERE 
                    paciente_id = ?
                ORDER BY 
                    data_hora DESC
                LIMIT ?
                """
                
                cursor.execute(query, (paciente_id, limit))
                
                # Converte os resultados para uma lista de dicionários
                col_names = [desc[0] for desc in cursor.description]
                registros = [dict(zip(col_names, row)) for row in cursor.fetchall()]
                
                # Os gráficos esperam os dados em ordem cronológica ASC, então inverta a lista
                return registros[::-1] 
                
            except Exception as e:
                print(f"Erro ao carregar registros de glicemia/nutrição: {e}")
                return []
                
            finally:
                cursor.close()
                conn.close()
                
    def obter_resumo_medico_filtrado(self, medico_id):
        # ... (código para obter a conexão) ...
        
        # 1. Total de Pacientes (Você já tem essa lógica, mas é bom centralizar)
        total_pacientes = self.contar_pacientes_por_medico(medico_id) 

        # 2. Média de Glicemia (Fazendo JOIN com a tabela de registros)
        media_glicemia = self.calcular_media_glicemia_por_medico(medico_id)
        
        # 3. Registros Hoje (Fazendo JOIN e filtrando por data)
        registros_hoje = self.contar_registros_hoje_por_medico(medico_id)
        
        return {
            'total_pacientes': total_pacientes,
            'registros_hoje': registros_hoje,
            'media_glicemia': f"{media_glicemia:.1f}" if media_glicemia else 'N/A'
    }  
    # db_manager.py (Dentro de class DatabaseManager:)

    def obter_resumo_paciente(self, paciente_id):
        conn = self.get_db_connection()
        cursor = conn.cursor()
        resumo = {
            'ultimo_registro': None,
            'tempo_desde_ultimo': 'Nunca registrado',
            'media_ultima_semana': 'N/A',
            'hiperglicemia_count': 0,
            'hipoglicemia_count': 0
        }
        
        hoje = datetime.now()
        data_semana_atras = hoje - timedelta(days=7)

        try:
            # 1. Último Registro
            cursor.execute("""
                SELECT valor, data_hora 
                FROM registros 
                WHERE paciente_id = ? 
                ORDER BY data_hora DESC 
                LIMIT 1
            """, (paciente_id,))
            ultimo = cursor.fetchone()

            if ultimo:
                valor, data_hora_str = ultimo
                # É crucial que o formato de data_hora_str corresponda ao que você salva no DB
                data_hora_reg = datetime.strptime(data_hora_str, '%Y-%m-%d %H:%M:%S') 
                
                # Calcula o status
                if valor < LIMITE_HIPO:
                    status = 'danger'
                elif valor > LIMITE_HIPER:
                    status = 'warning' 
                else:
                    status = 'success'
                    
                # Calcula o tempo desde o último registro
                delta = hoje - data_hora_reg
                if delta.total_seconds() < 3600:
                    tempo_str = f"{int(delta.total_seconds() // 60)} min atrás"
                elif delta.days < 1:
                    tempo_str = f"{int(delta.total_seconds() // 3600)} horas atrás"
                else:
                    tempo_str = f"{delta.days} dias atrás"
                
                resumo['ultimo_registro'] = {'valor': valor, 'status': status}
                resumo['tempo_desde_ultimo'] = tempo_str

            # 2. Média da Última Semana
            cursor.execute("""
                SELECT AVG(valor) 
                FROM registros 
                WHERE paciente_id = ? AND data_hora >= ?
            """, (paciente_id, data_semana_atras.strftime('%Y-%m-%d %H:%M:%S')))
            media = cursor.fetchone()[0]
            
            if media is not None:
                resumo['media_ultima_semana'] = f"{media:.1f}"

            # 3. Contagem de Eventos Extremos (Últimos 7 dias)
            cursor.execute("""
                SELECT 
                    SUM(CASE WHEN valor < ? THEN 1 ELSE 0 END) as hipo,
                    SUM(CASE WHEN valor > ? THEN 1 ELSE 0 END) as hiper
                FROM registros 
                WHERE paciente_id = ? AND data_hora >= ?
            """, (LIMITE_HIPO, LIMITE_HIPER, paciente_id, data_semana_atras.strftime('%Y-%m-%d %H:%M:%S')))
            
            contagens = cursor.fetchone()
            if contagens:
                resumo['hipoglicemia_count'] = contagens[0]
                resumo['hiperglicemia_count'] = contagens[1]

        except Exception as e:
            print(f"Erro ao carregar resumo do paciente: {e}")

        finally:
            conn.close()
            
        return resumo          
# ---------------------- NOVAS FUNÇÕES DE GRÁFICOS ----------------------

    def obter_dados_glicemia_para_grafico(self, paciente_id):
            """Retorna dados de glicemia (data e valor) ordenados por data."""
            # Sua lógica de conexão aqui, talvez self.get_db_connection()
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT 
                        strftime('%Y-%m-%d %H:%M', data_hora) as data_hora, 
                        valor 
                    FROM 
                        registros 
                    WHERE 
                        user_id = ? 
                        AND valor IS NOT NULL 
                        AND tipo != 'Refeição'
                    ORDER BY 
                        data_hora ASC
                """, (paciente_id,))
                return [dict(row) for row in cursor.fetchall()]

    def obter_carbs_diarios_para_grafico(self, paciente_id):
            """Retorna a soma total de carboidratos por dia (apenas Refeições)."""
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT 
                        strftime('%Y-%m-%d', data_hora) as data, 
                        SUM(total_carbs) as total_carbs
                    FROM 
                        registros 
                    WHERE 
                        user_id = ? 
                        AND tipo = 'Refeição' 
                        AND total_carbs IS NOT NULL
                    GROUP BY 
                        data
                    ORDER BY 
                        data ASC
                """, (paciente_id,))
                return [dict(row) for row in cursor.fetchall()]

    def obter_calorias_diarias_para_grafico(self, paciente_id):
            """Retorna a soma total de calorias por dia (apenas Refeições)."""
            # Você não tinha um campo 'total_calorias' no DB, então a consulta deve ser ajustada
            # para somar a caloria de cada alimento dentro do JSON, ou usar um campo de soma
            # que você já tenha. Assumindo que você tem um campo 'calorias_totais' ou similar:
            
            # 🚨 NOTA: Se você não tiver um campo de soma para calorias, esta função falhará.
            # Vou usar 'total_calorias' como um placeholder para um campo de soma no registro:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT 
                        strftime('%Y-%m-%d', data_hora) as data, 
                        SUM(total_calorias) as total_calorias
                    FROM 
                        registros 
                    WHERE 
                        user_id = ? 
                        AND tipo = 'Refeição'
                        AND total_calorias IS NOT NULL
                    GROUP BY 
                        data
                    ORDER BY 
                        data ASC
                """, (paciente_id,))
                return [dict(row) for row in cursor.fetchall()]

 # -----------------------------------------------------------------------