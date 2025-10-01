"""" ========||||||APP.PY ANTIGO||||||======== """""

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from functools import wraps
import json
import logging
import plotly.graph_objects as go
import numpy as np
import os
from relatorios import relatorios_bp

# Certifique-se de que DatabaseManager está disponível
# from database_manager import DatabaseManager 

# --- Configuração da Aplicação ---
app = Flask(__name__)

# Após a inicialização do Flask e antes das rotas
app.register_blueprint(relatorios_bp)
# OU, se quiser um prefixo de URL:
# app.register_blueprint(relatorios_bp, url_prefix='/relatorios')
app.secret_key = 'sua_chave_secreta_aqui' 
app.logger.setLevel(logging.INFO)

# --- Inicialização das Classes ---
db_path = os.path.join('data', 'glicemia.db')

# AVISO: Esta linha assume a existência da classe DatabaseManager. 
# Se esta classe não estiver definida no seu ambiente, ocorrerá um erro de NameError.
try:
    from database_manager import DatabaseManager
    db_manager = DatabaseManager()
except ImportError:
    app.logger.error("A classe DatabaseManager não foi encontrada. Substitua com sua implementação real.")
    # Adicionar um mock para evitar quebra total, mas o código não funcionará corretamente sem o DB
    class MockDatabaseManager:
        def carregar_usuario(self, username): return None
        def carregar_usuario_por_id(self, user_id): return None
        def salvar_log_acao(self, acao, usuario): pass
        def carregar_registros(self, user_id): return []
        def carregar_alimentos(self): return []
        def encontrar_registro(self, id): return None
        def excluir_registro(self, id): return False
        def atualizar_registro(self, registro): return False
        def carregar_todos_os_usuarios(self, perfil=None): return []
        def carregar_medicos(self): return []
        def atualizar_usuario(self, usuario): return False
        def excluir_usuario(self, username): return False
        def salvar_usuario(self, novo_usuario): return True
        def obter_pacientes_por_medico(self, medico_id): return []
        def medico_tem_acesso_a_paciente(self, medico_id, paciente_id): return True
        def carregar_ficha_medica(self, paciente_id): return {}
        def salvar_ficha_medica(self, ficha_data): return True
        def buscar_agendamentos_paciente(self, paciente_id): return []
        def atualizar_status_agendamento(self, agendamento_id, status): return True
        def buscar_todos_agendamentos(self): return []
        def get_user_id_by_username(self, username): return 1
        def salvar_agendamento(self, paciente_id, medico_id, data_hora, obs): return True
        def carregar_todos_os_usuarios(self, perfil=None): return []
        def carregar_cuidadores(self): return []
        def vincular_paciente_medico(self, paciente_id, medico_id): return True
        def salvar_alimento(self, alimento_data): return True
        def excluir_alimento(self, id): return True
        def buscar_exames_paciente(self, paciente_id): return []
        def salvar_exame_laboratorial(self, exame_data): return True
        def vincular_cuidador_paciente(self, cuidador_username, paciente_username): return True

    db_manager = MockDatabaseManager()


login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


# Adiciona a função ao ambiente Jinja2 (para usar em templates)
app.jinja_env.globals['from_json'] = json.loads

# Adiciona o filtro para JSON
def from_json_filter(json_string):
    if json_string:
        try:
            # Tenta decodificar a string JSON
            return json.loads(json_string)
        except (json.JSONDecodeError, TypeError):
            # Se a string não for um JSON válido ou for None
            return []
    return []

app.jinja_env.filters['from_json'] = from_json_filter


# Funções de ajuda para os templates (AppCore)
class AppCore:
    def __init__(self, db_manager):
        self.db_manager = db_manager

    def salvar_log_acao(self, acao, usuario):
        self.db_manager.salvar_log_acao(acao, usuario)

    # Tipos de Refeição Consolidado
    def obter_tipos_refeicao(self):
        # Consolida a lista de tipos de refeição de várias rotas do seu código
        return ['Jejum', 'Café da Manhã', 'Almoço', 'Janta', 'Lanche', 'Colação', 'Refeição']
    
    def encontrar_registro(self, registro_id):
        return self.db_manager.encontrar_registro(registro_id)

    def excluir_registro(self, registro_id):
        return self.db_manager.excluir_registro(registro_id)

    def carregar_dados_analise(self, user_id):
        # Implementação da função de análise
        pass
        
def carregar_dados_dashboard(user_id):
    """
    Carrega e processa os dados de glicemia para o dashboard.
    """
    # Use sua classe DatabaseManager para buscar os dados
    registros = db_manager.carregar_registros(user_id)
    
    # Inicializa os dados para o dashboard
    resumo_dados = {
        'ultimo_registro': None,
        'media_ultima_semana': 'N/A',
        'hiperglicemia_count': 0,
        'hipoglicemia_count': 0
    }
    
    if not registros:
        return resumo_dados

    # Encontra o último registro de glicemia
    registros_glicemia = [
        r for r in registros 
        if r.get('tipo') in ['Glicemia'] and r.get('data_hora') and r.get('valor') is not None
    ]
    registros_glicemia.sort(key=lambda x: datetime.fromisoformat(x['data_hora']) if isinstance(x['data_hora'], str) else datetime.min, reverse=True)
    
    if registros_glicemia:
        ultimo_registro = registros_glicemia[0]
        data_hora_ultimo = datetime.fromisoformat(ultimo_registro['data_hora'])
        tempo_passado = datetime.now() - data_hora_ultimo
        
        # Formata o tempo para exibição
        if tempo_passado.total_seconds() < 60:
            tempo_str = f"{int(tempo_passado.total_seconds())} segundos atrás"
        elif tempo_passado.total_seconds() < 3600:
            tempo_str = f"{int(tempo_passado.total_seconds() / 60)} minutos atrás"
        elif tempo_passado.total_seconds() < 86400:
            tempo_str = f"{int(tempo_passado.total_seconds() / 3600)} horas atrás"
        else:
            tempo_str = f"{int(tempo_passado.total_seconds() / 86400)} dias atrás"

        resumo_dados['ultimo_registro'] = {
            'valor': "%.1f" % ultimo_registro.get('valor', 0),
            'tempo_desde_ultimo': tempo_str
        }

    # Filtra os dados da última semana e calcula a média e eventos extremos
    data_limite = datetime.now() - timedelta(days=7)
    glicemias_semana = []
    
    for r in registros_glicemia:
        data_hora = datetime.fromisoformat(r['data_hora']) if isinstance(r.get('data_hora'), str) else datetime.min
        if data_hora >= data_limite:
            glicemias_semana.append(r['valor'])
            # Conta eventos extremos
            if r['valor'] < 70:
                resumo_dados['hipoglicemia_count'] += 1
            elif r['valor'] > 180:
                resumo_dados['hiperglicemia_count'] += 1
    
    if glicemias_semana:
        media = sum(glicemias_semana) / len(glicemias_semana)
        resumo_dados['media_ultima_semana'] = "%.1f" % media
    
    return resumo_dados

