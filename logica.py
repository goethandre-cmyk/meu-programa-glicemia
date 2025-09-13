# logica.py

import sqlite3
import bcrypt
import json
from datetime import datetime, date, timedelta
from flask import request

# --- Funções Utilitárias (Independentes de classes) ---
# Essas funções não precisam de estado e podem ser chamadas de qualquer lugar.

def get_cor_glicemia(valor):
    """Retorna uma classe CSS baseada no valor da glicemia."""
    if valor < 70:
        return 'hipoglicemia'
    elif 70 <= valor <= 120:
        return 'glicemia-normal'
    elif 120 < valor <= 180:
        return 'glicemia-elevada'
    else:
        return 'hiperglicemia'

def get_cor_classificacao(valor):
    """Retorna a classificação de glicemia baseada no valor."""
    if valor < 70:
        return 'Baixa'
    elif 70 <= valor <= 120:
        return 'Normal'
    elif 120 < valor <= 180:
        return 'Elevada'
    else:
        return 'Muito Alta'

def get_status_class(valor_glicemia):
    """Retorna a classe CSS para a cor da linha da tabela com base no valor da glicemia."""
    if valor_glicemia < 70:
        return 'hipo'  # Hipoglicemia
    elif valor_glicemia > 180:
        return 'hiper' # Hiperglicemia
    else:
        return 'normal' # Nível normal

def calcular_bolus_detalhado(carboidratos, glicemia, meta_glicemia, razao_ic, fator_sensibilidade):
    """Calcula a dose de bolus de insulina com base em carboidratos e correção de glicemia."""
    bolus_refeicao = carboidratos / razao_ic if razao_ic else 0
    bolus_correcao = (glicemia - meta_glicemia) / fator_sensibilidade if fator_sensibilidade else 0
    bolus_total = bolus_refeicao + bolus_correcao
    return {
        "bolus_refeicao": round(bolus_refeicao, 2),
        "bolus_correcao": round(bolus_correcao, 2),
        "bolus_total": round(bolus_total, 2)
    }

def calcular_fator_sensibilidade(dtdi, tipo_insulina):
    """
    Calcula o Fator de Sensibilidade à Insulina (FS).
    dtdi: Dose Total Diária de Insulina.
    tipo_insulina: 'rápida' ou 'ultrarrápida'.
    """
    if tipo_insulina == 'ultrarrápida':
        return round(500 / dtdi, 2)
    elif tipo_insulina == 'rápida':
        return round(450 / dtdi, 2)
    else:
        return None

def _limpar_string_para_busca(texto):
    """Função interna para remover espaços, pontuações e converter para minúsculas."""
    if not isinstance(texto, str):
        return ''
    return texto.strip().lower().replace(' ', '').replace('-', '')

def _processar_dados_registro(form_data):
    """
    Processa os dados de um formulário de registro (criação ou edição)
    e retorna um dicionário com os dados formatados.
    """
    valor = float(form_data.get('valor', 0))
    refeicao = form_data.get('refeicao', '')
    observacoes = form_data.get('observacoes', '')
    data_hora_str = form_data.get('data_hora')
    data_hora = datetime.strptime(data_hora_str, '%Y-%m-%dT%H:%M')

    alimentos_selecionados = form_data.getlist('alimento_selecionado[]')
    carbs_list = form_data.getlist('carbs[]')

    alimentos_refeicao = []
    total_carbs = 0.0
    total_calorias = 0.0

    # Processa os alimentos selecionados no formulário
    for i in range(len(alimentos_selecionados)):
        alimento_nome = alimentos_selecionados[i]
        try:
            carbs_valor = float(carbs_list[i])
        except (ValueError, IndexError):
            carbs_valor = 0.0

        if alimento_nome:
            alimentos_refeicao.append({'nome': alimento_nome, 'carbs': carbs_valor})
            total_carbs += carbs_valor
            total_calorias += carbs_valor * 4  # Assumindo 4 kcal por grama de carboidrato
    
    descricao_completa = f"{refeicao}: "
    if alimentos_refeicao:
        alimentos_descricao = [f"{a['nome']} ({a['carbs']}g de CHO)" for a in alimentos_refeicao]
        descricao_completa += f"{', '.join(alimentos_descricao)}. "
    descricao_completa += f"Total Carbs: {round(total_carbs, 2)}g."
    if observacoes:
        descricao_completa += f" Obs: {observacoes}"

    return {
        'valor': valor,
        'refeicao': refeicao,
        'observacoes': observacoes,
        'data_hora': data_hora,
        'alimentos_refeicao': alimentos_refeicao,
        'total_carbs': total_carbs,
        'total_calorias': total_calorias,
        'descricao': descricao_completa
    }

