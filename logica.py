import sqlite3
import bcrypt
import json
from datetime import datetime, date, timedelta
from typing import Optional, Dict, List, Any
import pandas as pd

# --- Funções Utilitárias ---
def get_cor_glicemia(valor):
    """Retorna uma cor de alerta para um valor de glicemia."""
    if valor < 70:
        return 'warning-hipo'
    if valor > 180:
        return 'warning-hiper'
    if valor > 140:
        return 'warning-pre'
    return 'success'

def get_cor_classificacao(classificacao):
    """Retorna uma cor de alerta para a classificação de uma refeição."""
    if 'Muito Baixa' in classificacao or 'Muito Alta' in classificacao:
        return 'warning'
    if 'Normal' in classificacao:
        return 'success'
    return 'info'

def calcular_fator_sensibilidade(dtdi: float, tipo_insulina: str) -> float:
    """Calcula o Fator de Sensibilidade à Insulina (FS)."""
    if tipo_insulina.lower() == 'rápida':
        # Regra 1800
        return 1800 / dtdi
    elif tipo_insulina.lower() == 'regular':
        # Regra 1500
        return 1500 / dtdi
    else:
        return 0

def calcular_bolus_detalhado(carbs: float, glicemia_momento: float, meta_glicemia: float, razao_ic: float, fator_sensibilidade: float) -> Dict[str, Any]:
    """Calcula a dose de insulina (bolus) detalhadamente."""
    bolus_refeicao = carbs / razao_ic
    bolus_correcao = (glicemia_momento - meta_glicemia) / fator_sensibilidade
    bolus_total = bolus_refeicao + bolus_correcao
    
    return {
        'bolus_refeicao': round(bolus_refeicao, 2),
        'bolus_correcao': round(bolus_correcao, 2),
        'bolus_total': round(bolus_total, 2)
    }

def _processar_dados_registro(form_data: Dict[str, Any]) -> Dict[str, Any]:
    """Processa e valida os dados de um formulário de registro de glicemia."""
    valor = float(form_data['valor_glicemia'])
    data_hora = datetime.strptime(form_data['data_hora'], '%Y-%m-%dT%H:%M')
    
    alimentos_refeicao_str = form_data.get('alimentos_refeicao', '[]')
    alimentos_refeicao_list = json.loads(alimentos_refeicao_str)
    
    total_carbs = sum(item.get('CHO (g)', 0) for item in alimentos_refeicao_list)
    total_calorias = sum(item.get('Kcal', 0) for item in alimentos_refeicao_list)
    
    return {
        'valor': valor,
        'data_hora': data_hora,
        'alimentos_refeicao': alimentos_refeicao_list,
        'observacoes': form_data.get('observacoes', ''),
        'total_carbs': total_carbs,
        'total_calorias': total_calorias
    }

def get_status_class(valor_glicemia):
    """Retorna uma classe CSS para o status da glicemia."""
    if valor_glicemia < 70:
        return 'status-hipo'
    elif valor_glicemia > 180:
        return 'status-hiper'
    else:
        return 'status-normal'

# --- Classes de Lógica de Negócio ---