# Lista de Especialidades Médicas
ESPECIALIDADES_MEDICAS = [
    "Acupuntura", "Alergia e Imunologia", "Anestesiologista", "Angiologia", "Cardiologia",
    "Cirurgia Cardiovascular", "Cirurgia da Mão", "Cirurgia de Cabeça e Pescoço", "Cirurgia do Aparelho Digestivo", 
    "Cirurgia Geral", "Cirurgia Oncológica", "Cirurgia Pediátrica", "Cirurgia Plástica", 
    "Cirurgia Torácica", "Cirurgia Vascular", "Clínica Médica", "Coloproctologia", "Dermatologia",
    "Endocrinologia e Metabologia", "Endoscopia", "Gastroenterologia", "Genética Médica", 
    "Geriatria", "Ginecologia e Obstetrícia", "Hematologia e Hemoterapia", "Homeopatia", 
    "Infectologia", "Mastologia", "Medicina de Emergência", "Medicina de Família e Comunidade", 
    "Medicina do Trabalho", "Medicina de Tráfego", "Medicina Esportiva", "Medicina Física e Reabilitação",
    "Medicina Intensiva", "Medicina Legal e Perícia Médica", "Medicina Nuclear", "Medicina Preventiva e Social",
    "Nefrologia", "Neurocirurgia", "Neurologia", "Nutrologia", "Oftalmologia", "Oncologia Clínica",
    "Ortopedia e Traumatologia", "Otorrinolaringologia", "Patologia", "Patologia Clínica/Medicina Laboratorial", 
    "Pediatria", "Pneumologia", "Psiquiatria", "Radiologia e Diagnóstico por Imagem", "Radioterapia", 
    "Reumatologia", "Urologia", "Medicina Aeroespacial", "Medicina do Sono", "Toxicologia Médica", "Oncogenética"
]


# --- Classes de Suporte ---
class User(UserMixin):
    def __init__(self, id, username, password_hash, role='user', email=None, razao_ic=1.0, fator_sensibilidade=1.0, data_nascimento=None, sexo=None):
        self.id = id
        self.username = username
        self.password_hash = password_hash
        self.role = role # Deve ser sempre minúsculo (paciente, medico, admin, cuidador)
        self.email = email
        self.razao_ic = razao_ic
        self.fator_sensibilidade = fator_sensibilidade
        self.data_nascimento = data_nascimento
        self.sexo = sexo
        
    @property
    def is_medico(self):
        # Checa o papel em minúsculas
        return self.role == 'medico'

    @property
    def is_admin(self):
        # Checa o papel em minúsculas
        return self.role == 'admin'

    @property
    def is_paciente(self):
        # Checa o papel em minúsculas
        return self.role == 'paciente' or self.role == 'user' # Mantendo 'user' por compatibilidade

    @property
    def is_cuidador(self):
        # Checa o papel em minúsculas
        return self.role == 'cuidador'
    
# --- Inicialização da AppCore com a instância GLOBAL do DatabaseManager
app_core = AppCore(db_manager)

# --- Carregador de Usuário para o Flask-Login ---
@login_manager.user_loader
def load_user(user_id):
    if db_manager:
        user_data = db_manager.carregar_usuario_por_id(int(user_id))
        if user_data:
            # Passa todos os dados do usuário para a classe User
            return User(
                id=user_data.get('id'),
                username=user_data.get('username'),
                password_hash=user_data.get('password_hash'),
                # Garantindo que a role lida do DB seja usada, mesmo que o padrão seja 'user'
                role=user_data.get('role', 'user').lower(), 
                email=user_data.get('email'),
                razao_ic=user_data.get('razao_ic', 1.0),
                fator_sensibilidade=user_data.get('fator_sensibilidade', 1.0),
                data_nascimento=user_data.get('data_nascimento'),
                sexo=user_data.get('sexo')
            )
    return None

# --- DECORADOR DE ACESSO EXCLUSIVO PARA MÉDICOS ---
def medico_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Você precisa estar logado para acessar esta página.', 'warning')
            return redirect(url_for('login'))
            
        if not current_user.is_medico:
            flash('Acesso negado. Apenas médicos podem acessar esta página.', 'danger')
            return redirect(url_for('dashboard')) 
        return f(*args, **kwargs)
    return decorated_function

# --- DECORADOR DE ACESSO EXCLUSIVO PARA ADMIN/GESTAO ---
def gestao_required(f):
    @wraps(f)
    @login_required # Garante que o usuário esteja logado
    def decorated_function(*args, **kwargs):
        # O perfil 'role' para Gestão/Admin deve ser 'admin' (em minúsculo)
        if not current_user.is_admin: # A propriedade .is_admin usa self.role == 'admin'
            flash('Acesso negado. Apenas administradores podem acessar esta página.', 'danger')
            return redirect(url_for('dashboard')) 
        return f(*args, **kwargs)
    return decorated_function

# --- Lista de Tipos de Diabetes para o <select> ---
TIPOS_DIABETES = [
    'Tipo 1',
    'Tipo 2',
    'LADA',
    'MODY',
    'Gestacional',
    'Outro/Não Especificado'
]

# --- Funções de Ajuda ---
def get_status_class(valor_glicemia):
    """Retorna uma classe CSS baseada no valor da glicemia."""
    try:
        valor = float(valor_glicemia)
    except (ValueError, TypeError):
        return 'bg-secondary'

    if valor < 70:
        return 'bg-danger' 
    elif 70 <= valor <= 130:
        return 'bg-success'
    elif 130 < valor <= 180:
        return 'bg-warning'
    else:
        return 'bg-danger' 


# --- ROTAS DA APLICAÇÃO (Bloco Corrigido) ---
@app.context_processor
def inject_now():
    return {'now': datetime.now}

@app.route('/')
def index(): 
    """Rota raiz. Se logado, vai para dashboard, senão, mostra a tela inicial."""
    if current_user.is_authenticated:
        # Garanta que o endpoint 'dashboard' existe
        return redirect(url_for('dashboard')) 
        
    # Se deslogado, renderiza a página de boas-vindas/login
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login(): # O endpoint é 'login'
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user_data = db_manager.carregar_usuario(username)
        
        if user_data and check_password_hash(user_data['password_hash'], password):
            user = User(
                id=user_data.get('id'),
                username=user_data.get('username'),
                password_hash=user_data.get('password_hash'),
                role=user_data.get('role', 'user').lower(), 
                email=user_data.get('email'),
                razao_ic=user_data.get('razao_ic', 1.0),
                fator_sensibilidade=user_data.get('fator_sensibilidade', 1.0),
                data_nascimento=user_data.get('data_nascimento'),
                sexo=user_data.get('sexo')
            )
            login_user(user)
            app_core.salvar_log_acao(f'Login', user.username)
            flash('Login realizado com sucesso!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Nome de usuário ou senha inválidos.', 'danger')
            app.logger.warning(f'Tentativa de login falha para o usuário {username}')
            
    # Se a requisição for GET ou o login falhar, renderiza o formulário de login
    return render_template('login.html')
@app.route('/logout')
@login_required
def logout():
    app_core.salvar_log_acao(f'Logout', current_user.username)
    logout_user()
    flash('Você foi desconectado.', 'info')
    return redirect(url_for('login'))


