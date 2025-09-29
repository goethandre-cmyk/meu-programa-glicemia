import os
import sqlite3
import json
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime


class DatabaseManager:
    def __init__(self, db_path='glicemia.db'):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        db_folder = os.path.join(base_dir, 'data')
        os.makedirs(db_folder, exist_ok=True)
        self.db_path = os.path.join(db_folder, db_path)
        
        self.create_tables()
        self.add_new_columns() # Mantido para garantir retrocompatibilidade em DBs existentes
        self._migrate_json_to_sqlite()

    def get_db_connection(self):
        conn = sqlite3.connect(self.db_path)
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
        
    # Mantive a função add_new_columns para compatibilidade com DBs já criados, 
    # embora as colunas já estejam na create_tables atualizada
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

    def create_tables(self):
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                
                # --- 1. Tabela de Usuários (CORRIGIDA E ATUALIZADA) ---
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY,
                        username TEXT UNIQUE NOT NULL,
                        password_hash TEXT NOT NULL,
                        role TEXT NOT NULL DEFAULT 'paciente',
                        email TEXT,
                        nome_completo TEXT, 
                        razao_ic REAL,
                        fator_sensibilidade REAL,
                        data_nascimento TEXT,
                        sexo TEXT,
                        telefone TEXT,          -- Adicionado
                        medico_id INTEGER       -- Adicionado
                        meta_glicemia REAL,
                        documento TEXT,
                        crm TEXT,
                        cns TEXT,
                        especialidade TEXT
                    );
                """)

                # --- 2. Tabela de Registros ---
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS registros (
                        id INTEGER PRIMARY KEY,
                        user_id INTEGER NOT NULL,
                        data_hora TEXT NOT NULL,
                        tipo TEXT NOT NULL,
                        valor REAL,
                        observacoes TEXT,
                        alimentos_json TEXT,
                        total_calorias REAL,
                        total_carbs REAL,
                        FOREIGN KEY (user_id) REFERENCES users (id)
                    );
                """)

                # --- 3. Tabela de Logs ---
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS logs_acao (
                        id INTEGER PRIMARY KEY,
                        data_hora TEXT,
                        acao TEXT,
                        usuario TEXT
                    );
                """)
                
                # --- 4. Tabela de Fichas Médicas (VERSÃO SIMPLIFICADA) ---
                # A tabela 'ficha_medica' abaixo é a nova e mais completa. A 'fichas_medicas' é redundante.
                # Mantida se for usada por outras funções antigas.
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS fichas_medicas (
                        paciente_id INTEGER PRIMARY KEY,
                        historico_clinico TEXT,
                        medicacoes_atuais TEXT,
                        alergias TEXT,
                        observacoes_medicas TEXT,
                        FOREIGN KEY (paciente_id) REFERENCES users (id)
                    );
                """)

                # --- 5. Tabela de Agendamentos ---
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS agendamentos (
                        id INTEGER PRIMARY KEY,
                        paciente_id INTEGER NOT NULL,
                        medico_id INTEGER NOT NULL,
                        data_hora TEXT NOT NULL,
                        status TEXT NOT NULL,
                        FOREIGN KEY (paciente_id) REFERENCES users (id),
                        FOREIGN KEY (medico_id) REFERENCES users (id)
                    );
                """)

                # --- 6. Tabela de Vínculos Médico-Paciente ---
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS vinculos_medico_paciente (
                        medico_id INTEGER NOT NULL,
                        paciente_id INTEGER NOT NULL,
                        PRIMARY KEY (medico_id, paciente_id),
                        FOREIGN KEY (medico_id) REFERENCES users (id),
                        FOREIGN KEY (paciente_id) REFERENCES users (id)
                    );
                """)
                
                # --- 7. Tabela de Vínculos Cuidador-Paciente ---
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS vinculos_cuidador_paciente (
                        cuidador_id INTEGER NOT NULL,
                        paciente_id INTEGER NOT NULL,
                        PRIMARY KEY (cuidador_id, paciente_id),
                        FOREIGN KEY (cuidador_id) REFERENCES users (id),
                        FOREIGN KEY (paciente_id) REFERENCES users (id)
                    );
                """)
                
                # --- 8. Tabela de Exames Laboratoriais ---
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS exames_laboratoriais (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        paciente_id INTEGER NOT NULL,
                        data_exame TEXT NOT NULL,
                        hb_a1c REAL,
                        glicose_jejum REAL,
                        colesterol_total REAL,
                        hdl REAL,
                        ldl REAL,
                        triglicerides REAL,
                        tsh REAL,
                        obs_medico TEXT,
                        FOREIGN KEY(paciente_id) REFERENCES users(id)
                    );
                """)

                # --- 9. Tabela Ficha Médica (Anamnese/Histórico Detalhado) ---
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS ficha_medica (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        medico_id INTEGER,
                        data_registro TEXT NOT NULL,
                        tipo_diabetes TEXT, 
                        data_diagnostico TEXT,
                        historico_familiar TEXT,
                        outras_comorbidades TEXT,
                        insulina_basal TEXT,
                        insulina_bolus TEXT,
                        dose_basal_manha REAL,
                        dose_basal_noite REAL,
                        FOREIGN KEY (user_id) REFERENCES users(id),
                        FOREIGN KEY (medico_id) REFERENCES users(id)
                    );
                """)
                
                conn.commit()
        
        except sqlite3.Error as e:
            print(f"Erro ao criar tabelas no banco de dados: {e}")

    def _migrate_json_to_sqlite(self):
        json_data = self._load_json_data()
        if not json_data:
            return

        print("Iniciando a migração dos dados do JSON para o SQLite...")
        
        with self.get_db_connection() as conn:
            cursor = conn.cursor()

            # Migrar usuários (AJUSTADO para nome_completo, telefone e medico_id)
            users_migrated_count = 0
            for user in json_data.get('users', []):
                cursor.execute("SELECT id FROM users WHERE username = ?", (user['username'],))
                if cursor.fetchone():
                    continue
                
                cursor.execute("""
                    INSERT INTO users (id, username, password_hash, role, email, nome_completo, razao_ic, fator_sensibilidade, data_nascimento, sexo, telefone, medico_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
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
                    user.get('telefone'), # Tenta carregar, senão None
                    user.get('medico_id') # Tenta carregar, senão None
                ))
                users_migrated_count += 1
            
            # Migrar registros (Sem alteração)
            registros_migrated_count = 0
            for registro in json_data.get('registros_glicemia_refeicao', []):
                cursor.execute("SELECT id FROM registros WHERE id = ?", (registro.get('id',-1),))
                if cursor.fetchone():
                    continue
                
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
            'documento', 'crm', 'cns', 'especialidade'
        ]
        
        # 1. Ajuste a QUERY para refletir as colunas corretas (Sem username, Com password_hash)
        set_clauses = ', '.join([f"{c} = ?" for c in colunas_set])
        query = f"""UPDATE users SET {set_clauses} WHERE id = ?"""
        
        # 2. Monte a tupla de valores na ORDEM EXATA das colunas_set
        valores = (
            # Valores na ordem de colunas_set:
            user_data.get('email'), 
            user_data.get('password_hash'), # NOVO CAMPO DE SENHA!
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
            user_data.get('medico_id'), # <<< VALOR ADICIONADO AQUI           
            # Condição WHERE:
            user_data.get('id')
        )
        
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
                            "MEDIDA CASEIRA", 
                            "PESO (g/ml)",    
                            Kcal, 
                            "CHO (g)"         -- ESTE É O ÍNDICE 5 QUE O PYTHON VAI LER
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
                            'cho': item[5]                 
                        })
                    
                    return alimentos_dict
            except Exception as e:
                print(f"Erro CRÍTICO na busca de alimentos: {e}")
                return []
    def salvar_registro(self, registro_data):
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO registros (user_id, data_hora, tipo, valor, observacoes, alimentos_json, total_calorias, total_carbs)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (registro_data['user_id'], registro_data['data_hora'], registro_data['tipo'], registro_data.get('valor'), registro_data.get('observacoes'), registro_data.get('alimentos_json'), registro_data.get('total_calorias'), registro_data.get('total_carbs')))
            conn.commit()
            return True
        
    def carregar_registros(self, user_id):
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM registros WHERE user_id = ? ORDER BY data_hora DESC", (user_id,))
            registros = cursor.fetchall()
            return [dict(row) for row in registros]
        
    def carregar_registros_por_usuario(user_id, dias=30):
        """
        Carrega todos os registros (glicemia e refeição) de um usuário
        dentro do período especificado.
        """
        data_limite = datetime.now() - timedelta(days=dias)
        
        # 1. Carregar Registros de Glicemia
        # Assumindo que a coleção se chama 'registros_glicemia'
        registros_glicemia = list(
            db.registros_glicemia.find({
                'user_id': user_id,
                'data_hora': {'$gte': data_limite}
            }).sort('data_hora', 1)
        )

        # 2. Carregar Registros de Refeição (para carbs/calorias)
        # Assumindo que a coleção se chama 'registros_refeicao'
        # Esta parte é crucial: Agrupar por dia para os gráficos de barra
        pipeline_refeicao = [
            {'$match': {'user_id': user_id, 'data_hora': {'$gte': data_limite}}},
            {'$group': {
                '_id': {'$dateToString': {'format': "%Y-%m-%d", 'date': "$data_hora"}},
                'total_carbs': {'$sum': "$carboidratos"}, # Assumindo campo 'carboidratos' na refeição
                'total_calorias': {'$sum': "$calorias"}   # Assumindo campo 'calorias' na refeição
            }},
            {'$sort': {'_id': 1}}
        ]
        registros_refeicao_agrupados = list(db.registros_refeicao.aggregate(pipeline_refeicao))
        
        return registros_glicemia, registros_refeicao_agrupados

    def encontrar_registro(self, registro_id):
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM registros WHERE id = ?", (registro_id,))
            registro = cursor.fetchone()
            return dict(registro) if registro else None
            
    def atualizar_registro(self, registro_data):
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE registros SET data_hora = ?, tipo = ?, valor = ?, observacoes = ?, alimentos_json = ?, total_calorias = ?, total_carbs = ?
                WHERE id = ?
            """, (registro_data['data_hora'], registro_data['tipo'], registro_data.get('valor'), registro_data.get('observacoes'), registro_data.get('alimentos_json'), registro_data.get('total_calorias'), registro_data.get('total_carbs'), registro_data['id']))
            conn.commit()
            return True

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
    def salvar_ficha_medica(self, ficha_data):
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("UPDATE fichas_medicas SET historico_clinico = ?, medicacoes_atuais = ?, alergias = ?, observacoes_medicas = ? WHERE paciente_id = ?",
                            (ficha_data.get('historico_clinico'), ficha_data.get('medicacoes_atuais'), ficha_data.get('alergias'), ficha_data.get('observacoes_medicas'), ficha_data['paciente_id']))
            
            if cursor.rowcount == 0:
                cursor.execute("INSERT INTO fichas_medicas (paciente_id, historico_clinico, medicacoes_atuais, alergias, observacoes_medicas) VALUES (?, ?, ?, ?, ?)",
                               (ficha_data['paciente_id'], ficha_data.get('historico_clinico'), ficha_data.get('medicacoes_atuais'), ficha_data.get('alergias'), ficha_data.get('observacoes_medicas')))
            
            conn.commit()
            return True

    def carregar_ficha_medica(self, paciente_id):
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM fichas_medicas WHERE paciente_id = ?", (paciente_id,))
            ficha = cursor.fetchone()
            return dict(ficha) if ficha else None
            
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