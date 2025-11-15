#===========DATABASE_MANAGE.PY==========#
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


    def inicializar_db(self): 
        """Cria as tabelas do banco de dados se elas não existirem, incluindo o novo schema unificado."""
        
        # IMPORTANTE: Garanta que self.db_path esteja definido no seu __init__
        with sqlite3.connect(self.db_path) as conn: 
            cursor = conn.cursor()
            
            # --- 1. Tabela de Usuários (users) ---
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
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    nome_completo TEXT,
                    telefone TEXT,
                    medico_id INTEGER
                );
            """)
            
            # Tabela para Histórico de Parâmetros Clínicos
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS historico_parametros (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    paciente_id INTEGER NOT NULL,
                    alterado_por_id INTEGER, 
                    campo TEXT NOT NULL, 	
                    valor_anterior REAL, 	
                    novo_valor REAL NOT NULL, 
                    data_registro DATETIME NOT NULL,
                    FOREIGN KEY (paciente_id) REFERENCES users(id),
                    FOREIGN KEY (alterado_por_id) REFERENCES users(id)
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
            
            # --- 3. Outras Tabelas ---
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS log_acoes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    acao TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # 🚨 NOVO SCHEMA UNIFICADO (Tabela TEMPORÁRIA)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ficha_medica_unificada (
                    paciente_id INTEGER PRIMARY KEY,
                    medico_id INTEGER,
                    data_registro TEXT,
                    tipo_diabetes TEXT,
                    data_diagnostico TEXT,
                    historico_clinico_familiar TEXT,
                    observacoes_comorbidades TEXT,
                    medicacoes_atuais TEXT,
                    alergias TEXT,
                    insulina_basal TEXT,
                    insulina_bolus TEXT,
                    dose_basal_manha REAL,
                    dose_basal_noite REAL,
                    FOREIGN KEY (paciente_id) REFERENCES users (id),
                    FOREIGN KEY (medico_id) REFERENCES users (id)
                );
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS detalhes_refeicao (
                    registro_id INTEGER PRIMARY KEY,
                    tipo_refeicao TEXT NOT NULL,
                    carboidratos REAL,
                    calorias REAL,
                    alimentos_json TEXT,
                    FOREIGN KEY (registro_id) REFERENCES registros (id)
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
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS registros_glicemia (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    paciente_id INTEGER NOT NULL,
                    valor_glicemia REAL NOT NULL,
                    data_hora TEXT NOT NULL,
                    tipo_medicao TEXT,
                    observacoes TEXT,
                    FOREIGN KEY (paciente_id) REFERENCES users (id)
                );
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS insulinas_config (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    nome_insulina TEXT NOT NULL,         -- Ex: 'Tresiba', 'Humalog', 'Lantus'
                    tipo_acao TEXT NOT NULL,             -- Ex: 'Basal Ultralonga', 'Rápida'
                    concentracao TEXT,                   -- Ex: '100 U/mL', '200 U/mL'
                    dose_basal_manha REAL,               -- Usada para insulinas Basais
                    dose_basal_noite REAL,               -- Usada para insulinas Basais
                    eh_ativa INTEGER DEFAULT 1,          -- 1 se a insulina está em uso
                    FOREIGN KEY (user_id) REFERENCES users(id)
                );
            """)

            conn.commit()
            

    def adicionar_colunas_calculo(self):
            """Adiciona colunas de cálculo de Bolus se elas não existirem."""
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            # Lista de colunas a serem adicionadas, evitando repetição
            colunas_a_adicionar = [
                ('ric_manha', 'REAL'), 
                ('ric_almoco', 'REAL'), 
                ('ric_jantar', 'REAL'),
                ('fsi_manha', 'REAL'), 
                ('fsi_almoco', 'REAL'), 
                ('fsi_jantar', 'REAL')
            ]
            
            for nome, tipo in colunas_a_adicionar:
                try:
                    # Tenta adicionar a coluna
                    cursor.execute(f"ALTER TABLE users ADD COLUMN {nome} {tipo}")
                    print(f"Coluna '{nome}' adicionada com sucesso.")
                except sqlite3.OperationalError as e:
                    # Se a coluna já existir (erro: "duplicate column name"), ignora
                    if 'duplicate column name' in str(e):
                        pass
                    else:
                        print(f"Erro ao adicionar coluna {nome}: {e}")
            
            conn.commit()
            conn.close()



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



    def migrar_fichas_medicas_antigas(self):
        """
        Migra dados da tabela obsoleta 'fichas_medicas' para a nova 'ficha_medica_unificada'.
        """
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        try:
            # 1. Seleciona os dados da tabela antiga (que tem menos campos)
            cursor.execute("""
                SELECT paciente_id, condicao_atual, alergias, historico_familiar, medicamentos_uso
                FROM fichas_medicas
            """)
            dados_antigos = cursor.fetchall()

            # 2. Insere na nova tabela unificada (preenchendo os campos específicos com NULL/N/A)
            data_migracao = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            for row in dados_antigos:
                paciente_id = row[0]
                condicao_atual = row[1]
                alergias = row[2]
                historico_familiar = row[3]
                medicamentos_uso = row[4]
                
                cursor.execute("""
                    INSERT OR IGNORE INTO ficha_medica_unificada (
                        paciente_id, historico_clinico_familiar, observacoes_comorbidades, 
                        medicacoes_atuais, alergias, data_registro, 
                        tipo_diabetes, data_diagnostico, insulina_basal, insulina_bolus
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    paciente_id,
                    historico_familiar,
                    condicao_atual,
                    medicamentos_uso,
                    alergias,
                    data_migracao,
                    'Migrado', # Valor temporário
                    None,
                    None,
                    None
                ))
                
            conn.commit()
            print(f"Migração de {len(dados_antigos)} fichas médicas concluída para 'ficha_medica_unificada'.")
            
        except sqlite3.OperationalError as e:
            print(f"Alerta de Migração: A tabela 'fichas_medicas' não pôde ser lida. {e}")
        finally:
            conn.close()

    def finalizar_refatoramento_fichas(self):
        """
        Remove a tabela obsoleta e renomeia a tabela unificada para o nome definitivo ('ficha_medica').
        """
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        # 1. Exclui a tabela obsoleta
        try:
            cursor.execute("DROP TABLE IF EXISTS fichas_medicas")
            print("Tabela obsoleta 'fichas_medicas' excluída.")
        except Exception as e:
            print(f"Erro ao excluir tabela 'fichas_medicas': {e}")
            
        # 2. Renomeia a tabela final unificada para o nome definitivo
        try:
            cursor.execute("ALTER TABLE ficha_medica_unificada RENAME TO ficha_medica")
            print("Tabela 'ficha_medica_unificada' renomeada para 'ficha_medica'.")
        except Exception as e:
            print(f"Erro ao renomear tabela para 'ficha_medica': {e}")
            
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


    def obter_usuario_por_id(self, user_id):
        """
        Busca um único usuário por ID, retornando todas as colunas necessárias para edição.
        """
        conn = self.get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            # Tabela 'users'
            query = """
                SELECT 
                    id, username, email, nome_completo, 
                    ric_manha, ric_almoco, ric_jantar,
                    fator_sensibilidade, meta_glicemia, medico_id, role
                FROM users 
                WHERE id = ?;
            """
            cursor.execute(query, (user_id,))
            user_row = cursor.fetchone()
            
            if user_row:
                user_data = dict(user_row)
                # Mapeamento para FSI, para consistência em toda a aplicação
                user_data['fsi'] = user_data.pop('fator_sensibilidade', None)
                return user_data
            
            return None
            
        except Exception as e:
            print(f"Erro ao obter usuário por ID {user_id}: {e}")
            return None
        finally:
            conn.close()


    def salvar_parametros_paciente(self, paciente_id, ric_manha, ric_almoco, ric_jantar, ric_noite, fsi_manha, fsi_almoco, fsi_jantar, fsi_noite, meta_glicemia, alterado_por_id):
        """
        Atualiza os parâmetros de Bolus por turno (RIC/FSI) para um paciente e registra as alterações no histórico.
        
        :param paciente_id: ID do paciente sendo atualizado.
        :param alterado_por_id: ID do usuário logado que está realizando a alteração (médico, paciente, etc.).
        """
        conn = self.get_db_connection()
        cursor = conn.cursor()
        historico_updates = []
        
        # 1. Mapeamento dos novos valores (incluindo todos os turnos agora)
        # ATENÇÃO: Verifique se esses 10 campos existem na sua tabela 'users'.
        novos_valores = {
            'ric_manha': ric_manha,
            'ric_almoco': ric_almoco,
            'ric_jantar': ric_jantar,
            'ric_noite': ric_noite,         # Adicionado
            'fsi_manha': fsi_manha,         # Adicionado
            'fsi_almoco': fsi_almoco,       # Adicionado
            'fsi_jantar': fsi_jantar,       # Adicionado
            'fsi_noite': fsi_noite,         # Adicionado
            'meta_glicemia': meta_glicemia,
        }

        try:
            # 2. Obter os valores ATUAIS da tabela users
            colunas = list(novos_valores.keys())
            # Garante que 'fator_sensibilidade' não está na lista de colunas se você migrou para fsi_manha/fsi_almoco...
            query_select = f"SELECT {', '.join(colunas)} FROM users WHERE id = ? AND role = 'paciente'"
            cursor.execute(query_select, (paciente_id,))
            valores_atuais_db = cursor.fetchone()
            
            # ... (O restante da lógica de comparação e histórico é a mesma) ...
            # ... (A lógica de UPDATE precisa ser ajustada) ...

            if not valores_atuais_db:
                print(f"ERRO: Paciente {paciente_id} não encontrado ou não é paciente.")
                return False
                
            valores_atuais = dict(zip(colunas, valores_atuais_db))
            
            # 3. Comparar valores e montar o histórico
            data_registro = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Lógica de comparação idêntica, mas para mais campos
            for campo, novo_valor in novos_valores.items():
                valor_atual = valores_atuais.get(campo)
                
                valor_atual_num = float(valor_atual) if valor_atual is not None else 0
                novo_valor_num = float(novo_valor) if novo_valor is not None and novo_valor != '' else 0
                
                if valor_atual_num != novo_valor_num:
                    historico_updates.append((
                        paciente_id,
                        alterado_por_id,
                        campo,
                        valor_atual,    # Valor anterior
                        novo_valor_num, # Novo valor
                        data_registro
                    ))
            
            # 4. Atualizar a tabela users (somente se houver alteração)
            if historico_updates:
                
                # 🚨 NOVO SQL UPDATE com todos os 9 campos
                query_update = """
                    UPDATE users
                    SET ric_manha = ?, ric_almoco = ?, ric_jantar = ?, ric_noite = ?, 
                        fsi_manha = ?, fsi_almoco = ?, fsi_jantar = ?, fsi_noite = ?, 
                        meta_glicemia = ?
                    WHERE id = ? AND role = 'paciente';
                """
                
                # Parâmetros: novos valores na ordem da query + paciente_id
                params_update = (
                    ric_manha, ric_almoco, ric_jantar, ric_noite, 
                    fsi_manha, fsi_almoco, fsi_jantar, fsi_noite, 
                    meta_glicemia,
                    paciente_id
                )
                
                cursor.execute(query_update, params_update)
                
                # 5. Salvar o Histórico (Lógica idêntica, mas com mais dados)
                sql_historico = """
                    INSERT INTO historico_parametros 
                    (paciente_id, alterado_por_id, campo, valor_anterior, novo_valor, data_registro)
                    VALUES (?, ?, ?, ?, ?, ?)
                """
                cursor.executemany(sql_historico, historico_updates)

            conn.commit()
            return True
            
        except Exception as e:
            print(f"Erro ao salvar parâmetros para o paciente {paciente_id}: {e}")
            if conn:
                conn.rollback() 
            return False
        finally:
            if conn:
                conn.close()

    def verificar_vinculo_medico_paciente(self, medico_id, paciente_id):
        """
        Verifica se o paciente está vinculado ao médico (usando a coluna medico_id
        na tabela users, que você já preencheu em criar_paciente_e_ficha_inicial).
        """
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 1 
                FROM users 
                WHERE id = ? AND medico_id = ?
            """, (paciente_id, medico_id))
            
            # Se fetchone() retornar um resultado, o vínculo existe (True).
            vinculo_existe = cursor.fetchone() is not None
            conn.close()
            return vinculo_existe
            
        except Exception as e:
            print(f"Erro ao verificar vínculo: {e}")
            return False

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
        cursor.execute("SELECT id, username, password_hash, role FROM users WHERE username = ?", (username,))
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
    
    def contar_usuarios(self, role=None):
        """
        Conta o número total de usuários, opcionalmente filtrando por função (role).
        """
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        try:
            if role:
                # Se a role for fornecida, conta apenas usuários com aquela role
                query = "SELECT COUNT(*) FROM users WHERE role = ?"
                cursor.execute(query, (role,))
            else:
                # Se nenhuma role for fornecida, conta todos os usuários
                query = "SELECT COUNT(*) FROM users"
                cursor.execute(query)
            
            # O fetchone retorna uma tupla, o COUNT é o primeiro elemento [0]
            count = cursor.fetchone()[0]
            return count
            
        except Exception as e:
            print(f"Erro ao contar usuários: {e}")
            return 0
        finally:
            conn.close()

    def contar_pacientes_sem_parametros(self):
            """
            Conta o número de pacientes que ainda não tiveram seus parâmetros de Bolus (RIC e Meta) configurados.
            Considera sem parâmetro se o RIC da manhã ou a Meta de Glicemia for NULL ou 0.
            """
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            try:
                # A consulta busca pacientes onde a role é 'paciente' E 
                # pelo menos um dos campos essenciais está AUSENTE ou ZERO.
                query = """
                    SELECT COUNT(id) FROM users 
                    WHERE role = 'paciente' 
                    AND (ric_manha IS NULL OR ric_manha = 0 
                        OR meta_glicemia IS NULL OR meta_glicemia = 0);
                """
                cursor.execute(query)
                
                # O fetchone retorna uma tupla, o COUNT é o primeiro elemento [0]
                count = cursor.fetchone()[0]
                return count
                
            except Exception as e:
                print(f"Erro ao contar pacientes sem parâmetros: {e}")
                return 0
            finally:
                conn.close()

    def contar_pacientes_em_alerta(self):
            """
            Conta o número de pacientes que tiveram uma glicemia fora da zona de segurança 
            (Hiper ou Hipoglicemia) nas últimas 48 horas.
            """
            conn = self.get_db_connection()
            cursor = conn.cursor()
        
            # 1. Definir o limite de tempo (48 horas atrás)
            # O uso correto com 'from datetime import datetime, timedelta' é:
            limite_tempo = datetime.now() - timedelta(hours=48) 
            limite_tempo_str = limite_tempo.strftime('%Y-%m-%d %H:%M:%S')
            # Definir limites de glicemia (em mg/dL)
            HIPOGLICEMIA = 70
            HIPERGLICEMIA = 250
            
            try:
                # 2. Consultar registros de glicemia nos últimos 48h que estejam fora da zona segura
                # Usamos DISTINCT para contar CADA PACIENTE apenas uma vez, mesmo que ele tenha múltiplos registros de alerta.
                query = """
                    SELECT COUNT(DISTINCT paciente_id) 
                    FROM registros
                    WHERE timestamp >= ? 
                    AND (glicemia < ? OR glicemia > ?);
                """
                cursor.execute(query, (limite_tempo_str, HIPOGLICEMIA, HIPERGLICEMIA))
                
                count = cursor.fetchone()[0]
                return count
                
            except Exception as e:
                print(f"Erro ao contar pacientes em alerta: {e}")
                return 0
            finally:
                conn.close()

    def contar_registros_24h(self):
            """
            Conta o número total de registros (glicemia, bolus, etc.) feitos nas últimas 24 horas.
            """
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            # 1. Definir o limite de tempo (24 horas atrás)
            limite_tempo = datetime.now() - timedelta(hours=24)
            limite_tempo_str = limite_tempo.strftime('%Y-%m-%d %H:%M:%S')
            
            try:
                # 2. Consultar registros onde o timestamp é maior ou igual ao limite
                query = """
                    SELECT COUNT(*) 
                    FROM registros
                    WHERE timestamp >= ?;
                """
                cursor.execute(query, (limite_tempo_str,))
                
                count = cursor.fetchone()[0]
                return count
                
            except Exception as e:
                print(f"Erro ao contar registros de 24h: {e}")
                return 0
            finally:
                conn.close()