@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        # 1. Coleta de dados básicos
        username = request.form['username']
        password = request.form['password']
        password_confirm = request.form['password_confirm']
        role = request.form.get('role', 'paciente').lower() 

        # 2. Validação básica
        if len(username) < 3 or len(password) < 6:
            flash('Nome de usuário deve ter no mínimo 3 caracteres e senha no mínimo 6.', 'danger')
            return redirect(url_for('cadastro'))

        if password != password_confirm:
            flash('A senha e a confirmação de senha não coincidem.', 'danger')
            return redirect(url_for('cadastro'))

        hashed_password = generate_password_hash(password)
        
        # 3. Coleta de dados gerais e específicos
        novo_usuario = {
            'username': username,
            'password_hash': hashed_password,
            'role': role,
            'email': request.form.get('email'),
            'nome_completo': request.form.get('nome_completo'),
            'telefone': request.form.get('telefone'),
            'data_nascimento': request.form.get('data_nascimento'),
            'sexo': request.form.get('sexo'),
            'razao_ic': float(request.form.get('razao_ic', 1.0)), 
            'fator_sensibilidade': float(request.form.get('fator_sensibilidade', 1.0)),
            
            # Dados específicos de Médico (default None)
            'documento': None,
            'crm': None,
            'cns': None,
            'especialidade': None
        }
        
        # 4. TRATAMENTO DE CAMPOS DE MÉDICO
        if role == 'medico':
            novo_usuario['documento'] = request.form.get('documento')
            novo_usuario['crm'] = request.form.get('crm')
            novo_usuario['cns'] = request.form.get('cns')
            novo_usuario['especialidade'] = request.form.get('especialidade')

            # Validação específica de Médico
            if not all([novo_usuario['nome_completo'], novo_usuario['documento'], novo_usuario['crm'], novo_usuario['especialidade']]):
                flash('Todos os campos de registro profissional (Médico) são obrigatórios.', 'danger')
                return redirect(url_for('cadastro'))

        # 5. Salvar usuário no DB
        if db_manager.salvar_usuario(novo_usuario):
            flash('Cadastro realizado com sucesso! Faça login para começar.', 'success')
            app.logger.info(f'Novo usuário cadastrado: {username} ({role})')
            return redirect(url_for('login'))
        else:
            flash('Nome de usuário já existe. Tente outro.', 'danger')
            return redirect(url_for('cadastro'))
            
    # Rota de Cadastro (GET) - Passa a lista para o template
    return render_template('cadastro.html', 
                            especialidades=ESPECIALIDADES_MEDICAS)


@app.route('/dashboard')
@login_required
def dashboard():
    # 1. Verifica se é Médico/Admin e redireciona (CORRETO)
    if current_user.is_medico:
        return redirect(url_for('dashboard_medico'))
    
    if current_user.is_admin:
        # Se você quiser que o Admin caia no dashboard de Gestão:
        # return redirect(url_for('dashboard_gestao'))
        # Se você quiser que o Admin caia no gerenciamento:
        return redirect(url_for('gerenciar_usuarios')) # <--- OK, mantemos sua lógica
        
    # 2. Se for PACIENTE ou outro usuário, carrega o Dashboard Paciente (CORRETO)
    resumo_dados = carregar_dados_dashboard(current_user.id)
    return render_template('dashboard_paciente.html', resumo_dados=resumo_dados)

# Rota do Dashboard Médico (DEFINIÇÃO ÚNICA E CORRIGIDA)
@app.route('/dashboard_medico')
@login_required
@medico_required
def dashboard_medico():
    # Lógica de carregamento de pacientes e resumo de dados
    pacientes = db_manager.obter_pacientes_por_medico(current_user.id)
    
    resumo_dados = {
        'total_pacientes': len(pacientes) if pacientes else 0,
        # Você pode adicionar outros dados de resumo aqui se precisar
    }
    
    return render_template('dashboard_medico.html', pacientes=pacientes, resumo_dados=resumo_dados)

@app.route('/dashboard/gestao')
@login_required 
@gestao_required 
def dashboard_gestao(): 
    """Página de dashboard para usuários com perfil de Gestão/Administrador."""
    usuarios = db_manager.carregar_todos_os_usuarios()

    resumo = {
        'total_pacientes': 15,
        'consultas_pendentes': 5,
        'leituras_alto': 30,
        'leituras_baixo': 10
        }
    return render_template('dashboard_gestao.html', usuarios=usuarios, resumo=resumo) 

# --- ROTAS DA ÁREA ADMINISTRATIVA E DE GESTÃO ---

@app.route('/gerenciar_usuarios')
@login_required
def gerenciar_usuarios():
    # Verifica se o usuário tem permissão de administrador ou secretário
    if not (current_user.is_admin or current_user.role == 'secretario'):
        flash('Acesso não autorizado.', 'danger')
        return redirect(url_for('dashboard'))

    usuarios = db_manager.carregar_todos_os_usuarios()
    return render_template('gerenciar_usuarios.html', usuarios=usuarios)

# Rota para editar um usuário existente
@app.route('/editar_usuario/<username>', methods=['GET', 'POST'])
@login_required
def editar_usuario(username):
    if not current_user.is_admin:
        flash('Acesso não autorizado.', 'danger')
        return redirect(url_for('dashboard'))

    usuario = db_manager.carregar_usuario(username)
    if not usuario:
        flash('Usuário não encontrado.', 'danger')
        return redirect(url_for('gerenciar_usuarios'))

    medicos = db_manager.carregar_medicos()

    if request.method == 'POST':
        if usuario.get('role') == 'paciente':
            medico_id_selecionado = request.form.get('medico_vinculado')
            if medico_id_selecionado:
                db_manager.vincular_paciente_medico(usuario['id'], int(medico_id_selecionado))
        
        # 1. CAPTURA DE DADOS BÁSICOS (Incluindo nome_completo)
        nome_completo = request.form.get('nome_completo')
        role = request.form.get('role').lower()
        email = request.form.get('email')
        nova_senha = request.form.get('senha')
        confirmar_senha = request.form.get('confirmar_senha')
        data_nascimento = request.form.get('data_nascimento')
        sexo = request.form.get('sexo')

        # 2. CAPTURA DOS NOVOS CAMPOS DO LOG (documento e crm)
        documento = request.form.get('documento')
        crm = request.form.get('crm') # Apenas relevante para médicos

        if nova_senha:
            if nova_senha != confirmar_senha:
                flash('A senha e a confirmação de senha não coincidem.', 'danger')
                return render_template('editar_usuario.html', usuario=usuario, medicos=medicos)
            
            # Hash da nova senha
            usuario['password_hash'] = generate_password_hash(nova_senha)

        # 3. ATRIBUIÇÃO DOS NOVOS VALORES AO OBJETO/DICIONÁRIO 'usuario'
        usuario['nome_completo'] = nome_completo
        usuario['role'] = role
        usuario['email'] = email
        usuario['data_nascimento'] = data_nascimento
        usuario['sexo'] = sexo
        
        # Atribuição dos campos de log
        usuario['documento'] = documento # <-- Adicionado
        usuario['crm'] = crm             # <-- Adicionado
        
        # Funções de conversão para float
        # Usamos float(value or 0.0) para garantir que strings vazias sejam 0.0,
        # ou, melhor, convertemos para None se estiver vazio, para melhor tratamento no DB.
        
        def safe_float(value):
            return float(value) if value else None
            
        usuario['razao_ic'] = safe_float(request.form.get('razao_ic'))
        usuario['fator_sensibilidade'] = safe_float(request.form.get('fator_sensibilidade'))
        usuario['meta_glicemia'] = safe_float(request.form.get('meta_glicemia'))
        
        
        # 4. Tentar Atualizar o DB
        if db_manager.atualizar_usuario(usuario):
            flash('Usuário atualizado com sucesso!', 'success')
            return redirect(url_for('gerenciar_usuarios'))
        else:
            # Se o erro for de DB (como 'no such column'), ele será exibido aqui
            flash('Erro ao atualizar usuário.', 'danger')

    # Rota GET ou POST com erro de senha
    return render_template('editar_usuario.html', usuario=usuario, medicos=medicos)