class DatabaseManager:
    """Gerencia a conexão e operações do banco de dados SQLite."""
    def __init__(self, db_path='app.db'):
        self.db_path = db_path
        self.setup_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Retorna uma conexão com o banco de dados com row_factory ativado."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def setup_db(self):
        """Cria todas as tabelas se elas ainda não existirem."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.executescript('''
                CREATE TABLE IF NOT EXISTS usuarios (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL,
                    email TEXT,
                    data_nascimento TEXT,
                    sexo TEXT,
                    razao_ic REAL,
                    fator_sensibilidade REAL,
                    meta_glicemia REAL
                );
                
                CREATE TABLE IF NOT EXISTS fichas_medicas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    paciente_id INTEGER UNIQUE NOT NULL,
                    condicao_atual TEXT,
                    alergias TEXT,
                    historico_familiar TEXT,
                    medicamentos_uso TEXT,
                    FOREIGN KEY (paciente_id) REFERENCES usuarios(id) ON DELETE CASCADE
                );
                
                CREATE TABLE IF NOT EXISTS registros (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    tipo TEXT NOT NULL,
                    valor REAL,
                    data_hora TEXT,
                    alimentos_refeicao TEXT,
                    observacoes TEXT,
                    total_carbs REAL,
                    total_calorias REAL,
                    FOREIGN KEY (user_id) REFERENCES usuarios(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS alimentos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alimento TEXT NOT NULL UNIQUE,
                    medida_caseira TEXT,
                    peso_g REAL,
                    kcal REAL,
                    carbs REAL
                );
                
                CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    usuario TEXT,
                    acao TEXT NOT NULL
                );
            ''')
            conn.commit()
    
    def salvar_usuario(self, username, password, email=None, role='paciente', **kwargs):
        """Salva um novo usuário no banco de dados."""
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO usuarios (username, password_hash, role, email, data_nascimento, sexo, razao_ic, fator_sensibilidade)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    username, password_hash, role, email,
                    kwargs.get('data_nascimento'), kwargs.get('sexo'),
                    kwargs.get('razao_ic'), kwargs.get('fator_sensibilidade')
                ))
                conn.commit()
            return True, "Usuário salvo com sucesso!"
        except sqlite3.IntegrityError:
            return False, "Nome de usuário já existe."

    def verificar_login(self, username, password):
        """Verifica as credenciais de login de um usuário."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM usuarios WHERE username = ?', (username,))
            usuario = cursor.fetchone()
            
            if usuario and bcrypt.checkpw(password.encode('utf-8'), usuario['password_hash'].encode('utf-8')):
                return usuario, "Login bem-sucedido!"
            
            return None, "Nome de usuário ou senha incorretos."

    def carregar_todos_usuarios(self):
        """Carrega todos os usuários, independente da função."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM usuarios')
            return cursor.fetchall()

    def carregar_usuario(self, username):
        """Carrega os dados de um usuário pelo nome de usuário."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM usuarios WHERE username = ?', (username,))
            return cursor.fetchone()
    
    def carregar_pacientes(self):
        """Carrega todos os usuários com o papel 'paciente'."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM usuarios WHERE role = "paciente"')
            return cursor.fetchall()
            
    def atualizar_perfil_usuario(self, username, dados, nova_senha=None):
        """Atualiza o perfil de um usuário com base em dados fornecidos."""
        set_clause = ", ".join([f"{key} = ?" for key in dados.keys() if dados[key] is not None])
        values = [v for v in dados.values() if v is not None]
        
        if nova_senha:
            password_hash = bcrypt.hashpw(nova_senha.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            set_clause += ", password_hash = ?"
            values.append(password_hash)
            
        values.append(username)
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE usuarios SET {set_clause} WHERE username = ?", values)
            conn.commit()
    
    def excluir_usuario(self, username):
        """Exclui um usuário e todos os seus registros."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM usuarios WHERE username = ?', (username,))
            conn.commit()
            return cursor.rowcount > 0

    def salvar_ficha_medica(self, dados_ficha: Dict[str, Any]):
        """Salva ou atualiza a ficha médica de um paciente."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO fichas_medicas (paciente_id, condicao_atual, alergias, historico_familiar, medicamentos_uso)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                dados_ficha['paciente_id'], dados_ficha['condicao_atual'],
                dados_ficha['alergias'], dados_ficha['historico_familiar'],
                dados_ficha['medicamentos_uso']
            ))
            conn.commit()

    def carregar_ficha_medica(self, username: str) -> Optional[Dict[str, Any]]:
        """Carrega a ficha médica de um paciente pelo nome de usuário."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT u.*, fm.*
                FROM usuarios u
                LEFT JOIN fichas_medicas fm ON u.id = fm.paciente_id
                WHERE u.username = ? AND u.role = 'paciente'
            ''', (username,))
            return cursor.fetchone()

    def adicionar_registro(self, user_id, tipo, valor, data_hora, alimentos_refeicao, observacoes, total_carbs, total_calorias):
        """Adiciona um novo registro de glicemia no banco de dados."""
        alimentos_json = json.dumps(alimentos_refeicao)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO registros (user_id, tipo, valor, data_hora, alimentos_refeicao, observacoes, total_carbs, total_calorias)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, tipo, valor, data_hora, alimentos_json, observacoes, total_carbs, total_calorias))
            conn.commit()
            
    def encontrar_registro(self, registro_id: int):
        """Busca um registro pelo ID e carrega os dados da refeição."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT r.*, u.username FROM registros r JOIN usuarios u ON r.user_id = u.id WHERE r.id = ?', (registro_id,))
            registro = cursor.fetchone()
            if registro:
                registro_dict = dict(registro)
                if registro_dict.get('alimentos_refeicao'):
                    registro_dict['alimentos_refeicao'] = json.loads(registro_dict['alimentos_refeicao'])
                if registro_dict.get('data_hora'):
                    registro_dict['data_hora'] = datetime.fromisoformat(registro_dict['data_hora'])
                return registro_dict
            return None

    def atualizar_registro(self, registro_id, tipo, valor, data_hora, alimentos_refeicao, observacoes, total_carbs, total_calorias):
        """Atualiza um registro de glicemia existente."""
        alimentos_json = json.dumps(alimentos_refeicao)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE registros SET tipo = ?, valor = ?, data_hora = ?, alimentos_refeicao = ?, observacoes = ?, total_carbs = ?, total_calorias = ?
                WHERE id = ?
            ''', (tipo, valor, data_hora, alimentos_json, observacoes, total_carbs, total_calorias, registro_id))
            conn.commit()

    def excluir_registro(self, registro_id: int) -> bool:
        """Exclui um registro do banco de dados pelo ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM registros WHERE id = ?', (registro_id,))
            conn.commit()
            return cursor.rowcount > 0

    def mostrar_registros(self, usuario_filtro: Optional[str] = None):
        """Exibe registros de glicemia, filtrando por usuário se necessário."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = """
                SELECT r.*, u.username
                FROM registros r
                JOIN usuarios u ON r.user_id = u.id
            """
            params = ()
            if usuario_filtro:
                query += " WHERE u.username = ?"
                params = (usuario_filtro,)
            
            query += " ORDER BY r.data_hora DESC"
            
            cursor.execute(query, params)
            registros = cursor.fetchall()
            
            registros_processados = []
            for reg in registros:
                reg_dict = dict(reg)
                reg_dict['data_hora'] = datetime.fromisoformat(reg_dict['data_hora'])
                if reg_dict['alimentos_refeicao']:
                    try:
                        reg_dict['alimentos_refeicao'] = json.loads(reg_dict['alimentos_refeicao'])
                    except (json.JSONDecodeError, TypeError):
                        reg_dict['alimentos_refeicao'] = []
                registros_processados.append(reg_dict)
            return registros_processados
    
    def salvar_log_acao(self, acao: str, usuario: Optional[str] = None):
        """Salva uma ação do usuário no log de ações."""
        timestamp = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT INTO logs (timestamp, usuario, acao) VALUES (?, ?, ?)',
                            (timestamp, usuario, acao))
            conn.commit()

    def pesquisar_alimentos(self, termo: str) -> List[Dict[str, Any]]:
        """Pesquisa alimentos no banco de dados com base em um termo."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            termo = f"%{termo}%"
            cursor.execute("SELECT * FROM alimentos WHERE alimento LIKE ? LIMIT 10", (termo,))
            return [dict(row) for row in cursor.fetchall()]

    def salvar_alimento_csv(self, alimento_data: Dict[str, Any]) -> bool:
        """Salva um alimento no banco de dados, mapeando a partir das colunas do CSV."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO alimentos (alimento, medida_caseira, peso_g, kcal, carbs)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    alimento_data.get('ALIMENTO'),
                    alimento_data.get('MEDIDA CASEIRA'),
                    alimento_data.get('PESO (g/ml)'),
                    alimento_data.get('Kcal'),
                    alimento_data.get('CHO (g)')
                ))
                conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def importar_alimentos_csv(self, filename: str) -> int:
        """Importa alimentos de um arquivo CSV para o banco de dados."""
        try:
            df = pd.read_csv(filename, sep='\t')
            df = df.rename(columns={'CHO (g)': 'CHO (g)'})
            df = df.fillna('')
            records_imported = 0
            for index, row in df.iterrows():
                row_dict = row.to_dict()
                if self.salvar_alimento_csv(row_dict):
                    records_imported += 1
            return records_imported
        except FileNotFoundError:
            print(f"Erro: O arquivo {filename} não foi encontrado.")
            return 0
        except Exception as e:
            print(f"Ocorreu um erro durante a importação do CSV: {e}")
            return 0
    
    def obter_dados_glicemia_json(self, user_id):
        """Retorna dados de glicemia para o gráfico em formato JSON."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT data_hora, valor FROM registros
                WHERE user_id = ? AND valor IS NOT NULL
                ORDER BY data_hora
            """, (user_id,))
            registros = cursor.fetchall()

            labels = [datetime.strptime(reg['data_hora'], '%Y-%m-%d %H:%M:%S').strftime('%d/%m %H:%M') for reg in registros]
            data = [reg['valor'] for reg in registros]
            return {'labels': labels, 'data': data}

    def obter_dados_carbs_diarios(self, user_id):
        """Obtém o total de carboidratos por dia para um usuário."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT data_hora, total_carbs FROM registros
                WHERE user_id = ? AND total_carbs IS NOT NULL
                ORDER BY data_hora
            """, (user_id,))
            
            registros = cursor.fetchall()
            
            dados_diarios = {}
            for registro in registros:
                data_hora, total_carbs = registro['data_hora'], registro['total_carbs']
                
                # Extrai a data do registro
                data = datetime.strptime(data_hora, '%Y-%m-%d %H:%M:%S').date()
                data_str = data.isoformat()
                
                if data_str in dados_diarios:
                    dados_diarios[data_str] += total_carbs
                else:
                    dados_diarios[data_str] = total_carbs
            
            # Formata os dados para o gráfico
            labels = sorted(dados_diarios.keys())
            data = [dados_diarios[key] for key in labels]
            
            return {'labels': labels, 'data': data}

    def obter_dados_calorias_diarias(self, user_id):
        """Obtém o total de calorias por dia para um usuário."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT data_hora, total_calorias FROM registros
                WHERE user_id = ? AND total_calorias IS NOT NULL
                ORDER BY data_hora
            """, (user_id,))
            
            registros = cursor.fetchall()
            
            dados_diarios = {}
            for registro in registros:
                data_hora, total_calorias = registro['data_hora'], registro['total_calorias']
                
                data = datetime.strptime(data_hora, '%Y-%m-%d %H:%M:%S').date()
                data_str = data.isoformat()
                
                if data_str in dados_diarios:
                    dados_diarios[data_str] += total_calorias
                else:
                    dados_diarios[data_str] = total_calorias
            
            labels = sorted(dados_diarios.keys())
            data = [dados_diarios[key] for key in labels]
            
            return {'labels': labels, 'data': data}


class AuthManager:
    """Gerencia a lógica de autenticação de usuários."""
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    def salvar_usuario(self, username, password, **kwargs):
        return self.db_manager.salvar_usuario(username, password, **kwargs)

    def verificar_login(self, username, password):
        return self.db_manager.verificar_login(username, password)
    
    def atualizar_perfil_usuario(self, username, dados, nova_senha=None):
        return self.db_manager.atualizar_perfil_usuario(username, dados, nova_senha)


class AppCore:
    """Gerencia a lógica principal da aplicação, como registros e relatórios."""
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    def salvar_log_acao(self, acao: str, usuario: Optional[str] = None):
        self.db_manager.salvar_log_acao(acao, usuario)
        
    def adicionar_registro(self, usuario: str, tipo: str, **kwargs):
        user = self.db_manager.carregar_usuario(usuario)
        if user:
            self.db_manager.adicionar_registro(user['id'], tipo, **kwargs)

    def mostrar_registros(self, usuario_filtro: Optional[str] = None):
        return self.db_manager.mostrar_registros(usuario_filtro)
    
    def encontrar_registro(self, registro_id: int):
        return self.db_manager.encontrar_registro(registro_id)

    def atualizar_registro(self, registro_id: int, tipo: str, **kwargs):
        return self.db_manager.atualizar_registro(registro_id, tipo, **kwargs)

    def excluir_registro(self, registro_id: int) -> bool:
        return self.db_manager.excluir_registro(registro_id)

    def salvar_alimento_json(self, novo_alimento_data: Dict[str, Any]) -> bool:
        """Salva um alimento a partir de um JSON."""
        with self.db_manager._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('''
                    INSERT INTO alimentos (alimento, medida_caseira, peso_g, kcal, carbs)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    novo_alimento_data.get("ALIMENTO"),
                    novo_alimento_data.get("MEDIDA CASEIRA"),
                    novo_alimento_data.get("PESO (g/ml)"),
                    novo_alimento_data.get("Kcal"),
                    novo_alimento_data.get("CHO (g)")
                ))
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False

    def pesquisar_alimentos(self, termo: str) -> List[Dict[str, Any]]:
        return self.db_manager.pesquisar_alimentos(termo)
        
    def get_resumo_dashboard(self, username):
        """Calcula dados de resumo para o dashboard do paciente."""
        registros = self.mostrar_registros(usuario_filtro=username)
        
        glicemias_recentes = [r['valor'] for r in registros if r['valor'] is not None and (datetime.now() - r['data_hora']).days <= 7]
        total_calorias_diarias = 0
        if registros:
            hoje = datetime.now().date()
            registros_hoje = [r for r in registros if r['data_hora'].date() == hoje]
            total_calorias_diarias = sum(r['total_calorias'] for r in registros_hoje)
        
        media_glicemia = sum(glicemias_recentes) / len(glicemias_recentes) if glicemias_recentes else 0
        
        return {
            'media_glicemia': round(media_glicemia, 1),
            'total_calorias_diarias': round(total_calorias_diarias, 1),
            'numero_registros': len(registros)
        }