# --- Classes de Lógica de Negócio ---

class DatabaseManager:
    """Gerencia a conexão e as operações do banco de dados SQLite."""
    def __init__(self, db_path='banco_de_dados.db'):
        self.db_path = db_path
        self._setup_db()

    def _get_connection(self):
        """Retorna uma conexão com o banco de dados com row_factory ativado."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _setup_db(self):
        """Cria todas as tabelas se elas ainda não existirem."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
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
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS fichas_medicas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                paciente_id INTEGER UNIQUE NOT NULL,
                condicao_atual TEXT,
                alergias TEXT,
                historico_familiar TEXT,
                medicamentos_uso TEXT,
                FOREIGN KEY (paciente_id) REFERENCES usuarios(id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS registros (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                tipo TEXT NOT NULL,
                valor REAL,
                data_hora TEXT,
                refeicao TEXT,
                alimentos_refeicao TEXT,
                observacoes TEXT,
                total_carbs REAL,
                total_calorias REAL,
                FOREIGN KEY (user_id) REFERENCES usuarios(id) ON DELETE CASCADE
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS alimentos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome_alimento TEXT NOT NULL UNIQUE,
                medida_caseira TEXT,
                peso_g REAL,
                kcal REAL,
                carbs REAL
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                usuario TEXT,
                acao TEXT NOT NULL
            )
        ''')

        conn.commit()
        conn.close()

    # --- Métodos para Usuários e Fichas Médicas ---
    def salvar_usuario(self, usuario):
        """Salva um novo usuário ou atualiza um existente."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Verifica se o usuário já existe
        cursor.execute("SELECT id FROM usuarios WHERE username = ?", (usuario['username'],))
        user_id = cursor.fetchone()

        if user_id:
            cursor.execute('''
                UPDATE usuarios SET password_hash=?, email=?, role=?, data_nascimento=?,
                sexo=?, razao_ic=?, fator_sensibilidade=?, meta_glicemia=?
                WHERE username=?
            ''', (
                usuario.get('password_hash'), usuario.get('email'), usuario.get('role'),
                usuario.get('data_nascimento'), usuario.get('sexo'), usuario.get('razao_ic'),
                usuario.get('fator_sensibilidade'), usuario.get('meta_glicemia'), usuario['username']
            ))
        else:
            cursor.execute('''
                INSERT INTO usuarios (username, password_hash, email, role, data_nascimento, sexo, razao_ic, fator_sensibilidade, meta_glicemia)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                usuario['username'], usuario['password_hash'], usuario.get('email'),
                usuario.get('role', 'paciente'), usuario.get('data_nascimento'), usuario.get('sexo'),
                usuario.get('razao_ic'), usuario.get('fator_sensibilidade'), usuario.get('meta_glicemia')
            ))
        
        conn.commit()
        conn.close()
        return True

    def carregar_usuario(self, username):
        """Carrega um único usuário pelo nome de usuário."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM usuarios WHERE username=?", (username,))
        usuario = cursor.fetchone()
        conn.close()
        return dict(usuario) if usuario else None

    def carregar_pacientes(self):
        """Carrega todos os usuários com a role 'paciente'."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM usuarios WHERE role = 'paciente'")
        pacientes = cursor.fetchall()
        conn.close()
        return [dict(row) for row in pacientes]
    
    def excluir_usuario(self, username):
        """Exclui um usuário e seus registros e ficha médica associados."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM usuarios WHERE username=?", (username,))
        conn.commit()
        conn.close()
        return True

    def salvar_ficha_medica(self, dados_ficha):
        """Salva ou atualiza a ficha médica de um paciente."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Verifica se a ficha já existe para o paciente
        cursor.execute("SELECT id FROM fichas_medicas WHERE paciente_id = ?", (dados_ficha['paciente_id'],))
        ficha_id = cursor.fetchone()

        if ficha_id:
            cursor.execute('''
                UPDATE fichas_medicas SET condicao_atual=?, alergias=?, historico_familiar=?, medicamentos_uso=?
                WHERE paciente_id=?
            ''', (
                dados_ficha['condicao_atual'], dados_ficha['alergias'],
                dados_ficha['historico_familiar'], dados_ficha['medicamentos_uso'],
                dados_ficha['paciente_id']
            ))
        else:
            cursor.execute('''
                INSERT INTO fichas_medicas (paciente_id, condicao_atual, alergias, historico_familiar, medicamentos_uso)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                dados_ficha['paciente_id'], dados_ficha['condicao_atual'],
                dados_ficha['alergias'], dados_ficha['historico_familiar'],
                dados_ficha['medicamentos_uso']
            ))
        
        conn.commit()
        conn.close()
        return True

    def carregar_ficha_medica(self, username):
        """Carrega os dados de usuário e a ficha médica de um paciente."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT
                u.*,
                fm.condicao_atual,
                fm.alergias,
                fm.historico_familiar,
                fm.medicamentos_uso
            FROM usuarios u
            LEFT JOIN fichas_medicas fm ON u.id = fm.paciente_id
            WHERE u.username = ?
        ''', (username,))
        
        paciente = cursor.fetchone()
        conn.close()
        return dict(paciente) if paciente else None
        
    # --- Métodos para Registros e Logs ---
    def salvar_registro(self, registro):
        """Salva um novo registro no banco de dados."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO registros (user_id, tipo, valor, data_hora, refeicao, alimentos_refeicao, observacoes, total_carbs, total_calorias)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            registro['user_id'], registro['tipo'], registro['valor'], registro['data_hora'],
            registro.get('refeicao'), json.dumps(registro.get('alimentos_refeicao')),
            registro.get('observacoes'), registro.get('total_carbs'), registro.get('total_calorias')
        ))
        conn.commit()
        conn.close()
        return True

    def carregar_registros(self, user_id=None):
        """Carrega registros de um usuário específico ou todos os registros."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        query = "SELECT * FROM registros"
        params = ()
        
        if user_id:
            query += " WHERE user_id = ?"
            params = (user_id,)
        
        query += " ORDER BY data_hora DESC"
        
        cursor.execute(query, params)
        registros = cursor.fetchall()
        conn.close()
        
        lista_registros = []
        for row in registros:
            reg = dict(row)
            try:
                if reg.get('alimentos_refeicao'):
                    reg['alimentos_refeicao'] = json.loads(reg['alimentos_refeicao'])
                if reg.get('data_hora'):
                    reg['data_hora'] = datetime.fromisoformat(reg['data_hora'])
            except (json.JSONDecodeError, ValueError):
                continue
            lista_registros.append(reg)
            
        return lista_registros

    def encontrar_registro(self, registro_id):
        """Encontra um registro pelo seu ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM registros WHERE id=?", (registro_id,))
        registro = cursor.fetchone()
        conn.close()
        
        if registro:
            reg = dict(registro)
            try:
                if reg.get('alimentos_refeicao'):
                    reg['alimentos_refeicao'] = json.loads(reg['alimentos_refeicao'])
                if reg.get('data_hora'):
                    reg['data_hora'] = datetime.fromisoformat(reg['data_hora'])
            except (json.JSONDecodeError, ValueError):
                return None
            return reg
        return None
    
    def atualizar_registro(self, registro_id, dados):
        """Atualiza um registro existente."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE registros SET valor=?, tipo=?, refeicao=?, alimentos_refeicao=?, total_carbs=?, total_calorias=?, observacoes=?
            WHERE id=?
        ''', (
            dados['valor'], dados['tipo'], dados.get('refeicao'),
            json.dumps(dados.get('alimentos_refeicao')), dados.get('total_carbs'),
            dados.get('total_calorias'), dados.get('observacoes'), registro_id
        ))
        conn.commit()
        conn.close()
        return True

    def excluir_registro(self, registro_id):
        """Exclui um registro pelo seu ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM registros WHERE id=?", (registro_id,))
        conn.commit()
        conn.close()
        return True

    def salvar_log_acao(self, acao, usuario):
        """Salva um log de ação no banco de dados."""
        conn = self._get_connection()
        cursor = conn.cursor()
        timestamp = datetime.now().isoformat()
        cursor.execute('''
            INSERT INTO logs (timestamp, acao, usuario)
            VALUES (?, ?, ?)
        ''', (timestamp, acao, usuario))
        conn.commit()
        conn.close()
        return True

    # --- Métodos para Alimentos ---
    def salvar_alimento(self, alimento_data):
        """Salva um novo alimento no banco de dados."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO alimentos (nome_alimento, medida_caseira, peso_g, kcal, carbs)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                _limpar_string_para_busca(alimento_data.get('ALIMENTO')),
                alimento_data.get('MEDIDA CASEIRA'),
                alimento_data.get('PESO (g/ml)'),
                alimento_data.get('Kcal'),
                alimento_data.get('CHO (g)')
            ))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()

    def buscar_alimentos(self, termo):
        """Busca alimentos no banco de dados por termo no nome."""
        conn = self._get_connection()
        cursor = conn.cursor()
        termo = f'%{_limpar_string_para_busca(termo)}%'
        cursor.execute("SELECT * FROM alimentos WHERE nome_alimento LIKE ? ORDER BY nome_alimento ASC", (termo,))
        resultados = cursor.fetchall()
        conn.close()
        return [dict(row) for row in resultados]


class AuthManager:
    """Gerencia a autenticação e dados de usuário."""
    def __init__(self, db_manager):
        self.db_manager = db_manager

    def salvar_usuario(self, username, password, role='paciente', **kwargs):
        """Cadastra um novo usuário com senha hasheada."""
        if self.db_manager.carregar_usuario(username):
            return False, "Nome de usuário já existe."

        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        novo_usuario = {
            "username": username,
            "password_hash": hashed_password,
            "role": role,
            **kwargs
        }
        
        self.db_manager.salvar_usuario(novo_usuario)
        return True, "Cadastro bem-sucedido."
    
    def atualizar_perfil_usuario(self, username, dados_perfil, nova_senha=None):
        """Atualiza o perfil de um usuário."""
        usuario_existente = self.db_manager.carregar_usuario(username)
        if not usuario_existente:
            return False

        # Converte o objeto Row para um dicionário mutável
        usuario_atualizado = dict(usuario_existente)
        usuario_atualizado.update(dados_perfil)
        
        if nova_senha:
            usuario_atualizado['password_hash'] = bcrypt.hashpw(nova_senha.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        self.db_manager.salvar_usuario(usuario_atualizado)
        return True

    def verificar_login(self, username, password):
        """Verifica as credenciais do usuário com a senha hasheada."""
        usuario = self.db_manager.carregar_usuario(username)
        if usuario:
            try:
                if bcrypt.checkpw(password.encode('utf-8'), usuario['password_hash'].encode('utf-8')):
                    return usuario, "Login bem-sucedido."
            except (KeyError, ValueError, TypeError):
                pass
        return None, "Credenciais inválidas. Tente novamente."


class AppCore:
    """A camada de aplicação que coordena a lógica de negócio."""
    def __init__(self, db_manager):
        self.db_manager = db_manager
        
    def salvar_log_acao(self, acao, usuario):
        """Salva uma ação do usuário no banco de dados."""
        self.db_manager.salvar_log_acao(acao, usuario)
        return True

    def adicionar_registro(self, usuario, **kwargs):
        """Adiciona um novo registro ao banco de dados."""
        user_info = self.db_manager.carregar_usuario(usuario)
        if not user_info:
            return False, "Usuário não encontrado."
        
        novo_registro = {
            'user_id': user_info['id'],
            'data_hora': kwargs.get('data_hora', datetime.now()).isoformat(),
            'tipo': kwargs.get('tipo'),
            'valor': kwargs.get('valor'),
            'refeicao': kwargs.get('refeicao'),
            'alimentos_refeicao': kwargs.get('alimentos_refeicao', []),
            'total_carbs': kwargs.get('total_carbs'),
            'total_calorias': kwargs.get('total_calorias'),
            'observacoes': kwargs.get('observacoes')
        }
        self.db_manager.salvar_registro(novo_registro)
        return True, "Registro adicionado com sucesso."

    def mostrar_registros(self, usuario_filtro=None):
        """Retorna uma lista de registros, opcionalmente filtrada por usuário."""
        if usuario_filtro:
            user_info = self.db_manager.carregar_usuario(usuario_filtro)
            if not user_info:
                return []
            return self.db_manager.carregar_registros(user_id=user_info['id'])
        return self.db_manager.carregar_registros()

    def encontrar_registro(self, registro_id):
        """Encontra um registro pelo ID."""
        return self.db_manager.encontrar_registro(registro_id)
        
    def atualizar_registro(self, registro_id, dados):
        """Atualiza um registro existente no banco de dados."""
        return self.db_manager.atualizar_registro(registro_id, dados)
        
    def excluir_registro(self, registro_id):
        """Exclui um registro pelo ID."""
        return self.db_manager.excluir_registro(registro_id)

    def salvar_alimento_json(self, alimento_data):
        """Salva um novo alimento na base de dados (agora no banco de dados)."""
        return self.db_manager.salvar_alimento(alimento_data)
        
    def pesquisar_alimentos(self, termo_pesquisa):
        """Busca alimentos na base de dados por nome."""
        return self.db_manager.buscar_alimentos(termo_pesquisa)
        
    def get_resumo_dashboard(self, username):
        """
        Retorna um dicionário com dados resumidos do dashboard para um usuário.
        Esta lógica agora usa os registros diretamente do banco de dados.
        """
        registros = self.mostrar_registros(usuario_filtro=username)
        
        resumo_dados = {
            'media_ultima_semana': None,
            'hipoglicemia_count': 0,
            'hiperglicemia_count': 0,
            'ultimo_registro': None,
            'tempo_desde_ultimo': None,
            'total_calorias_diarias': 0.0
        }
        
        if not registros:
            return resumo_dados

        # Encontra o último registro
        ultimo_registro = registros[0]
        resumo_dados['ultimo_registro'] = ultimo_registro
        
        # Calcula o tempo desde o último registro
        agora = datetime.now()
        delta = agora - ultimo_registro['data_hora']
        if delta.days > 0:
            resumo_dados['tempo_desde_ultimo'] = f"{delta.days} dias atrás"
        elif delta.seconds >= 3600:
            horas = delta.seconds // 3600
            resumo_dados['tempo_desde_ultimo'] = f"{horas} horas atrás"
        else:
            minutos = delta.seconds // 60
            resumo_dados['tempo_desde_ultimo'] = f"{minutos} minutos atrás"

        # Filtra registros da última semana, conta hipo/hiper e soma calorias
        sete_dias_atras = agora - timedelta(days=7)
        hoje = date.today()
        glicemias_ultima_semana = []
        
        for reg in registros:
            if reg['data_hora'] > sete_dias_atras:
                glicemias_ultima_semana.append(reg['valor'])
            
            if 'total_calorias' in reg and reg['data_hora'].date() == hoje:
                resumo_dados['total_calorias_diarias'] += reg['total_calorias']
            
            if reg['valor'] < 70:
                resumo_dados['hipoglicemia_count'] += 1
            elif reg['valor'] > 180:
                resumo_dados['hiperglicemia_count'] += 1
                
        if glicemias_ultima_semana:
            media = sum(glicemias_ultima_semana) / len(glicemias_ultima_semana)
            resumo_dados['media_ultima_semana'] = round(media, 2)
        
        resumo_dados['total_calorias_diarias'] = round(resumo_dados['total_calorias_diarias'], 2)
        return resumo_dados