@app.route('/excluir_usuario/<username>', methods=['POST'])
@login_required
def excluir_usuario(username):
    if not current_user.is_admin:
        flash('Acesso não autorizado.', 'danger')
        return redirect(url_for('dashboard'))

    if current_user.username == username:
        flash('Você não pode excluir a sua própria conta.', 'danger')
        return redirect(url_for('gerenciar_usuarios'))

    if db_manager.excluir_usuario(username):
        flash(f'Usuário {username} excluído com sucesso!', 'success')
    else:
        flash(f'Erro ao excluir o usuário {username}.', 'danger')

    return redirect(url_for('gerenciar_usuarios'))


@app.route('/vincular_cuidador_paciente', methods=['POST'])
@login_required
def vincular_cuidador_paciente():
    if not current_user.is_admin:
        flash('Acesso não autorizado.', 'danger')
        return redirect(url_for('dashboard'))

    paciente_username = request.form.get('paciente_username')
    cuidador_username = request.form.get('cuidador_username')
    
    if db_manager.vincular_cuidador_paciente(cuidador_username, paciente_username):
        flash('Cuidador vinculado ao paciente com sucesso!', 'success')
    else:
        flash('Erro ao vincular cuidador ao paciente.', 'danger')
        
    return redirect(url_for('gerenciar_usuarios'))

@app.route('/vincular_cuidador/<username>')
@login_required
def vincular_cuidador(username):
    if not current_user.is_admin:
        flash('Acesso não autorizado.', 'danger')
        return redirect(url_for('dashboard'))

    paciente = db_manager.carregar_usuario(username)
    if not paciente:
        flash('Paciente não encontrado.', 'danger')
        return redirect(url_for('gerenciar_usuarios'))

    cuidadores = db_manager.carregar_cuidadores()
    
    return render_template('vincular_cuidador.html', paciente=paciente, cuidadores=cuidadores)


# --- ROTAS DE REGISTRO DO PACIENTE ---

@app.route('/registros')
@login_required
def registros():
    # 1. Chame a função de consulta APENAS UMA VEZ. 
    # Mantenha o nome da sua função original (seja 'carregar_registros' ou 'get_registros_by_user').
    # Vou usar 'carregar_registros' como o principal.
    registros_list = db_manager.carregar_registros(current_user.id)
    
    import sys
    print(f"DEBUG LEITURA: User ID atual: {current_user.id}", file=sys.stderr)
    print(f"DEBUG LEITURA: Registros encontrados: {len(registros_list)}", file=sys.stderr)
    sys.stderr.flush()
    
    registros_formatados = []
    
    for registro in registros_list:
        tipo = registro.get('tipo')
        # Tenta pegar o tipo_refeicao primeiro, se não existir, usa o campo 'tipo'
        tipo_exibicao = registro.get('tipo_refeicao', tipo) 
        
        data_hora_str = registro.get('data_hora')
        if data_hora_str and isinstance(data_hora_str, str):
            try:
                # O registro é modificado aqui (se for um objeto mutável, como um dicionário)
                registro['data_hora'] = datetime.fromisoformat(data_hora_str)
            except ValueError:
                pass 

        registro['tipo_exibicao'] = tipo_exibicao
        registros_formatados.append(registro)

    # 🚨 NOTA: Removida a consulta duplicada: registros = db_manager.get_registros_by_user(current_user.id)
    # E os prints de debug associados que estavam confusos.

    return render_template(
        'registros.html', # Mudei para 'meus_registros.html' para ser consistente com a maioria das imagens
        registros=registros_formatados, # <- Enviando a lista formatada e populada
        current_user=current_user,
        get_status_class=get_status_class 
    )
from datetime import datetime
from flask import request, redirect, url_for, flash, render_template
from flask_login import current_user, login_required

# Substitua suas duas rotas por esta única função
@app.route('/registrar_glicemia', methods=['GET', 'POST'])
@login_required
def registrar_glicemia():
    
    # Lógica para processar o formulário (POST)
    if request.method == 'POST':
        
        URL_FAIL = 'registrar_glicemia' 
        URL_SUCCESS = 'registros' 

        # 1. Leitura e Validação de Formato
        valor = request.form.get('valor')
        data_hora_str = request.form.get('data_hora')
        tipo = request.form.get('tipo') 
        observacao = request.form.get('observacao', '')

        if not valor or not data_hora_str or not tipo:
            flash('Por favor, preencha todos os campos obrigatórios.', 'danger')
            return redirect(url_for(URL_FAIL))

        try:
            data_hora = datetime.fromisoformat(data_hora_str)
            # Garante que o valor da glicemia é um float
            valor_glicemia = float(valor.replace(',', '.')) 
        except (ValueError, TypeError):
            flash('Valores inválidos para glicemia ou data/hora.', 'danger')
            return redirect(url_for(URL_FAIL))
        print(f"DEBUG: Tentando salvar para o user_id: {current_user.id}") # 🚨 IMPRIMA ISTO

        # 2. Chamada da Função de Salvamento
        try:
            # Tenta salvar no DB
            sucesso = db_manager.salvar_glicemia(
                current_user.id, 
                valor_glicemia, 
                data_hora.isoformat(), 
                tipo, 
                observacao
            )
            
        except Exception as e:
            # Se ocorrer um erro Python (e.g., função não existe)
            print(f"ERRO CRÍTICO NO APP.PY AO CHAMAR SALVAR_GLICEMIA: {e}") 
            flash(f'Erro crítico no servidor: Verifique o log. (Código: {e.__class__.__name__})', 'danger')
            return redirect(url_for(URL_FAIL))
        
        # 3. Processamento do Resultado do DB (Garante o Retorno)
        # Se chegamos aqui, sucesso foi definido
        if sucesso:
            flash('Registro de glicemia salvo com sucesso!', 'success')
            return redirect(url_for(URL_SUCCESS))
        else:
            # Se salvar_glicemia retornou False (erro de SQLite no database_manager)
            print("ERRO INTERNO: salvar_glicemia retornou False. O erro real do SQLite foi impresso no terminal.")
            flash('Erro ao salvar no banco de dados. Verifique a integridade dos dados.', 'danger')
            return redirect(url_for(URL_FAIL))

    # Fora do if request.method == 'POST':
    return render_template('registrar_glicemia.html')

    