# NO ARQUIVO: database_manager.py (dentro da classe DatabaseManager)

    def obter_todos_pacientes(self):
        """
        Retorna todos os usuários com o role 'paciente', usado para o Painel de Gestão/Admin.
        """
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        # 🚨 USANDO TABELA 'users' E COLUNA 'nome_completo' 🚨
        query = """
        SELECT 
            id, 
            username, 
            nome_completo, 
            razao_ic, 
            fator_sensibilidade,
            meta_glicemia 
        FROM 
            users
        WHERE 
            role = 'paciente';
        """
        
        cursor.execute(query)
        colunas = [col[0] for col in cursor.description]
        pacientes = [dict(zip(colunas, row)) for row in cursor.fetchall()]
        
        conn.close()
        return pacientes
    
    def obter_todos_pacientes_com_parametros(self):
            """
            Retorna a lista de pacientes (role='paciente') com seus parâmetros clínicos.
            """
            conn = self.get_db_connection()
            # Usamos Row para retornar os dados como um dicionário (acessível por nome da coluna)
            conn.row_factory = Row 
            cursor = conn.cursor()
            
            try:
                query = """
                    SELECT id, username, nome_completo, medico_id, 
                        ric_manha, ric_almoco, ric_jantar,
                        fator_sesibilidade, meta_glicemia
                    FROM users
                    WHERE role = 'paciente'
                    ORDER BY nome_completo ASC;
                """
                cursor.execute(query)
                pacientes = [dict(row) for row in cursor.fetchall()]
                return pacientes
                
            except Exception as e:
                print(f"Erro ao obter pacientes com parâmetros: {e}")
                return []
            finally:
                conn.close()

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
            cursor.execute("SELECT COUNT(id) FROM users WHERE role = 'paciente'")
            resumo['total_pacientes'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(id) FROM users WHERE role = 'medico'")
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
        
    # No arquivo: database_manager.py

 # No arquivo: database_manager.py

    def salvar_refeicao(self, user_id, data_hora_str, tipo_refeicao, total_carbs, total_kcal, alimentos_selecionados_json, dose_aplicada=None, observacoes=None):
        """
        Salva um novo registro de refeição, dividindo a informação entre 'registros' e 'detalhes_refeicao'.
        """
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        try:
            # 1. INSERT na tabela 'registros' (Armazena o link e a dose aplicada)
            # Assumindo que a coluna 'dose_aplicada' existe em 'registros'
            cursor.execute("""
                INSERT INTO registros (user_id, tipo, data_hora, observacoes, dose_aplicada) 
                VALUES (?, ?, ?, ?, ?) 
            """, (user_id, 'Refeição', data_hora_str, observacoes, dose_aplicada))

            # 2. Captura o ID do registro principal recém-criado
            registro_id = cursor.lastrowid
            
            # 3. INSERT na tabela 'detalhes_refeicao' (Armazena carbos/kcal/JSON)
            cursor.execute("""
                INSERT INTO detalhes_refeicao (registro_id, tipo_refeicao, carboidratos, calorias, alimentos_json)
                VALUES (?, ?, ?, ?, ?)
            """, (registro_id, tipo_refeicao, total_carbs, total_kcal, alimentos_selecionados_json))
            
            conn.commit()
            return True
        
        except sqlite3.Error as e:
            # LOG CRÍTICO: Se o erro for de SQL (coluna faltando, tipo errado), ele aparecerá aqui.
            print(f"ERRO SQL CRÍTICO ao salvar refeição: {e}")
            conn.rollback() 
            return False
        except Exception as e:
            print(f"ERRO DESCONHECIDO ao salvar refeição: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
   
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
                    INSERT INTO registros (user_id, data_hora, tipo, valor, observacoes, alimentos_json, total_calorias, total_carbs, dose_aplicada)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (registro_data['user_id'], 
                    registro_data['data_hora'], 
                    registro_data['tipo'], 
                    registro_data.get('valor'), 
                    registro_data.get('observacoes'), 
                    registro_data.get('alimentos_json'), 
                    registro_data.get('total_calorias'), 
                    registro_data.get('total_carbs'),
                    registro_data.get('dose_aplicada'))) # <--- NOVO CAMPO
                conn.commit()
                return True
        except sqlite3.Error as e:
            print(f"ERRO DE SQL NO SALVAMENTO: {e}") 
            return False


    def carregar_registros(self, user_id):
        """
        Carrega todos os registros (glicemia e refeição) do usuário,
        unindo dados da tabela 'registros' com 'detalhes_refeicao' (assumindo que esta faz parte do seu modelo).
        """
        sql = """
            SELECT 
                r.id, 
                r.data_hora, 
                r.tipo, 
                r.valor, 
                r.observacoes, 
                r.dose_aplicada, -- <--- NOVO CAMPO
                -- Colunas da tabela detalhes_refeicao (dr)
                dr.tipo_refeicao,
                dr.alimentos_json, 
                dr.calorias AS total_calorias,
                dr.carboidratos AS total_carbs 
            FROM registros r
            LEFT JOIN detalhes_refeicao dr ON r.id = dr.registro_id
            WHERE r.user_id = ?
            ORDER BY r.data_hora DESC
        """
        with self.get_db_connection() as conn:
            # Garante que as colunas sejam acessíveis por nome
            conn.row_factory = sqlite3.Row 
            cursor = conn.cursor() 
        try:
            cursor.execute(sql, (user_id,)) 
            registros = cursor.fetchall()
            
            # Retorna a lista de dicionários
            return [dict(row) for row in registros]
            
        except sqlite3.OperationalError as e:
            print(f"Erro ao carregar registros: {e}")
            return []
        
   # No arquivo: database_manager.py

    def excluir_registro(self, registro_id):
        """
        Exclui um registro, incluindo todos os detalhes associados em outras tabelas.
        A exclusão deve ser em cascata (CASCADE) no DB. Se não for, excluímos manualmente.
        """
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        try:
            # A boa prática é usar FOREIGN KEY com ON DELETE CASCADE, mas se não tiver:
            # 1. Excluir detalhes da refeição (para evitar erro de FK)
            cursor.execute("DELETE FROM detalhes_refeicao WHERE registro_id = ?", (registro_id,))
            
            # 2. Excluir o registro principal
            cursor.execute("DELETE FROM registros WHERE id = ?", (registro_id,))
            
            conn.commit()
            return True
        
        except sqlite3.Error as e:
            print(f"ERRO SQL ao excluir registro {registro_id}: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
        # No arquivo: database_manager.py

    def salvar_glicemia(self, user_id, valor_glicemia, data_hora_str, tipo_medicao, observacoes=None, dose_aplicada=None):
            """
            Salva um registro de glicemia, incluindo a dose de insulina aplicada, se fornecida.
            """
            conn = self.get_db_connection()
            cursor = conn.cursor()

            # Assumindo que as colunas 'valor', 'tipo_medicao' e 'dose_aplicada' existem em 'registros'
            query = """
                INSERT INTO registros (user_id, tipo, valor, data_hora, tipo_medicao, observacoes, dose_aplicada) 
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """
            
            try:
                cursor.execute(query, (
                    user_id, 
                    'Glicemia', 
                    valor_glicemia, 
                    data_hora_str, 
                    tipo_medicao, 
                    observacoes, 
                    dose_aplicada 
                ))
                conn.commit()
                return True
            except sqlite3.Error as e:
                # LOG CRÍTICO: Se o erro for de SQL (coluna faltando, tipo errado), ele aparecerá aqui.
                print(f"ERRO SQL CRÍTICO ao salvar glicemia: {e}")
                return False
            except Exception as e:
                print(f"ERRO DESCONHECIDO ao salvar glicemia: {e}")
                return False
            finally:
                conn.close()
                    

    def encontrar_registro(self, registro_id):
        """
        Busca um registro principal pelo ID na tabela 'registros', incluindo 
        detalhes de refeição. Inclui LOG de diagnóstico.
        """
        conn = self.get_db_connection()
        # Garante que as colunas sejam retornadas como chaves de dicionário.
        conn.row_factory = sqlite3.Row 
        cursor = conn.cursor()
        
        try:
            # 🚨 Removendo o filtro "r.tipo IN (...)" temporariamente para garantir a busca
            query = """
                SELECT 
                    r.*, 
                    d.tipo_refeicao, d.carboidratos, d.calorias, d.alimentos_json
                FROM 
                    registros r
                LEFT JOIN 
                    detalhes_refeicao d ON r.id = d.registro_id
                WHERE 
                    r.id = ?
            """
            
            print(f"DEBUG DB: Buscando registro ID: {registro_id} para o SQL.")
            cursor.execute(query, (registro_id,))
            registro = cursor.fetchone()
            
            # Processamento e retorno dos dados
            if registro:
                resultado = dict(registro)
                
                # LOG CRÍTICO: Informa o ID do usuário retornado pelo banco e o tipo
                print(f"DEBUG DB: Registro ENCONTRADO. user_id do DB: {resultado.get('user_id')}, tipo: {resultado.get('tipo')}")
                
                return resultado
            else:
                print(f"DEBUG DB: Registro ID {registro_id} NÃO ENCONTRADO no banco de dados.")
                return None
        
        except sqlite3.Error as e:
            print(f"ERRO SQL ao encontrar registro {registro_id}: {e}")
            return None
        except Exception as e:
            print(f"ERRO GENÉRICO ao encontrar registro {registro_id}: {e}")
            return None
        finally:
            conn.close()

# NO database_manager.py, DENTRO da classe DatabaseManager

    def atualizar_registro(self, registro_data):
        """
        Atualiza um registro existente no banco de dados com base no seu tipo (Glicemia ou Refeição).
        O parâmetro registro_data é um dicionário contendo 'id' e 'tipo'.
        Inclui o campo 'dose_aplicada' para Glicemia e Refeição.
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

            if tipo_principal in ['Glicemia', 'Pre_Refeicao', 'Pos_Refeicao', 'Jejum', 'Antes_Dormir']:
                # Atualiza campos de Glicemia + Comuns + DOSE DE INSULINA
                sql = """
                    UPDATE registros SET 
                        data_hora = ?, 
                        observacoes = ?, 
                        valor = ?,
                        tipo = ?,
                        tipo_medicao = ?,
                        dose_aplicada = ?  -- <-- CAMPO ADICIONADO
                    WHERE id = ?
                """
                params = (
                    registro_data.get('data_hora'),
                    registro_data.get('observacoes'),
                    registro_data.get('valor'),
                    registro_data.get('tipo'),      # 'Glicemia' ou subtipo
                    registro_data.get('tipo_medicao'),
                    registro_data.get('dose_aplicada'), # <-- VALOR ADICIONADO
                    registro_id
                )
            
            elif tipo_principal == 'Refeição':
                # Atualiza campos de Refeição + Comuns + DOSE DE INSULINA
                sql = """
                    UPDATE registros SET 
                        data_hora = ?, 
                        observacoes = ?, 
                        tipo = ?,
                        alimentos_json = ?, 
                        total_carbs = ?, 
                        total_calorias = ?,
                        tipo_refeicao = ?,
                        dose_aplicada = ?  -- <-- CAMPO ADICIONADO
                    WHERE id = ?
                """
                params = (
                    registro_data.get('data_hora'),
                    registro_data.get('observacoes'),
                    registro_data.get('tipo'),      # 'Refeição'
                    registro_data.get('alimentos_json'),
                    registro_data.get('total_carbs'),
                    registro_data.get('total_calorias'),
                    registro_data.get('tipo_refeicao'),
                    registro_data.get('dose_aplicada'), # <-- VALOR ADICIONADO
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
        """
        Exclui um registro, tratando a ordem de deleção devido às chaves estrangeiras.
        """
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        # É fundamental que o PRAGMA foreign_keys = ON esteja na sua função get_db_connection
        # para que o SQLite honre as FOREIGN KEYS. Se ele estiver lá, podemos confiar no CASCADE.

        try:
            # A ordem de exclusão é crítica: filhas -> principal
            # Incluímos as 3 dependências mais prováveis:
            cursor.execute("DELETE FROM detalhes_refeicao WHERE registro_id = ?", (registro_id,))
            cursor.execute("DELETE FROM registros_glicemia WHERE registro_id = ?", (registro_id,))
            cursor.execute("DELETE FROM registros_insulina WHERE registro_id = ?", (registro_id,))
            
            # Se você tiver uma tabela de 'detalhes_glicemia' ou outra, adicione-a aqui!
            
            # Excluir o registro principal
            cursor.execute("DELETE FROM registros WHERE id = ?", (registro_id,))
            
            conn.commit()
            return True
        
        except Exception as e:
            # Se o erro FOREIGN KEY persistir AQUI, significa que HÁ MAIS UMA TABELA FILHA
            print(f"ERRO CRÍTICO NA EXCLUSÃO (FOREIGN KEY): {e}") 
            conn.rollback()
            try:
                print("Tentando exclusão com Foreign Keys desabilitadas...")
                conn.execute("PRAGMA foreign_keys = OFF")
                conn.execute("DELETE FROM registros WHERE id = ?", (registro_id,))
                conn.commit()
                return True
            except Exception as retry_e:
                print(f"Falha total na exclusão: {retry_e}")
                conn.rollback()
                return False
        finally:
            # Garante que a conexão seja fechada e o PRAGMA volte ao normal
            conn.execute("PRAGMA foreign_keys = ON")
            conn.close()

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
                    paciente_id, medico_id, data_exame, hb_a1c, glicose_jejum, colesterol_total, 
                    hdl, ldl, triglicerides, tsh, obs_medico
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ficha_exame.get('paciente_id'),
                ficha_exame.get('medico_id'), 
                ficha_exame.get('data_exame'), 
                hb_a1c, glicose_jejum, colesterol_total, hdl, ldl, triglicerides, tsh,
                ficha_exame.get('obs_medico')
            ))
            conn.commit()
            return True

        except Exception as e:
            print(f"Erro SQLite ao salvar exame laboratorial: {e}")
            conn.rollback()
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
            historico_clinico_familiar = ficha_data.get('condicao_atual')
            medicacoes_atuais = ficha_data.get('medicamentos_uso')
            alergias = ficha_data.get('alergias')
            observacoes_medicas = ficha_data.get('historico_familiar')
            paciente_id = ficha_data['paciente_id']

            # UPDATE:
            cursor.execute("""
                UPDATE ficha_medica 
                SET historico_clinico_familiar = ?, medicacoes_atuais = ?, alergias = ?, observacoes_medicas = ? 
                WHERE paciente_id = ?
                """,
                (historico_clinico_familiar, medicacoes_atuais, alergias, observacoes_medicas, paciente_id))
            
            # INSERT (se a linha não existir):
            if cursor.rowcount == 0:
                cursor.execute("""
                    INSERT INTO fichas_medicas (paciente_id, historico_clinico_familiar, medicacoes_atuais, alergias, observacoes_medicas) 
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (paciente_id, historico_clinico_familiar, medicacoes_atuais, alergias, observacoes_medicas))
            
            conn.commit()
            return True

    def carregar_ficha_medica(self, paciente_id):
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Seleciona as colunas na ordem correta
            cursor.execute("""
                SELECT historico_clinico_familiar, medicacoes_atuais, alergias, observacoes_comorbidades 
                FROM ficha_medica
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

    # NO SEU ARQUIVO database_manager.py (Definição ideal)

    def salvar_agendamento(self, agendamento_data):
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO agendamentos (paciente_id, medico_id, data_hora, observacoes, status)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    agendamento_data['paciente_id'], 
                    agendamento_data['medico_id'], 
                    agendamento_data['data_hora'], 
                    agendamento_data['observacoes'], # NOVO CAMPO
                    'Agendada' # Status
                ))
                conn.commit()
                return True
        except Exception as e:
            print(f"Erro ao salvar agendamento: {e}")
            return False

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
                FROM users u
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
        """
        Busca os agendamentos de um paciente, convertendo a data/hora do DB (string) 
        para um objeto datetime do Python.
        """
        conn = self.get_db_connection()
        # Usar row_factory para acessar colunas por nome é mais seguro
        conn.row_factory = sqlite3.Row 
        cursor = conn.cursor()
        
        # Formato padrão do SQLite para DATETIME. Verifique se é este o formato.
        DB_FORMAT = '%Y-%m-%dT%H:%M'
        
        query = """
            SELECT a.id, a.data_hora, a.status, a.observacoes, m.username as medico_username
            FROM agendamentos a
            JOIN users m ON a.medico_id = m.id
            WHERE a.paciente_id = ?
            ORDER BY a.data_hora DESC
        """
        
        try:
            cursor.execute(query, (user_id,))
            agendamentos = []
            
            for row in cursor.fetchall():
                agendamento = dict(row) # Cria um dicionário a partir da linha
                data_hora_str = agendamento.get('data_hora') # Acessando o valor como string
                
                # 1. Assume que não há objeto datetime
                data_hora_obj = None 
                
                # 2. Tenta converter APENAS se houver string
                if data_hora_str:
                    try:
                        # Tenta converter a string do DB em objeto datetime
                        data_hora_obj = datetime.strptime(data_hora_str, DB_FORMAT)
                    except ValueError:
                        # 3. Se houver erro, loga e mantém data_hora_obj como None
                        print(f"DEBUG: Falha na conversão de data/hora (Paciente ID {user_id}). Valor DB: '{data_hora_str}'.")
                
                # 4. Atualiza o dicionário com o objeto datetime ou None
                agendamento['data_hora'] = data_hora_obj
                
                agendamentos.append(agendamento)
                
            return agendamentos
            
        except Exception as e:
            print(f"Erro fatal ao buscar agendamentos para o paciente {user_id}: {e}")
            return []
            
        finally:
            if conn:
                conn.close()

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
    
    # db_manager.py

   # No arquivo: database_manager.py

    def obter_pacientes_do_medico(self, medico_id):
        """
        Retorna a lista de pacientes vinculados a um médico específico, 
        usando a tabela de ligação 'vinculo_medico_paciente'.
        """
        conn = self.get_db_connection()
        conn.row_factory = sqlite3.Row 
        cursor = conn.cursor()
        
        try:
            query = """
                SELECT 
                    u.id, u.username, u.email, u.nome_completo, 
                    u.ric_manha, u.ric_almoco, u.ric_jantar,
                    u.fator_sensibilidade, u.meta_glicemia 
                FROM users u
                JOIN vinculos_medico_paciente v 
                    ON u.id = v.paciente_id
                WHERE v.medico_id = ? AND u.role = 'paciente'
                ORDER BY u.nome_completo ASC;
            """
            
            # 1. Execução ÚNICA e Correta da Consulta
            cursor.execute(query, (medico_id,))
            
            # 2. Obter e converter resultados
            pacientes = [dict(row) for row in cursor.fetchall()]

            # 3. Mapeamento de FSI para consistência no frontend
            for p in pacientes:
                # Renomeia a chave 'fator_sensibilidade' para 'fsi'
                p['fsi'] = p.pop('fator_sensibilidade', None) 
                
            return pacientes
                
        # 4. Blocos de erro e finalização corretamente indentados
        except Exception as e:
            print(f"Erro ao obter pacientes do médico {medico_id} (usando tabela vinculo): {e}")
            return []
        finally:
            conn.close()



    def salvar_parametros_clinicos(self, paciente_id, novos_parametros: dict, alterado_por_id):
        """
        Atualiza múltiplos parâmetros clínicos para um paciente e registra as alterações no histórico.
        
        :param paciente_id: ID do paciente.
        :param novos_parametros: Dicionário {campo: novo_valor} dos parâmetros a serem atualizados.
        :param alterado_por_id: ID do usuário que fez a alteração.
        """
        conn = self.get_db_connection()
        cursor = conn.cursor()
        historico_updates = []
        
        # Prepara listas de colunas para SELECT
        campos_a_verificar = list(novos_parametros.keys())

        try:
            # 1. Obter os valores ATUAIS da tabela users
            query_select = f"SELECT {', '.join(campos_a_verificar)} FROM users WHERE id = ? AND role = 'paciente'"
            cursor.execute(query_select, (paciente_id,))
            valores_atuais_db = cursor.fetchone()
            
            if not valores_atuais_db:
                print(f"ERRO: Paciente {paciente_id} não encontrado ou não é paciente.")
                return False
                
            valores_atuais = dict(zip(campos_a_verificar, valores_atuais_db))
            
            # 2. Comparar valores e montar o histórico
            data_registro = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            update_parts = []
            update_params = []
            
            for campo, novo_valor in novos_parametros.items():
                valor_atual = valores_atuais.get(campo)
                
                # Sanitização e comparação de valores numéricos
                valor_atual_num = float(valor_atual) if valor_atual is not None else 0
                novo_valor_num = float(novo_valor) if novo_valor is not None else 0
                
                if valor_atual_num != novo_valor_num:
                    
                    # Adiciona ao histórico
                    historico_updates.append((
                        paciente_id,
                        alterado_por_id,
                        campo,
                        valor_atual,    # Valor anterior
                        novo_valor_num, # Novo valor
                        data_registro
                    ))
                    
                    # Prepara o UPDATE para a tabela users
                    update_parts.append(f"{campo} = ?")
                    update_params.append(novo_valor_num)

            # 3. Atualizar a tabela users (somente se houver alteração)
            if update_params:
                update_params.append(paciente_id) # O ID do paciente vai por último
                
                query_update = "UPDATE users SET " + ", ".join(update_parts) + " WHERE id = ? AND role = 'paciente';"
                cursor.execute(query_update, tuple(update_params))
                
                # 4. Salvar o Histórico
                sql_historico = """
                    INSERT INTO historico_parametros 
                    (paciente_id, alterado_por_id, campo, valor_anterior, novo_valor, data_registro)
                    VALUES (?, ?, ?, ?, ?, ?)
                """
                cursor.executemany(sql_historico, historico_updates)

            conn.commit()
            return True
            
        except Exception as e:
            print(f"Erro ao salvar parâmetros para o paciente {paciente_id}: {e}")
            if conn:
                conn.rollback() 
            return False
        finally:
            if conn:
                conn.close()

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
                    total_carbs, 
                    total_calorias
                FROM 
                    registros
                WHERE 
                    user_id = ?
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
        """
        Retorna o dicionário de resumo para o Dashboard do Médico.
        """
        
        # 1. Total de Pacientes e Cálculo de Pendentes (Reaproveita o método que já funciona)
        pacientes = self.obter_pacientes_do_medico(medico_id)
        total_pacientes_vinculados = len(pacientes)
        
        pacientes_pendentes = sum(
            1 for p in pacientes 
            if not (p.get('ric_manha') and p.get('fator_sensibilidade') and p.get('meta_glicemia'))
        )

        # 2. Média de Glicemia (Chama o novo método)
        media_glicemia = self.calcular_media_glicemia_por_medico(medico_id)
        
        # 3. Registros Hoje (Chama o novo método)
        registros_hoje = self.contar_registros_hoje_por_medico(medico_id)
        
        return {
            'total_pacientes_vinculados': total_pacientes_vinculados, # CORRIGIDO: nome da chave para consistência
            'pacientes_pendentes': pacientes_pendentes,              # NOVO: Chave essencial para o Jinja2
            'registros_hoje': registros_hoje,
            'media_glicemia': f"{media_glicemia:.1f}" if media_glicemia else 'N/A'
        }

    def calcular_media_glicemia_por_medico(self, medico_id):
        """
        Calcula a média de todos os registros de glicemia (tipo='Glicemia' ou valor IS NOT NULL)
        dos pacientes vinculados a um médico.
        """
        conn = self.get_db_connection()
        try:
            cursor = conn.cursor()
            
            # 1. Busca os IDs dos pacientes do médico
            # Reutilizando a função que você já tem (obter_pacientes_por_medico)
            pacientes = self.obter_pacientes_do_medico(medico_id)
            if not pacientes:
                return 0.0

            paciente_ids = [p['id'] for p in pacientes]
            
            # Cria uma string de placeholders (?, ?, ?) para a cláusula IN do SQL
            placeholders = ','.join('?' for _ in paciente_ids)
            
            # 2. Executa a média nos registros desses pacientes
            sql = f"""
                SELECT AVG(valor) 
                FROM registros 
                WHERE user_id IN ({placeholders}) 
                AND valor IS NOT NULL 
                AND tipo IN ('Glicemia', 'Pre_Refeicao', 'Pos_Refeicao') 
            """
            
            cursor.execute(sql, paciente_ids)
            media = cursor.fetchone()[0]
            
            # Retorna a média ou 0.0 se for None (sem registros)
            return round(media, 1) if media is not None else 0.0
            
        except Exception as e:
            print(f"Erro ao calcular média de glicemia por médico {medico_id}: {e}")
            return 0.0
        finally:
            conn.close()


    def contar_registros_hoje_por_medico(self, medico_id):
        """
        Conta o total de registros (glicemia, refeição, etc.) feitos HOJE 
        por todos os pacientes vinculados a um médico.
        """
        conn = self.get_db_connection()
        try:
            cursor = conn.cursor()
            
            # 1. Busca os IDs dos pacientes do médico
            pacientes = self.obter_pacientes_do_medico(medico_id)
            if not pacientes:
                return 0

            paciente_ids = [p['id'] for p in pacientes]
            
            # 2. Define o início do dia de hoje (em formato string SQL)
            hoje_str = datetime.now().strftime('%Y-%m-%d')
            
            # Cria uma string de placeholders (?, ?, ?) para a cláusula IN
            placeholders = ','.join('?' for _ in paciente_ids)
            
            # 3. Executa a contagem
            # Usamos GLOB para verificar se a data_hora começa com a data de hoje
            sql = f"""
                SELECT COUNT(*) 
                FROM registros 
                WHERE user_id IN ({placeholders}) 
                AND data_hora LIKE ? || '%'
            """
            
            # O último parâmetro é o filtro de data (hoje_str)
            params = paciente_ids + [hoje_str]
            
            cursor.execute(sql, params)
            contagem = cursor.fetchone()[0]
            
            return contagem
            
        except Exception as e:
            print(f"Erro ao contar registros de hoje por médico {medico_id}: {e}")
            return 0
        finally:
            conn.close()
   
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
        # Para o filtro SQL, usamos o formato YYYY-MM-DD HH:MM:SS
        data_semana_atras_str = (hoje - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')

        try:
            # 1. Último Registro
            # Nota: A consulta está na tabela 'registros', se você moveu os dados, atualize a tabela!
            cursor.execute("""
                SELECT valor, data_hora 
                FROM registros 
                WHERE user_id = ?
                AND valor IS NOT NULL
                ORDER BY data_hora DESC 
                LIMIT 1
            """, (paciente_id,))
            ultimo = cursor.fetchone()

            if ultimo:
                valor_raw, data_hora_str = ultimo
                
                valor_glicemia = None
                data_hora_reg = None
                tempo_str = 'Erro de Data/Hora'
                status = 'secondary'

                # Tenta converter o valor
                try:
                    valor_glicemia = float(valor_raw) 
                except (TypeError, ValueError):
                    valor_glicemia = None # Se falhar, o valor não é usado
                
                # Tenta converter a data, sendo robusto contra diferentes formatos (o foco da correção)
                if valor_glicemia is not None:
                    data_hora_str_limpa = data_hora_str.replace('T', ' ')
                    
                    # Tenta formatos em ordem decrescente de precisão
                    formatos_data = [
                        '%Y-%m-%d %H:%M:%S.%f',  # Com microsssegundos (o que estava falhando: ':00')
                        '%Y-%m-%d %H:%M:%S',    # Com segundos
                        '%Y-%m-%d %H:%M'        # Sem segundos
                    ]
                    
                    for fmt in formatos_data:
                        try:
                            data_hora_reg = datetime.strptime(data_hora_str_limpa, fmt)
                            break # Se for bem-sucedido, sai do loop de formatos
                        except ValueError:
                            continue # Tenta o próximo formato

                    # Cálculo de tempo e status SÓ se a data foi convertida
                    if data_hora_reg:
                        # Cálculo de status
                        if valor_glicemia < LIMITE_HIPO:
                            status = 'warning' # Use 'warning' para hipo, como no seu template
                        elif valor_glicemia > LIMITE_HIPER:
                            status = 'danger' # Use 'danger' para hiper
                        else:
                            status = 'success'
                            
                        # Cálculo do tempo decorrido
                        delta = hoje - data_hora_reg
                        if delta.total_seconds() < 60:
                            tempo_str = "Agora mesmo"
                        elif delta.total_seconds() < 3600:
                            tempo_str = f"{int(delta.total_seconds() // 60)} min atrás"
                        elif delta.days < 1:
                            tempo_str = f"{int(delta.total_seconds() // 3600)} horas atrás"
                        else:
                            tempo_str = f"{delta.days} dias atrás"
                        
                        # Atribuição final ao resumo
                        resumo['ultimo_registro'] = {
                            'valor': valor_glicemia, 
                            'status': status, 
                            'tempo_desde_ultimo': tempo_str
                        }

            # 2. Média da Última Semana (Consulta de 7 dias)
            cursor.execute("""
                SELECT AVG(valor) 
                FROM registros 
                WHERE user_id = ? AND data_hora >= ? 
                AND valor IS NOT NULL
            """, (paciente_id, data_semana_atras_str))
            media = cursor.fetchone()[0]
            
            if media is not None:
                resumo['media_ultima_semana'] = f"{media:.1f}"

            # 3. Contagem de Eventos Extremos (Consulta de 7 dias)
            cursor.execute("""
                SELECT 
                    SUM(CASE WHEN valor < ? THEN 1 ELSE 0 END) as hipo,
                    SUM(CASE WHEN valor > ? THEN 1 ELSE 0 END) as hiper
                FROM registros 
                WHERE user_id = ? AND data_hora >= ?
            """, (LIMITE_HIPO, LIMITE_HIPER, paciente_id, data_semana_atras_str))
            
            contagens = cursor.fetchone()
            if contagens:
                resumo['hipoglicemia_count'] = contagens[0] if contagens[0] is not None else 0
                resumo['hiperglicemia_count'] = contagens[1] if contagens[1] is not None else 0
                            
        except Exception as e:
            print(f"Erro CRÍTICO ao carregar resumo do paciente: {e}")
            # Em caso de erro crítico (p. ex., falha na conexão DB), retorna o resumo vazio.
            
        finally:
            conn.close()
            
        print(f"DEBUG: Resumo Final Paciente {paciente_id}: {resumo}")
        return resumo

    def obter_parametros_clinicos(self, user_id):
        """
        Busca todos os parâmetros necessários para o cálculo do Bolus.
        Se parâmetros específicos por horário (fsi/ric) não existirem, 
        usa os valores gerais (razao_ic/fator_sensibilidade).
        """
        sql = """
            SELECT 
                meta_glicemia AS glicemia_alvo, 
                
                razao_ic AS ric_geral, 
                fator_sensibilidade AS fsi_geral,
                
                ric_manha, ric_almoco, ric_jantar,
                fsi_manha, fsi_almoco, fsi_jantar
            FROM users 
            WHERE id = ?
        """
        conn = self.get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(sql, (user_id,))
            parametros = cursor.fetchone()
            
            if not parametros:
                return None

            # Unificação: Usa o valor específico por horário, se existir. 
            # Caso contrário, usa o valor geral (ric_geral ou fsi_geral).
            # Garante que os valores necessários para o BolusService existam.
            dados_calculo = {
                'glicemia_alvo': parametros['glicemia_alvo'] or 120.0,
                # RIC
                'ric_manha': parametros['ric_manha'] or parametros['ric_geral'] or 10.0,
                'ric_almoco': parametros['ric_almoco'] or parametros['ric_geral'] or 10.0,
                'ric_jantar': parametros['ric_jantar'] or parametros['ric_geral'] or 10.0,
                'ric': parametros['ric_geral'] or 10.0, # Valor padrão para o Bolus Nutricional (caso o serviço use apenas 1)
                
                # FSI
                'fsi_manha': parametros['fsi_manha'] or parametros['fsi_geral'] or 50.0,
                'fsi_almoco': parametros['fsi_almoco'] or parametros['fsi_geral'] or 50.0,
                'fsi_jantar': parametros['fsi_jantar'] or parametros['fsi_geral'] or 50.0,
            }
            return dados_calculo

        except sqlite3.Error as e:
            print(f"Erro de DB ao obter parâmetros clínicos: {e}")
            return None
        finally:
            conn.close()


    def buscar_doses_insulina_recentes(self, user_id, horas_limite=5):
            """
            Busca todos os registros de doses de insulina aplicadas pelo paciente
            dentro do limite de tempo (ex: últimas 5 horas).
            
            Retorna uma lista de dicionários: [{'dose': X, 'data_hora': Y}, ...]
            """
            # 1. Calcular o ponto de corte no tempo
            hora_limite = datetime.now() - timedelta(hours=horas_limite)
            
            sql = """
                SELECT 
                    data_hora, 
                    dose_insulina
                FROM registros 
                WHERE 
                    user_id = ? 
                    AND dose_insulina IS NOT NULL 
                    AND data_hora >= ?
                ORDER BY data_hora DESC
            """
            conn = self.get_db_connection()
            try:
                cursor = conn.cursor()
                # O SQLite compara strings ISO 8601 corretamente
                cursor.execute(sql, (user_id, hora_limite.isoformat()))
                
                # Retorna como dicionários
                doses = [dict(row) for row in cursor.fetchall()]
                return doses
                
            except sqlite3.Error as e:
                print(f"Erro ao buscar doses de insulina recentes: {e}")
                return []
            finally:
                conn.close()
                
    def buscar_ultima_glicemia(self, user_id):
            """
            Busca a última Glicemia Capilar (GC) registrada pelo paciente.
            Retorna o valor da glicemia (float) ou None se não encontrar.
            """
            sql = """
                SELECT valor 
                FROM registros 
                WHERE user_id = ? 
                -- Filtra registros que são glicemia ou que contêm um valor de glicemia
                AND valor IS NOT NULL 
                ORDER BY data_hora DESC 
                LIMIT 1
            """
            conn = self.get_db_connection() # Use o seu método de conexão
            try:
                cursor = conn.cursor()
                cursor.execute(sql, (user_id,))
                resultado = cursor.fetchone()
                
                # Retorna o valor (índice 0) ou None
                return float(resultado[0]) if resultado and resultado[0] is not None else None
            
            except sqlite3.Error as e:
                print(f"Erro ao buscar última glicemia: {e}")
                return None
            finally:
                conn.close()

    def salvar_registro_insulina(self, user_id, dose_insulina, data_hora):
        """
        Salva uma dose de insulina Bolus aplicada pelo paciente na tabela de registros.
        """
        if dose_insulina <= 0:
            # Não salva se a dose for zero ou negativa
            return
            
        sql = """
            INSERT INTO registros 
                (user_id, tipo, dose_insulina, data_hora, observacao)
            VALUES (?, ?, ?, ?, ?)
        """
        # Usamos 'Insulina Aplicada' como tipo para diferenciar claramente
        # de uma Glicemia ou Refeição
        tipo = 'Insulina Aplicada'
        observacao = f"Bolus aplicado: {dose_insulina:.1f} UI"
        
        conn = self.get_db_connection() # Use o seu método de conexão
        try:
            cursor = conn.cursor()
            cursor.execute(sql, (user_id, tipo, dose_insulina, data_hora, observacao))
            conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Erro ao salvar registro de insulina: {e}")
            return False
        finally:
            conn.close()


    def calcular_dose_media_aplicada(self, user_id, dias=14):
        """
        Calcula a dose média de insulina aplicada pelo paciente nos últimos 'dias'.
        Usamos o campo 'dose_aplicada' da tabela 'registros'.
        """
        conn = self.get_db_connection()
        try:
            cursor = conn.cursor()
            
            # Calcula a data de início do período (ex: 14 dias atrás)
            data_inicio = (datetime.now() - timedelta(days=dias)).strftime('%Y-%m-%d %H:%M:%S')
            
            # A condição chave é que a dose_aplicada seja maior que zero
            sql = """
                SELECT AVG(dose_aplicada) 
                FROM registros 
                WHERE user_id = ?
                AND data_hora >= ?
                AND dose_aplicada IS NOT NULL 
                AND dose_aplicada > 0
            """
            
            cursor.execute(sql, (user_id, data_inicio))
            media = cursor.fetchone()[0]
            
            # Linha de DEBUG (deve ser identada)
            print(f"DEBUG: Dose Média Calculada para User {user_id}: {media}")
            
            # Retorna a média arredondada ou None se não houver registros
            if media is None:
                return None
            
            return round(media, 1) # <--- O retorno final do bloco TRY
            
        except Exception as e:
            # Bloco EXCEPT: Tratamento de erro (identado)
            print(f"Erro ao calcular dose média aplicada para o usuário {user_id}: {e}")
            return None
        finally:
            # Bloco FINALLY: Sempre executa (identado)
            conn.close()

    def obter_pacientes_vinculados(self, medico_id):
        """
        Busca pacientes vinculados a um médico específico.
        Assume que a tabela 'usuarios' armazena os parâmetros clínicos.
        """
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        # Esta query une usuários com a tabela 'vinculos' para filtrar por medico_id.
        query = """
        SELECT 
            u.id, 
            u.username, 
            u.nome_completo, 
            u.razao_ic, 
            u.fator_sensibilidade,
            u.meta_glicemia 
        FROM 
            users u
        JOIN 
            vinculos_medico_paciente v ON u.id = v.paciente_id
        WHERE 
            v.medico_id = ? AND u.role = 'paciente';
        """
        
        cursor.execute(query, (medico_id,))
        colunas = [col[0] for col in cursor.description]
        pacientes = [dict(zip(colunas, row)) for row in cursor.fetchall()]
        
        conn.close()
        return pacientes
    
    def obter_pacientes_em_alerta_detalhado(self):
        """
        Busca pacientes que tiveram registros de glicemia fora do alvo nas últimas 48 horas.
        Retorna uma lista de dicionários com dados básicos do paciente.
        """
        conn = self.get_db_connection()
        conn.row_factory = sqlite3.Row  # Garante que os resultados venham como dicionário
        cursor = conn.cursor()
        
        # 1. Encontrar o último registro e os parâmetros de meta do paciente
        # Esta query é complexa e depende da sua estrutura, mas o princípio é:
        # 2. Filtrar os pacientes cuja última glicemia ou qualquer uma nas últimas 48h
        #    está abaixo/acima da 'meta_glicemia' definida em 'users'.
        
        query = """
            SELECT DISTINCT
                u.id, u.username, u.nome_completo, u.meta_glicemia, u.medico_id
            FROM users u
            JOIN registros r ON u.id = r.user_id
            WHERE u.role = 'paciente'
            AND r.tipo_registro = 'glicemia'
            AND r.data_hora >= DATETIME('now', '-48 hours')
            AND (
                    r.valor < u.meta_glicemia - 30 OR  -- Exemplo: Hipoglicemia (ajuste o delta)
                    r.valor > u.meta_glicemia + 60    -- Exemplo: Hiperglicemia (ajuste o delta)
                )
            ORDER BY u.nome_completo;
        """
        
        # NOTA: Ajuste os deltas (30 e 60) conforme sua definição clínica de alerta.
        
        try:
            cursor.execute(query)
            pacientes = [dict(row) for row in cursor.fetchall()]
            return pacientes
        except Exception as e:
            print(f"Erro ao buscar pacientes em alerta: {e}")
            return []
        finally:
            conn.close()

         # database_manager.py (Adicione estas novas funções)

    def adicionar_insulina_config(self, user_id, nome, tipo_acao, concentracao, dose_manha=None, dose_noite=None):
        """Insere uma nova configuração de insulina para o usuário."""
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        # Primeiro, desativa qualquer insulina ATIVA do mesmo tipo de ação (Basal ou Bolus/Rápida)
        # Isso simplifica o gerenciamento: apenas uma Basal e uma Rápida podem estar ativas por vez.
        if tipo_acao in ['Basal Ultralonga', 'Basal Longa', 'Basal Intermediária']:
            cursor.execute("""
                UPDATE insulinas_config 
                SET eh_ativa = 0 
                WHERE user_id = ? AND tipo_acao LIKE 'Basal%' AND eh_ativa = 1
            """, (user_id,))
        elif tipo_acao in ['Rápida', 'Ultrarrápida', 'Regular']:
            cursor.execute("""
                UPDATE insulinas_config 
                SET eh_ativa = 0 
                WHERE user_id = ? AND tipo_acao NOT LIKE 'Basal%' AND eh_ativa = 1
            """, (user_id,))


        cursor.execute("""
            INSERT INTO insulinas_config 
            (user_id, nome_insulina, tipo_acao, concentracao, dose_basal_manha, dose_basal_noite, eh_ativa)
            VALUES (?, ?, ?, ?, ?, ?, 1)
        """, (user_id, nome, tipo_acao, concentracao, dose_manha, dose_noite))
        
        conn.commit()
        conn.close()
        return cursor.lastrowid


    def carregar_insulinas_user(self, user_id):
        """Carrega todas as insulinas configuradas para um usuário."""
        conn = self.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM insulinas_config WHERE user_id = ? ORDER BY eh_ativa DESC, id DESC
        """, (user_id,))
        insulinas = cursor.fetchall()
        conn.close()
        
        # Converte para um dicionário de dicionários (mais fácil para usar no Flask)
        return [dict(row) for row in insulinas]

    def carregar_insulina_ativa_por_acao(self, user_id, tipo_acao):
        """Carrega a insulina ativa para um determinado tipo (ex: 'Basal')."""
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        # Usa LIKE para cobrir todos os tipos de basal (Basal Ultralonga, etc.)
        if 'Basal' in tipo_acao:
            query = "tipo_acao LIKE 'Basal%'"
        else:
            # Simplifica para encontrar Rápida/Bolus (que não são 'Basal')
            query = "tipo_acao NOT LIKE 'Basal%'"

        cursor.execute(f"""
            SELECT * FROM insulinas_config 
            WHERE user_id = ? AND eh_ativa = 1 AND {query}
            ORDER BY id DESC LIMIT 1
        """, (user_id,))
        
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

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