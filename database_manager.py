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
        return {} # Retorna um dicionário vazio se o arquivo não existir

    # No seu database_manager.py

    def create_tables(self):
        # O bloco 'with' garante que a conexão será fechada ao final,
        # mesmo que ocorra um erro.
        try:
            # Use self.get_db_connection() para iniciar a conexão
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                
                # --- Criação da Tabela de Usuários ---
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY,
                        username TEXT UNIQUE NOT NULL,
                        password_hash TEXT NOT NULL,
                        role TEXT NOT NULL DEFAULT 'paciente',
                        email TEXT,
                        nome TEXT,
                        razao_ic REAL,
                        fator_sensibilidade REAL,
                        data_nascimento TEXT,
                        sexo TEXT
                    );
                """)

                # --- Criação da Tabela de Registros ---
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

                # --- Criação da Tabela de Logs ---
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS logs_acao (
                        id INTEGER PRIMARY KEY,
                        data_hora TEXT,
                        acao TEXT,
                        usuario TEXT
                    );
                """)
                
                # --- Criação da Tabela de Fichas Médicas ---
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

                # --- Criação da Tabela de Agendamentos ---
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

                # --- Criação das Tabelas de Vínculos ---
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS vinculos_medico_paciente (
                        medico_id INTEGER NOT NULL,
                        paciente_id INTEGER NOT NULL,
                        PRIMARY KEY (medico_id, paciente_id),
                        FOREIGN KEY (medico_id) REFERENCES users (id),
                        FOREIGN KEY (paciente_id) REFERENCES users (id)
                    );
                """)
                
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS vinculos_cuidador_paciente (
                        cuidador_id INTEGER NOT NULL,
                        paciente_id INTEGER NOT NULL,
                        PRIMARY KEY (cuidador_id, paciente_id),
                        FOREIGN KEY (cuidador_id) REFERENCES users (id),
                        FOREIGN KEY (paciente_id) REFERENCES users (id)
                    );
                """)
                
                # --- NOVO: Criação da tabela de Exames Laboratoriais ---
                # ATENÇÃO: Corrigi 'REFERENCES usuarios(id)' para 'REFERENCES users(id)' para coincidir com o nome da sua tabela.
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
                
                conn.commit() # Confirma todas as criações de tabela
        
        except sqlite3.Error as e:
            print(f"Erro ao criar tabelas no banco de dados: {e}")

    def _migrate_json_to_sqlite(self):
        json_data = self._load_json_data()
        if not json_data:
            return

        print("Iniciando a migração dos dados do JSON para o SQLite...")
        
        with self.get_db_connection() as conn:
            cursor = conn.cursor()

            # Migrar usuários
            users_migrated_count = 0
            for user in json_data.get('users', []):
                cursor.execute("SELECT id FROM users WHERE username = ?", (user['username'],))
                if cursor.fetchone():
                    continue
                
                cursor.execute("""
                    INSERT INTO users (id, username, password_hash, role, email, nome, razao_ic, fator_sensibilidade, data_nascimento, sexo)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (user['id'], user['username'], user['password_hash'], user.get('role', 'paciente'), user.get('email'), user.get('nome'), user.get('razao_ic'), user.get('fator_sensibilidade'), user.get('data_nascimento'), user.get('sexo')))
                users_migrated_count += 1
            
            # Migrar registros
            registros_migrated_count = 0
            for registro in json_data.get('registros_glicemia_refeicao', []):
                # Verificar se o registro já existe para evitar duplicação
                cursor.execute("SELECT id FROM registros WHERE id = ?", (registro.get('id',-1),))
                if cursor.fetchone():
                    continue
                
                # Tratamento de campos NOT NULL
                data_hora = registro.get('data_hora')
                if not data_hora:
                    data_hora = datetime.now().isoformat()
                    print(f"Atenção: 'data_hora' ausente para o registro {registro.get('id', 'desconhecido')}. Usando a data/hora atual.")

                tipo = registro.get('tipo')
                if not tipo:
                    tipo = 'Desconhecido'
                    print(f"Atenção: 'tipo' ausente para o registro {registro.get('id', 'desconhecido')}. Usando 'Desconhecido'.")

                alimentos_json_str = json.dumps(registro.get('alimentos')) if registro.get('alimentos') else None
                
                cursor.execute("""
                    INSERT INTO registros (id, user_id, data_hora, tipo, valor, observacoes, alimentos_json, total_calorias, total_carbs)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (registro.get('id'), registro['user_id'], data_hora, tipo, registro.get('valor'), registro.get('observacoes'), alimentos_json_str, registro.get('total_calorias'), registro.get('total_carbs')))
                registros_migrated_count += 1

            conn.commit()
            print(f"Migração concluída! {users_migrated_count} usuários e {registros_migrated_count} registros migrados.")

    def carregar_usuario(self, username):
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
            user_data = cursor.fetchone()
            return dict(user_data) if user_data else None

    def carregar_usuario_por_id(self, user_id):
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            user_data = cursor.fetchone()
            return dict(user_data) if user_data else None
            
    def carregar_todos_os_usuarios(self, perfil=None):
        conn = self.get_db_connection()
        cursor = conn.cursor()
        query = "SELECT id, username FROM users"
        params = ()
        if perfil:
            query += " WHERE perfil = ?"
            params = (perfil,)
        
        cursor.execute(query, params)
        usuarios = cursor.fetchall()
        conn.close()
        return [{'id': row[0], 'username': row[1]} for row in usuarios]

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
        
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO users (username, password_hash, role, email, nome, razao_ic, fator_sensibilidade, data_nascimento, sexo)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_data['username'], user_data['password_hash'], user_data.get('role', 'paciente'), user_data.get('email'), user_data.get('nome'), user_data.get('razao_ic'), user_data.get('fator_sensibilidade'), user_data.get('data_nascimento'), user_data.get('sexo')))
            conn.commit()
            return True

    def atualizar_usuario(self, user_data):
        """Atualiza os dados de um usuário existente."""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            query = """
                UPDATE users SET 
                    username = ?, email = ?, nome = ?, razao_ic = ?, 
                    fator_sensibilidade = ?, data_nascimento = ?, sexo = ?
                WHERE id = ?
            """
            cursor.execute(query, (
                user_data['username'], user_data.get('email'), user_data.get('nome'),
                user_data.get('razao_ic'), user_data.get('fator_sensibilidade'),
                user_data.get('data_nascimento'), user_data.get('sexo'), user_data['id']
            ))
            conn.commit()
            return True

    def carregar_alimentos(self):
        """Carrega todos os alimentos da tabela 'alimentos'."""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM alimentos ORDER BY alimento ASC")
            alimentos = cursor.fetchall()
            return [dict(row) for row in alimentos]
        
    def salvar_alimento(self, alimento_data):
        """Salva um novo alimento no banco de dados."""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO alimentos (alimento, medida_caseira, peso, kcal, carbs)
                    VALUES (?, ?, ?, ?, ?)
                """, (alimento_data['alimento'], alimento_data['medida_caseira'], alimento_data['peso'], alimento_data['kcal'], alimento_data['carbs']))
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                # Retorna False se o alimento já existir (se o campo 'alimento' for UNIQUE)
                return False
            except Exception as e:
                print(f"Erro ao salvar alimento: {e}")
                return False
            
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
            cursor.execute("SELECT 1 FROM vinculos_medico_paciente WHERE medico_id = ? AND paciente_id = ?", (medico_id, paciente_id))
            return cursor.fetchone() is not None
        
   # Dentro da classe DatabaseManager...

    def salvar_exame_laboratorial(self, ficha_exame: dict) -> bool:
        conn = self.get_db_connection()
        try:
            # Tenta converter para os tipos corretos ou define como None se o campo estiver vazio
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
                ficha_exame.get('data_exame'), # Salvo como TEXT 'YYYY-MM-DD'
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
        
        # Busca e ordena por data decrescente
        exames = conn.execute("""
            SELECT * FROM exames_laboratoriais
            WHERE paciente_id = ?
            ORDER BY data_exame DESC
        """, (paciente_id,)).fetchall()
        
        # Converte rows do SQLite para dicionários padrão e formata a data para objeto datetime
        result = [dict(row) for row in exames]
        conn.close()
        
        for exame in result:
            try:
                # Converte a string de data (YYYY-MM-DD) para objeto datetime para uso no Jinja
                exame['data_exame'] = datetime.strptime(exame['data_exame'], '%Y-%m-%d')
            except (ValueError, TypeError):
                pass

        return result
    
    def carregar_usuario_por_id(self, user_id: int) -> dict | None:
        conn = self.get_db_connection()
        # Busca dados essenciais do paciente
        user_data = conn.execute(
            "SELECT id, username, role, email, nome, razao_ic, fator_sensibilidade, data_nascimento, sexo FROM users WHERE id = ?", 
            (user_id,)
        ).fetchone()
        conn.close()
        
        if user_data:
            # Retorna como um dicionário
            return dict(user_data) 
        return None

    
            
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
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("INSERT INTO vinculos_medico_paciente (paciente_id, medico_id) VALUES (?, ?)", (paciente_id, medico_id))
                conn.commit()
                return True
            except sqlite3.IntegrityError:
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

    def buscar_todos_agendamentos(self):
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT a.id, a.data_hora, a.status, u.username as paciente_username, m.username as medico_username
            FROM agendamentos a
            JOIN users u ON a.paciente_id = u.id
            JOIN users m ON a.medico_id = m.id
            ORDER BY a.data_hora DESC
        """)
        
        agendamentos = [
            {'id': row[0], 
             'data_hora': row[1], 
             'status': row[2], 
             'paciente_username': row[3], 
             'medico_username': row[4],
             'data_hora_formatada': datetime.strptime(row[1], "%Y-%m-%dT%H:%M:%S.%f").strftime('%d/%m/%Y às %H:%M')
            } 
            for row in cursor.fetchall()
        ]
        conn.close()
        return agendamentos

    def obter_pacientes_por_medico(self, medico_id):
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT u.* FROM users u
                JOIN vinculos_medico_paciente v ON u.id = v.paciente_id
                WHERE v.medico_id = ?
            """, (medico_id,))
            pacientes = cursor.fetchall()
            return [dict(row) for row in pacientes]