@app.route('/registrar_refeicao', methods=['GET', 'POST'])
@login_required
def registrar_refeicao():
    if request.method == 'POST':
        try:
            data_hora_str = request.form['data_hora']
            tipo_refeicao = request.form['tipo'] # Novo campo 'tipo' para Jejum, Almoço, etc.
            observacoes = request.form.get('observacoes')
            
            total_carbs = float(request.form['total_carbs'])
            total_kcal = float(request.form['total_kcal'])
            alimentos_selecionados_json = request.form['alimentos_selecionados']
            
            # Não é necessário carregar o JSON para salvá-lo, mas fazemos para validar
            json.loads(alimentos_selecionados_json) 
            
            # O tipo principal é Refeição, mas usamos tipo_refeicao para o detalhe
            registro_data = {
                'user_id': current_user.id,
                'data_hora': data_hora_str,
                'tipo': 'Refeição', 
                'valor': None,
                'observacoes': observacoes,
                'alimentos_json': alimentos_selecionados_json,
                'total_calorias': total_kcal,
                'total_carbs': total_carbs,
                'tipo_refeicao': tipo_refeicao
            }
            
            db_manager.salvar_registro(registro_data)
            
            flash('Refeição registrada com sucesso!', 'success')
            return redirect(url_for('dashboard'))

        except Exception as e:
            flash(f'Erro ao registrar a refeição: {e}', 'danger')
            return redirect(url_for('registrar_refeicao'))

    alimentos = db_manager.carregar_alimentos()
    now = datetime.now().strftime('%Y-%m-%dT%H:%M')
    
    # Usa a função do AppCore para obter a lista de tipos

    return render_template('registrar_refeicao.html', alimentos=alimentos, tipos_refeicao=app_core.obter_tipos_refeicao())
    
@app.route('/excluir_registo/<int:id>', methods=['POST'])
@login_required
def excluir_registo(id):
    registro_para_excluir = db_manager.encontrar_registo(id)
    
    if not registro_para_excluir or registro_para_excluir['user_id'] != current_user.id:
        flash('Registro não encontrado ou você não tem permissão para excluí-lo.', 'danger')
        return redirect(url_for('registros'))
    
    sucesso = db_manager.excluir_registro(id)
    
    if sucesso:
        flash('Registro excluído com sucesso!', 'success')
        app_core.salvar_log_acao(f'Registro {id} excluído', current_user.username)
    else:
        flash('Erro ao excluir o registro.', 'danger')
        
    return redirect(url_for('registros'))
    
# NO SEU ARQUIVO app.py

@app.route('/editar_registo/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_registo(id):
    # 1. Carregar o registro do banco de dados
    registro = db_manager.encontrar_registo(id)
    
    # 2. Verificação de segurança
    if not registro or registro.get('user_id') != current_user.id:
        flash('Registro não encontrado ou você não tem permissão para editá-lo.', 'danger')
        return redirect(url_for('registros'))

    if request.method == 'POST':
        # --- LÓGICA DE ATUALIZAÇÃO (POST) ---
        
        # Tipo principal do registro (Glicemia ou Refeição)
        tipo_principal = registro.get('tipo', '') 

        # =========================================================
        # EDICÃO DE GLICEMIA
        # =========================================================
        if tipo_principal == 'Glicemia':
            # Captura todos os campos relevantes do formulário 'editar_glicemia.html'
            valor_glicemia = request.form.get('valor_glicemia')
            data_hora_str = request.form.get('data_hora')
            observacoes = request.form.get('observacoes')
            tipo_medicao = request.form.get('tipo_medicao') # <-- CORREÇÃO: Capturando o dropdown

            try:
                data_hora = datetime.fromisoformat(data_hora_str)
                # Garante que o valor da glicemia seja um float (aceitando ',' ou '.')
                valor_glicemia = float(valor_glicemia.replace(',', '.')) 
            except (ValueError, TypeError):
                flash('Valores de glicemia ou data/hora inválidos.', 'danger')
                # Retorna ao formulário com o ID para permitir nova tentativa
                return redirect(url_for('editar_registo', id=id))

            # Atualiza o dicionário com os novos valores
            registro['valor'] = valor_glicemia
            registro['data_hora'] = data_hora.isoformat()
            registro['observacoes'] = observacoes
            registro['tipo_medicao'] = tipo_medicao # <-- CORREÇÃO: Salvando o tipo de medição
            
            # Tentar salvar no banco de dados
            if db_manager.atualizar_registro(registro):
                flash('Registro de glicemia atualizado com sucesso!', 'success')
                app_core.salvar_log_acao(f'Registro de glicemia {id} atualizado', current_user.username)
            else:
                flash('Erro ao atualizar registro de glicemia no banco de dados.', 'danger')
                
            return redirect(url_for('registros'))

        # =========================================================
        # EDICÃO DE REFEIÇÃO
        # =========================================================
        elif tipo_principal == 'Refeição':
            # Captura os dados básicos
            data_hora_str = request.form.get('data_hora')
            observacoes = request.form.get('observacoes')
            
            # 🚨 CORREÇÃO PRINCIPAL: Captura o tipo de refeição específico (dropdown)
            tipo_refeicao_especifica = request.form.get('tipo_refeicao') 
            
            # Como a edição de alimentos não está implementada no JS/HTML (só no backend), 
            # reusamos o JSON salvo. Se você enviar um novo JSON, use: request.form.get('alimentos_selecionados')
            alimentos_json_str = registro.get('alimentos_json', '[]') 
            
            if not data_hora_str or not tipo_refeicao_especifica:
                flash('Por favor, preencha a Data/Hora e o Tipo de Refeição.', 'danger')
                return redirect(url_for('editar_registo', id=id))
            
            try:
                data_hora = datetime.fromisoformat(data_hora_str)
                alimentos_list = json.loads(alimentos_json_str)
                
                # Recalcula os totais (para garantir consistência, embora o JSON seja reusado)
                # OBS: Ajuste as chaves 'carbs' e 'kcal' se o seu JSON usa nomes diferentes.
                total_carbs = sum(item.get('carbs', 0) for item in alimentos_list)
                total_calorias = sum(item.get('kcal', 0) for item in alimentos_list)
                
            except (ValueError, TypeError, json.JSONDecodeError) as e:
                flash(f'Dados de refeição inválidos: {e}', 'danger')
                return redirect(url_for('editar_registo', id=id))

            # Atualiza o dicionário 'registro' com os novos dados
            registro['data_hora'] = data_hora.isoformat()
            registro['observacoes'] = observacoes
            registro['alimentos_json'] = alimentos_json_str
            registro['total_carbs'] = total_carbs
            registro['total_calorias'] = total_calorias
            registro['tipo_refeicao'] = tipo_refeicao_especifica # Valor CORRIGIDO

            if db_manager.atualizar_registro(registro):
                flash('Registro de refeição atualizado com sucesso!', 'success')
                app_core.salvar_log_acao(f'Registro de refeição {id} atualizado', current_user.username)
            else:
                flash('Erro ao atualizar registro de refeição no banco de dados.', 'danger')
                
            return redirect(url_for('registros'))
        
        # Caso o POST não corresponda a nenhum tipo conhecido (improvável, mas seguro)
        else:
            flash('Tipo de registro desconhecido para edição.', 'danger')
            return redirect(url_for('registros'))

    # --- LÓGICA DE CARREGAMENTO DO FORMULÁRIO (GET) ---
    else: 
        # Pré-processamento comum de data_hora para ambos os templates
        if 'data_hora' in registro and isinstance(registro['data_hora'], str):
            try:
                # Converte string ISO de volta para objeto datetime (necessário se o Jinja não for formatar)
                registro['data_hora'] = datetime.fromisoformat(registro['data_hora'])
            except ValueError:
                pass # Ignora se a conversão falhar

        tipo_principal = registro.get('tipo', '')
        
        if tipo_principal == 'Glicemia':
            return render_template('editar_glicemia.html', registro=registro)
            
        elif tipo_principal == 'Refeição':
            # Lógica para carregar alimentos disponíveis para a edição de Refeição
            if 'alimentos_json' in registro and registro['alimentos_json']:
                registro['alimentos_list'] = json.loads(registro['alimentos_json'])
            else:
                registro['alimentos_list'] = []
            
            alimentos = db_manager.carregar_alimentos()
            return render_template(
                'editar_refeicao.html',
                registro=registro,
                alimentos_disponiveis=alimentos,
                tipos_refeicao=app_core.obter_tipos_refeicao(),
            )
            
        else:
            flash('Tipo de registro inválido.', 'danger')
            return redirect(url_for('registros'))
        
# --- ROTAS DE ALIMENTOS ---

@app.route('/alimentos')
@login_required
def alimentos():
    lista_alimentos = db_manager.carregar_alimentos()
    return render_template('alimentos.html', alimentos=lista_alimentos)

@app.route('/excluir_alimento/<int:id>', methods=['POST'])
@login_required
def excluir_alimento(id):
    if not (current_user.is_admin or current_user.role == 'secretario'):
        flash('Acesso não autorizado.', 'danger')
        return redirect(url_for('alimentos'))

    sucesso = db_manager.excluir_alimento(id)
    if sucesso:
        flash('Alimento excluído com sucesso!', 'success')
    else:
        flash('Erro ao excluir o alimento.', 'danger')
    return redirect(url_for('alimentos'))

# Rota Consolidada: use 'adicionar_alimento' como a rota principal
@app.route('/adicionar_alimento', methods=['GET', 'POST'])
@login_required
def adicionar_alimento():
    if not (current_user.role in ['secretario', 'admin']):
        flash('Acesso não autorizado.', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        try:
            nome = request.form['nome']
            medida_caseira = request.form['medida_caseira']
            peso_g = float(request.form['peso_g'].replace(',', '.'))
            kcal = float(request.form['kcal'].replace(',', '.'))
            # O campo carbs_100g do formulário, mas o DB pode querer o valor total para a porção
            carbs_100g = float(request.form['carbs_100g'].replace(',', '.')) 
            
            # Novo alimento usa o nome das colunas do DB
            novo_alimento = {
                'alimento': nome,
                'medida_caseira': medida_caseira,
                'peso': peso_g, # Peso da porção em g
                'kcal': kcal, # Kcal na porção
                'carbs': carbs_100g # Carbs na porção (assumindo que o frontend envia o valor final)
            }
            
            if db_manager.salvar_alimento(novo_alimento):
                flash('Alimento adicionado com sucesso!', 'success')
            else:
                flash('Erro ao adicionar o alimento.', 'danger')
        except (ValueError, TypeError):
            flash('Dados do alimento inválidos. Por favor, verifique os valores numéricos.', 'danger')
        
        return redirect(url_for('alimentos'))

    # Se a requisição for GET, carrega a lista de alimentos (se a rota for usada para listar/adicionar)
    alimentos = db_manager.carregar_alimentos()
    # A rota agora renderiza um template de adição
    return render_template('adicionar_alimento.html', alimentos=alimentos)

# Rota antiga 'registrar_alimento' redireciona para a nova
@app.route('/registrar_alimento')
@login_required
def registrar_alimento_redirect():
    return redirect(url_for('adicionar_alimento'))


# --- ROTAS DE UTILIDADE ---

@app.route('/refeicao')
@login_required
def refeicao():
    alimentos = db_manager.carregar_alimentos()
    return render_template('refeicao.html', alimentos=alimentos, tipos_refeicao=app_core.obter_tipos_refeicao())

@app.route('/relatorios')
@login_required
def relatorios():
    return render_template('relatorios.html')

@app.route('/calculadora_bolus')
@login_required
def calculadora_bolus():
    return render_template('calculadora_bolus.html')

@app.route('/calcular_fs')
@login_required
def calcular_fs():
    return render_template('calcular_fs.html')

@app.route('/guia_insulina')
@login_required
def guia_insulina():
    return render_template('guia_insulina.html')

# Certifique-se de que 'request', 'jsonify', 'login_required' e 'db_manager'
# (ou o objeto que gerencia seu SQLite) estejam importados corretamente.

@app.route('/buscar_alimentos', methods=['POST'])
@login_required 
def buscar_alimentos():
    termo = request.form.get('termo_pesquisa', '') 
    
    if len(termo) < 3:
        return jsonify({'resultados': []})
        
    try:
        # A função deve retornar uma lista de dicionários/Rows com as chaves: 
        # 'alimento', 'medida_caseira', 'peso', 'kcal', 'carbs'
        alimentos_encontrados = db_manager.buscar_alimentos_por_nome(termo)
    except Exception as e:
        print(f"Erro no Database Manager ao buscar alimentos: {e}")
        return jsonify({'resultados': []})
    
    resultados_finais = []
    for item_db in alimentos_encontrados:
        
        # 🟢 Mapeamento 1 e 2: DB para chaves esperadas pelo JavaScript
        nome_alimento = item_db.get('alimento', 'Nome Indefinido') # DB 'alimento' -> JSON 'nome'
        peso_porcao = float(item_db.get('peso', 100))               # DB 'peso' -> JSON 'peso_g'
        
        # Mapeamento 3: Obter valores base
        # ATENÇÃO: Estou assumindo que 'carbs' e 'kcal' são os valores por 100g.
        # Se os valores em 'carbs' e 'kcal' já forem referentes ao peso da porção (coluna 'peso'), 
        # a lógica de cálculo precisa ser simplificada (veja o bloco 'Atenção' abaixo).
        carbs_100g_base = float(item_db.get('carbs', 0)) 
        kcal_100g_base = float(item_db.get('kcal', 0))         
        medida_caseira = item_db.get('medida_caseira', 'Porção')
        
        # Lógica de Cálculo: Usando o peso da porção e o valor por 100g
        carbs_porcao = (carbs_100g_base * peso_porcao) / 100
        kcal_porcao = (kcal_100g_base * peso_porcao) / 100
        
        # Monta o dicionário de SAÍDA (o que o JavaScript espera)
        resultados_finais.append({
            'nome': nome_alimento,          # O JS usa esta chave
            'medida_caseira': medida_caseira,
            'peso_g': peso_porcao,          # O JS usa esta chave
            'carbs_porcao': carbs_porcao,   # O JS usa esta chave
            'kcal_porcao': kcal_porcao      # O JS usa esta chave
        })
        
    return jsonify({'resultados': resultados_finais})

# --- ROTAS DA ÁREA MÉDICA ---

# Rota para o Cadastro de Novo Paciente
@app.route('/medico/novo_paciente', methods=['GET', 'POST'])
@login_required 
@medico_required
def novo_paciente():
    # A variável medico_id pode ser útil para rastrear quem cadastrou, mas não é usada no cadastro básico
    # medico_id = current_user.id 

    if request.method == 'POST':
        # 1. Coletar dados do formulário (verifique os 'name' dos inputs no HTML)
        nome_completo = request.form.get('nome_completo')
        email = request.form.get('email')
        senha = request.form.get('senha')
        data_nascimento_str = request.form.get('data_nascimento') 
        tipo_diabetes = request.form.get('tipo_diabetes')

        # 2. Validação de dados (Mínima)
        if not nome_completo or not email or not senha or not data_nascimento_str or not tipo_diabetes:
            flash('Por favor, preencha todos os campos do formulário.', 'warning')
            return render_template('cadastrar_paciente_medico.html', tipos_diabetes=TIPOS_DIABETES)

        # 3. Processamento dos dados
        try:
            # Hash da senha para segurança
            hashed_password = generate_password_hash(senha)
            
            # Converte a data de nascimento para o objeto datetime.date
            data_nascimento = datetime.strptime(data_nascimento_str, '%Y-%m-%d').date()

            # a) Verifica se o usuário já existe
            if Usuario.query.filter_by(email=email).first():
                flash('Erro: Já existe um usuário cadastrado com este e-mail.', 'danger')
                return render_template('cadastrar_paciente_medico.html', tipos_diabetes=TIPOS_DIABETES)

            # b) Cria o registro de Usuário (role='paciente')
            novo_usuario = Usuario(
                username=email, # Usando email como username para login
                email=email, 
                password_hash=hashed_password, 
                role='paciente',
                nome_completo=nome_completo
            )
            db.session.add(novo_usuario)
            # Não faça o commit ainda, espere criar o paciente para commitar tudo junto

            # c) Cria o registro de Paciente, linkando-o ao ID do novo usuário
            # É necessário um commit para obter o ID do novo_usuario se você não usa uma sessão única.
            # Vamos fazer um commit parcial ou garantir que o relacionamento seja criado corretamente.
            # Se você usa relacionamentos de modelo (e.g., backref), o ID pode ser obtido após o commit.

            db.session.flush() # Força a atribuição do ID ao novo_usuario

            novo_paciente_obj = Paciente(
                user_id=novo_usuario.id,
                data_nascimento=data_nascimento,
                tipo_diabetes=tipo_diabetes
                # Outros campos do modelo Paciente devem ser adicionados aqui, se houver
            )
            db.session.add(novo_paciente_obj)
            
            # Commit final de todas as alterações
            db.session.commit()
            
            flash(f'Paciente {nome_completo} cadastrado com sucesso e pronto para login!', 'success')
            return redirect(url_for('lista_pacientes'))

        except Exception as e:
            # Em caso de qualquer erro (ex: falha no banco de dados, formato de data inválido, etc.)
            db.session.rollback() # Desfaz qualquer alteração no banco
            print(f"Erro ao cadastrar paciente: {e}") # Ajuda a depurar
            flash('Erro interno ao cadastrar paciente. Verifique o log do servidor.', 'danger')
            
            # Retorna o formulário com a mensagem de erro
            return render_template('cadastrar_paciente_medico.html', tipos_diabetes=TIPOS_DIABETES)

    # GET: Exibe o formulário
    return render_template('cadastrar_paciente_medico.html', tipos_diabetes=TIPOS_DIABETES)
    
# Rota para a Lista de Pacientes do Médico
@app.route('/medico/pacientes')
@login_required
@medico_required
def lista_pacientes():
    medico_id = current_user.id
    
    try:
        pacientes = db_manager.obter_pacientes_por_medico(medico_id) 
        
    except Exception as e:
        app.logger.error(f"Erro ao carregar pacientes para o médico {medico_id}: {e}")
        flash('Erro ao carregar lista de pacientes.', 'danger')
        pacientes = []
        
    return render_template('lista_pacientes.html', pacientes=pacientes)

# Rota de lista de pacientes (nome alternativo, redireciona para a lista principal)
@app.route('/pacientes')
@login_required
def pacientes():
    if not current_user.is_medico:
        flash('Acesso não autorizado. Esta página é exclusiva para médicos.', 'danger')
        return redirect(url_for('dashboard'))

    return redirect(url_for('lista_pacientes'))

# Rota do Relatório Medico
@app.route('/relatorio_medico')
@login_required
@medico_required
def relatorio_medico():
    return render_template('relatorio_medico.html')

@app.route('/paciente/<int:paciente_id>')
@login_required
def perfil_paciente(paciente_id):
    if not current_user.is_medico and not current_user.is_admin:
        flash('Acesso não autorizado.', 'danger')
        return redirect(url_for('dashboard'))
        
    if not db_manager.medico_tem_acesso_a_paciente(current_user.id, paciente_id) and not current_user.is_admin:
        flash('Acesso não autorizado a este paciente.', 'danger')
        return redirect(url_for('dashboard_medico'))
    
    paciente = db_manager.carregar_usuario_por_id(paciente_id)
    registros = db_manager.carregar_registros(paciente_id)
    ficha_medica = db_manager.carregar_ficha_medica(paciente_id)
    
    return render_template('perfil_paciente.html', paciente=paciente, registros_glicemia=registros, ficha_medica=ficha_medica)

# Rota para exibir/editar a ficha médica de um paciente
@app.route('/ficha_medica/<int:paciente_id>', methods=['GET', 'POST'])
@login_required
def ficha_medica(paciente_id):
    # Carrega o paciente pelo ID para garantir que ele existe
    paciente = db_manager.carregar_usuario_por_id(paciente_id)
    if not paciente or paciente.get('role') != 'paciente':
        flash('Paciente não encontrado.', 'danger')
        return redirect(url_for('dashboard'))

    # Verifica se o médico tem permissão para acessar a ficha
    if not current_user.is_admin and not db_manager.medico_tem_acesso_a_paciente(current_user.id, paciente_id):
        flash('Acesso negado. Você não tem permissão para visualizar a ficha deste paciente.', 'danger')
        return redirect(url_for('dashboard'))
        
    ficha_medica_data = db_manager.carregar_ficha_medica(paciente_id)
    if not ficha_medica_data:
        ficha_medica_data = {'paciente_id': paciente_id}

    if request.method == 'POST':
        # Processa o formulário de atualização da ficha
        ficha_medica_data['tipo_diabetes'] = request.form.get('tipo_diabetes')
        ficha_medica_data['insulina_basal'] = request.form.get('insulina_basal')
        ficha_medica_data['insulina_bolus'] = request.form.get('insulina_bolus')
        ficha_medica_data['observacoes'] = request.form.get('observacoes')
        ficha_medica_data['data_diagnostico'] = request.form.get('data_diagnostico')

        db_manager.salvar_ficha_medica(ficha_medica_data)
        flash('Ficha médica atualizada com sucesso!', 'success')
        # Redireciona para o perfil do paciente
        return redirect(url_for('perfil_paciente', paciente_id=paciente_id))

    return render_template('ficha_medica.html', paciente=paciente, ficha=ficha_medica_data, tipos_diabetes=TIPOS_DIABETES)

@app.route('/salvar_ficha_medica', methods=['POST'])
@login_required
def salvar_ficha_medica():
    # Apenas médicos e administradores podem salvar fichas médicas
    if not (current_user.is_medico or current_user.is_admin):
        flash('Acesso não autorizado.', 'danger')
        return redirect(url_for('dashboard'))

    try:
        paciente_id = int(request.form['paciente_id'])
        
        ficha_data = {
            'paciente_id': paciente_id,
            'condicao_atual': request.form['condicao_atual'],
            'alergias': request.form['alergias'],
            'historico_familiar': request.form['historico_familiar'],
            'medicamentos_uso': request.form['medicamentos_uso']
        }
        
        if db_manager.salvar_ficha_medica(ficha_data):
            flash('Ficha médica salva com sucesso!', 'success')
        else:
            flash('Erro ao salvar a ficha médica.', 'danger')

        return redirect(url_for('perfil_paciente', paciente_id=paciente_id))

    except Exception as e:
        flash(f'Ocorreu um erro: {e}', 'danger')
        return redirect(url_for('dashboard'))
    
@app.route('/medico/ficha_acompanhamento/<int:paciente_id>', methods=['GET'])
@login_required
def ficha_acompanhamento(paciente_id):
    if not current_user.is_medico and not current_user.is_admin:
        flash('Acesso não autorizado.', 'danger')
        return redirect(url_for('dashboard'))

    paciente = db_manager.carregar_usuario_por_id(paciente_id) 
    if not paciente:
        flash('Paciente não encontrado.', 'danger')
        return redirect(url_for('dashboard_medico')) 
        
    exames_anteriores = db_manager.buscar_exames_paciente(paciente_id)
    
    return render_template(
        'ficha_acompanhamento.html', 
        paciente=paciente, 
        exames_anteriores=exames_anteriores
    )

@app.route('/medico/salvar_ficha_exame/<int:paciente_id>', methods=['POST'])
@login_required
def salvar_ficha_exame(paciente_id):
    if not current_user.is_medico and not current_user.is_admin:
        flash('Acesso não autorizado.', 'danger')
        return redirect(url_for('dashboard'))

    novo_exame = {
        'paciente_id': paciente_id,
        'data_exame': request.form.get('data_exame'), 
        'hb_a1c': float(request.form.get('hb_a1c', 0.0)),
        'glicose_jejum': int(request.form.get('glicose_jejum', 0)),
        'ldl': int(request.form.get('ldl', 0)),
        'triglicerides': int(request.form.get('triglicerides', 0)),
        'obs_medico': request.form.get('obs_medico')
    }
    
    if db_manager.salvar_exame_laboratorial(novo_exame):
        flash('Ficha de exame salva com sucesso!', 'success')
    else:
        flash('Erro ao salvar ficha de exame.', 'danger')

    return redirect(url_for('ficha_acompanhamento', paciente_id=paciente_id))


# --- ROTAS DE AGENDAMENTO ---

@app.route('/agendamentos')
@login_required
def agendamentos_redirect():
    return redirect(url_for('gerenciar_agendamentos'))

@app.route('/minhas_consultas')
@login_required
def minhas_consultas():
    if not current_user.is_paciente:
        flash('Acesso não autorizado. Esta página é para pacientes.', 'danger')
        return redirect(url_for('dashboard'))

    agendamentos = db_manager.buscar_agendamentos_paciente(current_user.id)
    return render_template('minhas_consultas.html', agendamentos=agendamentos)

@app.route('/atualizar_status_paciente/<int:id>', methods=['POST'])
@login_required
def atualizar_status_paciente(id):
    if not current_user.is_paciente:
        flash('Acesso não autorizado.', 'danger')
        return redirect(url_for('dashboard'))

    novo_status = request.form.get('novo_status')
    if db_manager.atualizar_status_agendamento(id, novo_status):
        flash('Status da consulta atualizado com sucesso.', 'success')
    else:
        flash('Erro ao atualizar o status da consulta.', 'danger')
    return redirect(url_for('minhas_consultas'))

@app.route('/gerenciar_agendamentos')
@login_required
def gerenciar_agendamentos():
    if not current_user.is_medico and not current_user.is_admin:
        flash('Acesso não autorizado.', 'danger')
        return redirect(url_for('dashboard'))

    agendamentos = db_manager.buscar_todos_agendamentos()
    return render_template('gerenciar_agendamentos.html', agendamentos=agendamentos)

@app.route('/agendar_para_paciente', methods=['GET', 'POST'])
@login_required
def agendar_para_paciente():
    if not current_user.is_medico and not current_user.is_admin:
        flash('Acesso não autorizado.', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        try:
            paciente_username = request.form['paciente_username']
            medico_username = request.form['medico_username']
            data_hora = request.form['data_hora']
            observacoes = request.form.get('observacoes', '')

            paciente_id = db_manager.get_user_id_by_username(paciente_username)
            medico_id = db_manager.get_user_id_by_username(medico_username)

            if not paciente_id or not medico_id:
                flash('Paciente ou médico não encontrado.', 'danger')
                return redirect(url_for('agendar_para_paciente'))

            if db_manager.salvar_agendamento(paciente_id, medico_id, data_hora, observacoes):
                flash('Agendamento criado com sucesso!', 'success')
                return redirect(url_for('gerenciar_agendamentos'))
            else:
                flash('Erro ao salvar agendamento.', 'danger')
                return redirect(url_for('agendar_para_paciente'))
        
        except Exception as e:
            flash(f'Ocorreu um erro: {e}', 'danger')
            return redirect(url_for('agendar_para_paciente'))

    pacientes = db_manager.carregar_todos_os_usuarios('paciente')
    medicos = db_manager.carregar_todos_os_usuarios('medico')
    
    return render_template('agendar_para_paciente.html', pacientes=pacientes, medicos=medicos)

@app.route('/agendar_consulta', methods=['GET', 'POST'])
@login_required
def agendar_consulta():
    if request.method == 'POST':
        medico_id = request.form.get('medico_id')
        data_hora = request.form.get('data_agendamento')
        observacoes = request.form.get('observacoes')
        paciente_id = current_user.id 

        if db_manager.salvar_agendamento(paciente_id, medico_id, data_hora, observacoes):
            flash('Consulta agendada com sucesso!', 'success')
            return redirect(url_for('minhas_consultas'))
        else:
            flash('Erro ao agendar consulta. Tente novamente.', 'danger')
            return redirect(url_for('agendar_consulta'))

    medicos = db_manager.carregar_todos_os_usuarios(perfil='medico')
    return render_template('agendar_consulta.html', medicos=medicos)

if __name__ == '__main__':
    app.run(debug=True)