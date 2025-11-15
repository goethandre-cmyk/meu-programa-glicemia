#========||||||APP.PY ANTIGO||||||======== """""
from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, SubmitField
from wtforms.validators import DataRequired, NumberRange
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask import Flask, render_template, redirect, url_for, request, flash, jsonify
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
from service_manager import formatar_registros_para_exibicao 
from db_instance import db_manager # <--- Use esta instância!
from models import User 
from service_manager import BolusService
from service_manager import get_hba1c_class, get_jejum_class
# A LINHA 'from db_manager import DatabaseManager' foi removida se você usa 'db_instance'

bolus_service = BolusService(db_manager) 
INSULINAS_DISPONIVEIS = {
    'Asparte (Fiasp/NovoLog)': 'Rápida',
    'Lispro (Humalog)': 'Rápida',
    'Degludeca (Tresiba)': 'Basal Ultralonga',
    'Detemir (Levemir)': 'Basal Longa',
    'Glargina (Lantus)': 'Basal Longa',
    'Humana Regular': 'Regular',
    'Humana NPH': 'Basal Intermediária',
    'Xultophy (Associação Degludeca/Liraglutida)': 'Basal Ultralonga' # Assumindo que a dose basal é o foco
}

app = Flask(__name__)


def get_status_class(status):
    """Mapeia o status do agendamento para a classe de cor Bootstrap."""
    status = status.lower() # Garante que a comparação seja insensível a maiúsculas/minúsculas
    if status == 'agendado':
        return 'info'
    elif status == 'confirmado':
        return 'success'
    elif status == 'cancelado':
        return 'danger'
    elif status == 'realizado':
        return 'secondary'
    return 'light' # Cor padrão/fallback

app.jinja_env.globals.update(get_status_class=get_status_class)

# CONFIGURAÇÃO CRÍTICA PARA DESATIVAR O CACHE DE TEMPLATE EM DESENVOLVIMENTO
# Isso garante que o Jinja2 não armazene o HTML antigo.
app.jinja_env.cache = {} 
app.jinja_env.globals.update(get_hba1c_class=get_hba1c_class)
app.jinja_env.globals.update(get_jejum_class=get_jejum_class)

# Após a inicialização do Flask e antes das rotas
app.register_blueprint(relatorios_bp)
# OU, se quiser um prefixo de URL:
# app.register_blueprint(relatorios_bp, url_prefix='/relatorios')
app.secret_key = 'sua_chave_secreta_aqui' 
app.logger.setLevel(logging.INFO)

# --- Inicialização das Classes ---
db_path = os.path.join('data', 'glicemia.db')
class AlimentoForm(FlaskForm):
    # Os nomes dos campos devem corresponder aos nomes dos inputs no HTML original
    nome = StringField('Alimento', validators=[DataRequired()])
    medida_caseira = StringField('Medida Caseira', validators=[DataRequired()])
    # Campos numéricos
    peso_g = FloatField('Peso (g) por porção', validators=[DataRequired(), NumberRange(min=0.1)])
    kcal = FloatField('Kcal por porção', validators=[DataRequired(), NumberRange(min=0)])
    carbs_100g = FloatField('Carboidratos (g) por porção', validators=[DataRequired(), NumberRange(min=0)])
    
    submit = SubmitField('Salvar Alterações')

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

def get_float_or_none(key):
    # 'request' precisa ser importado e disponível globalmente se for usado aqui
    value = request.form.get(key) 
    if not value:
        return None
    try:
        # Substitui vírgula por ponto e converte para float
        return float(value.replace(',', '.'))
    except ValueError:
        return None

def get_int_or_none(key):
    # 'request' precisa ser importado e disponível globalmente se for usado aqui
    value = request.form.get(key)
    if not value:
        return None
    try:
        # Converte diretamente para int (após garantir que não é vazio)
        return int(value)
    except ValueError:
        return None

# --- DECORADOR DE ACESSO EXCLUSIVO PARA ADMIN ---
def admin_only(f):
    @wraps(f)
    @login_required # Garante que o usuário esteja logado
    def decorated_function(*args, **kwargs):
        
        # Apenas permite se a propriedade 'is_admin' for True
        if not current_user.is_admin: 
            flash('Acesso negado. Apenas administradores do sistema podem acessar esta função.', 'danger')
            return redirect(url_for('dashboard')) 
            
        return f(*args, **kwargs)
    return decorated_function

def paciente_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Assumindo que current_user tem uma propriedade 'is_paciente' 
        # OU o papel (role) é 'paciente'
        if not current_user.is_authenticated or current_user.role != 'paciente':
            flash('Acesso não autorizado. Esta página é exclusiva para pacientes.', 'danger')
            return redirect(url_for('dashboard')) # Redireciona para um dashboard neutro
        return f(*args, **kwargs)
    return decorated_function
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

    def obter_tipos_medicao(self):
            """
            Retorna uma lista de tipos de medição de glicemia (momentos de coleta)
            para uso nos formulários.
            """
            return [
                'Jejum',
                'Pre_Refeicao',
                'Pos_Refeicao',
                'Antes_Dormir',
                'Madrugada',
                'Outros'
            ]   
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

# --- Inicialização da AppCore com a instância GLOBAL do DatabaseManager
app_core = AppCore(db_manager)

# --- Carregador de Usuário para o Flask-Login ---
# app.py (Função load_user com argumentos completos)

@login_manager.user_loader
def load_user(user_id):
    if db_manager:
        user_data = db_manager.carregar_usuario_por_id(int(user_id))
        if user_data:
            return User(
                id=user_data.get('id'),
                username=user_data.get('username'),
                password_hash=user_data.get('password_hash'),
                role=user_data.get('role', 'user').lower(), 
                email=user_data.get('email'),
                razao_ic=user_data.get('razao_ic', 1.0),
                fator_sensibilidade=user_data.get('fator_sensibilidade', 1.0),
                data_nascimento=user_data.get('data_nascimento'),
                sexo=user_data.get('sexo'),
                
                # ⭐ NOVOS CAMPOS QUE VOCÊ ADICIONOU ANTERIORMENTE DEVEM ESTAR AQUI:
                nome_completo=user_data.get('nome_completo'),
                telefone=user_data.get('telefone'),
                documento=user_data.get('documento'),
                crm=user_data.get('crm'),
                cns=user_data.get('cns'),
                especialidade=user_data.get('especialidade')
                # ⭐ FIM DOS NOVOS CAMPOS
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
    @login_required 
    def decorated_function(*args, **kwargs):
        
        # Lista de todos os papéis que têm permissão de Gestão/Gerenciamento.
        PAPEIS_DE_GESTAO = ['admin', 'secretario', 'medico']
        
        if current_user.role not in PAPEIS_DE_GESTAO:
            # Note a mensagem mais clara sobre quem pode acessar
            flash('Acesso negado. Apenas profissionais de gestão, médicos e administradores podem acessar esta página.', 'danger')
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
def obter_tipos_medicao(self):
        """
        Retorna uma lista de tipos de medição de glicemia para o dropdown.
        """
        return [
            'Jejum',
            'Pre_Refeicao',
            'Pos_Refeicao',
            'Antes_Dormir',
            'Madrugada',
            'Outros'
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

@app.template_filter()
def format_datetime(value, format_string='%d/%m/%Y às %H:%M'):
    """Filtro Jinja para formatar strings ou objetos datetime."""
    if isinstance(value, datetime):
        # Já é um objeto datetime, apenas formata
        return value.strftime(format_string)
    
    if isinstance(value, str):
        # Tenta converter a string para datetime (usando o formato do DB)
        DB_FORMAT = '%Y-%m-%d %H:%M:%S'
        try:
            dt_obj = datetime.strptime(value, DB_FORMAT)
            return dt_obj.strftime(format_string)
        except (ValueError, TypeError):
            # Retorna a string bruta se a conversão falhar
            return value 
            
    return value

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

@app.route('/cuidador')
@login_required
def dashboard_cuidador(): # <--- O endpoint DEVE ser 'dashboard_cuidador'
    
    cuidador_id = current_user.id
    pacientes_monitorados = db_manager.obter_pacientes_por_cuidador(cuidador_id)
    
    return render_template('dashboard_cuidador.html', pacientes=pacientes_monitorados)

@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    # 1. Redireciona se o usuário já estiver logado
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        # 2. Coleta de dados do formulário
        username = request.form['username']
        password = request.form['password']
        password_confirm = request.form['password_confirm']
        role = request.form.get('role', 'paciente').lower() 

        # 3. Validações de Senha e Tamanho
        if len(username) < 3 or len(password) < 6:
            flash('Nome de usuário deve ter no mínimo 3 caracteres e senha no mínimo 6.', 'danger')
            return redirect(url_for('cadastro'))

        if password != password_confirm:
            flash('A senha e a confirmação de senha não coincidem.', 'danger')
            return redirect(url_for('cadastro'))

        hashed_password = generate_password_hash(password)
        
        # 4. Definição do Novo Usuário (Dados Pessoais + Autenticação)
        novo_usuario = {
            'username': username,
            'password_hash': hashed_password,
            'role': role,
            'email': request.form.get('email'),
            'nome_completo': request.form.get('nome_completo'),
            'telefone': request.form.get('telefone'),
            'data_nascimento': request.form.get('data_nascimento'),
            'sexo': request.form.get('sexo'),
            
            # Campos clínicos definidos como None (serão preenchidos em /configurar_parametros)
            'razao_ic': None, 
            'fator_sensibilidade': None,
            
            # Campos de Médico/Profissional (default None)
            'documento': None,
            'crm': None,
            'cns': None,
            'especialidade': None
        }
        
        # 5. Tratamento de campos de Médico/Profissional (se o papel for 'medico')
        if role == 'medico':
            novo_usuario['documento'] = request.form.get('documento')
            novo_usuario['crm'] = request.form.get('crm')
            novo_usuario['cns'] = request.form.get('cns')
            novo_usuario['especialidade'] = request.form.get('especialidade')

            # Validação específica de Médico
            if not all([novo_usuario['nome_completo'], novo_usuario['documento'], novo_usuario['crm'], novo_usuario['especialidade']]):
                flash('Todos os campos de registro profissional (Médico) são obrigatórios.', 'danger')
                return redirect(url_for('cadastro'))

        # 6. Salvar usuário no DB
        try:
            # Assumindo que db_manager.salvar_usuario(novo_usuario) retorna True em caso de sucesso
            if db_manager.salvar_usuario(novo_usuario): 
                
                # 6.1. Carregar o usuário recém-criado do banco (necessário para login_user)
                user = db_manager.carregar_usuario_por_username(username) 
                
                if user:
                    # 6.2. Fazer o login automático
                    login_user(user) 
                    app.logger.info(f'Novo usuário cadastrado e logado: {username} ({role})')
                    flash('Cadastro realizado com sucesso! Bem-vindo(a).', 'success')

                    # 6.3. Redirecionamento Condicional Imediato
                    if role == 'paciente':
                        # Redireciona para a configuração de parâmetros
                        flash('Por favor, defina seus Fatores Clínicos (RIC, FSI, Glicemia Alvo) para usar a calculadora de Bolus.', 'warning')
                        return redirect(url_for('configurar_parametros')) 
                    elif role == 'medico':
                        return redirect(url_for('dashboard_medico'))
                    else:
                        return redirect(url_for('dashboard')) 
                else:
                    # Se o login automático falhar (usuário não encontrado após salvar)
                    flash('Cadastro realizado. Faça login para começar.', 'success')
                    return redirect(url_for('login'))
            else:
                # Caso db_manager.salvar_usuario retorne False (ex: nome de usuário duplicado)
                flash('Nome de usuário já existe. Tente outro.', 'danger')
                return redirect(url_for('cadastro'))
                
        except Exception as e:
            app.logger.error(f'Erro fatal ao salvar usuário no DB: {e}')
            flash(f'Erro interno ao cadastrar. Tente novamente. Detalhes: {e}', 'danger')
            return redirect(url_for('cadastro'))

    # 7. Rota de Cadastro (GET) - Exibir formulário
    # Passa a lista de especialidades para o template (se for usada para médicos)
    return render_template('cadastro.html', 
                             especialidades=ESPECIALIDADES_MEDICAS)
# rota dashboard

@app.route('/dashboard')
@login_required
def dashboard():
    
    # 1. GESTORES (Admin/Secretario)
    if current_user.role in ['admin', 'secretario']:
        # Esta rota deve renderizar o novo dashboard_gestao.html
        return redirect(url_for('dashboard_gestao'))
    
    # 2. MÉDICO
    elif current_user.role == 'medico':
        # Esta rota deve levar à visão do médico (gerenciamento de pacientes)
        return redirect(url_for('dashboard_medico'))
        
    # 3. CUIDADOR/CAREGIVER
    elif current_user.role == 'cuidador':
        # Esta rota deve levar à visão de acompanhamento dos pacientes vinculados
        return redirect(url_for('dashboard_cuidador'))
    
    # 4. PACIENTE
    elif current_user.role == 'paciente': 
        paciente_id = current_user.id
        
        # 4a. Busca dados de resumo do paciente (glicemia média, etc.)
        # Depende da implementação de db_manager.obter_resumo_paciente
        resumo_dados = db_manager.obter_resumo_paciente(paciente_id) 
        
        # 4b. NOVO: Calcula a dose média de insulina aplicada nos últimos 14 dias
        # Requer a função db_manager.calcular_dose_media_aplicada(id, dias)
        dose_media = db_manager.calcular_dose_media_aplicada(paciente_id, dias=14)
        
        # 4c. Passa os dados para o template específico do paciente
        return render_template('dashboard_paciente.html', # Renomeado para clareza
                               resumo_dados=resumo_dados,
                               dose_media_aplicada=dose_media) 
        
    # 5. Caso de segurança: se o papel não for reconhecido, desloga
    flash("Seu perfil não está configurado. Por favor, entre em contato com o suporte.", 'danger')
    return redirect(url_for('logout'))

# ||||||| -----DASHBOARD DE GESTÃO (para Médicos, Admins, etc.)--------||||||

# No seu app.py ou rotas.py

@app.route('/dashboard_gestao')
@login_required
def dashboard_gestao():
    # Garantimos que apenas Gestores/Admin tenham acesso direto a esta rota
    if current_user.role not in ['admin', 'secretario']:
        flash('Acesso restrito ao Painel de Gestão.', 'danger')
        return redirect(url_for('dashboard'))
        
    # Estas funções precisam existir no seu db_manager.py
    # Odb_manager deve contar usuários e dados, independente do ID do usuário logado.
    resumo = {
        'total_pacientes': db_manager.contar_usuarios(role='paciente'),
        # CRUCIAL: Contar quem não tem os 2 campos essenciais (glicemia_alvo e ric_manha)
        'pacientes_sem_parametros': db_manager.contar_pacientes_sem_parametros(),
        # Novo KPI focado na saúde do paciente (ex: Glicemia fora da zona alvo nas últimas 48h)
        'pacientes_em_alerta': db_manager.contar_pacientes_em_alerta(), 
        'registros_hoje': db_manager.contar_registros_24h()
    }

    return render_template('dashboard_gestao.html', resumo=resumo)

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
    # 1. Busca os dados brutos (usando a função correta: carregar_registros)
    registros_brutos = db_manager.carregar_registros(current_user.id) 
    
    # 2. CHAMADA AO SERVIÇO: Formata os dados
    registros_prontos = formatar_registros_para_exibicao(registros_brutos)
    
    # 3. Envia os dados LIMPOS e PRONTOS para o template
    # ✅ CORRIGIDO: get_status_class agora é um argumento da função render_template.
    return render_template(
        'registros.html', 
        registros=registros_prontos,
        get_status_class=get_status_class 
    )


@app.route('/registrar_glicemia', methods=['GET', 'POST'])
@login_required
def registrar_glicemia():
    
    URL_FAIL = 'registrar_glicemia' 
    URL_SUCCESS = 'registros' 

    # Lógica para processar o formulário (POST)
    if request.method == 'POST':
        
        # 1. Leitura e Validação de Formato
        valor = request.form.get('valor')
        data_hora_str = request.form.get('data_hora')
        tipo = request.form.get('tipo') 
        observacao = request.form.get('observacao', '')
        dose_aplicada_str = request.form.get('dose_aplicada')

        if not valor or not data_hora_str or not tipo:
            flash('Por favor, preencha todos os campos obrigatórios.', 'danger')
            return redirect(url_for(URL_FAIL))

        try:
            data_hora = datetime.fromisoformat(data_hora_str)
            valor_glicemia = float(valor.replace(',', '.')) 
            dose_aplicada = float(dose_aplicada_str) if dose_aplicada_str else None
        except (ValueError, TypeError):
            flash('Valores inválidos para glicemia, dose aplicada ou data/hora.', 'danger')
            return redirect(url_for(URL_FAIL))
        
        # 🚨 NOVO CÓDIGO: RECÁLCULO DO BÓLUS SUGERIDO NO POST 🚨
        # Assumindo que você tem acesso ao 'calcular_bolus_correcao'
        # Você deve definir esta função ou importá-la corretamente.
        try:
            bolus_sugerido = calcular_bolus_correcao(current_user.id, valor_glicemia)
        except Exception:
             # Em caso de erro (ex: parâmetros não definidos), trata como 0
            bolus_sugerido = 0 
        
        # 🚨 NOVO CÓDIGO: INSERIR O BÓLUS SUGERIDO NA OBSERVAÇÃO 🚨
        if bolus_sugerido is not None and bolus_sugerido > 0:
            info_bolus = f"Bólus Sugerido: {bolus_sugerido:.1f}U."
            if observacao:
                # Adiciona no início da observação do usuário
                observacao = f"{info_bolus} {observacao}"
            else:
                # Se o campo estava vazio, usa o sugerido
                observacao = info_bolus
        # -------------------------------------------------------------

        print(f"DEBUG: Tentando salvar para o user_id: {current_user.id}")

        # 2. Chamada da Função de Salvamento (A variável 'observacao' agora tem a dose sugerida)
        try:
            sucesso = db_manager.salvar_glicemia(
                current_user.id, 
                valor_glicemia, 
                data_hora.isoformat(), 
                tipo, 
                observacao, # AGORA ESTA VARIÁVEL TEM A DOSE SUGERIDA
                dose_aplicada=dose_aplicada
            )
            
        except Exception as e:
            print(f"ERRO CRÍTICO NO APP.PY AO CHAMAR SALVAR_GLICEMIA: {e}") 
            flash(f'Erro crítico no servidor: Verifique o log. (Código: {e.__class__.__name__})', 'danger')
            return redirect(url_for(URL_FAIL))
        
        # 3. Processamento do Resultado do DB
        if sucesso:
            flash('Registro de glicemia salvo com sucesso!', 'success')
            return redirect(url_for(URL_SUCCESS))
        else:
            print("ERRO INTERNO: salvar_glicemia retornou False. O erro real do SQLite foi impresso no terminal.")
            flash('Erro ao salvar no banco de dados. Verifique a integridade dos dados.', 'danger')
            return redirect(url_for(URL_FAIL))

    # Lógica GET (Renderização do Formulário)
    # -------------------------------------------------------------------------------------
    # Aqui, a variável 'bolus_calculado' é gerada para o atributo 'value' do input 'dose_aplicada'.
    # Isso está correto, e não precisa ser alterado.
    # Exemplo:
    # bolus_calculado = calcular_bolus_correcao(current_user.id, valor_glicemia_atual) 
    # return render_template('registrar_glicemia.html', bolus_calculado=bolus_calculado)
    # -------------------------------------------------------------------------------------
    
    # Se você não tem o cálculo aqui no bloco GET, o bolus_calculado no template será vazio, 
    # mas o POST funcionará. Para ser completo:

    bolus_calculado = None # Inicializa
    
    # 💡 Se você quiser que o bolus_calculado continue aparecendo no campo de dose ao carregar a página:
    try:
        # Você precisaria de um valor inicial de glicemia ou um padrão
        glicemia_inicial = 150 # Exemplo de valor inicial, ou você obtém de um sensor
        bolus_calculado = calcular_bolus_correcao(current_user.id, glicemia_inicial)
    except Exception:
        bolus_calculado = None
    
    return render_template('registrar_glicemia.html', bolus_calculado=bolus_calculado)
    
@app.route('/registrar_refeicao', methods=['GET', 'POST'])
@login_required
def registrar_refeicao():
    
    if request.method == 'POST':
        try:
            user_id = current_user.id
            
            # 1. COLETA DE DADOS CRUCIAIS
            data_hora_str = request.form['data_hora']
            tipo_refeicao = request.form['tipo'] 
            glicemia_input = request.form.get('glicemia_atual') 
            
            # 🚨 CORREÇÃO: Usar a dose_aplicada enviada pelo formulário (Se o usuário ajustou/confirmou)
            dose_aplicada_str = request.form.get('dose_aplicada')
            try:
                dose_aplicada = float(dose_aplicada_str) if dose_aplicada_str else None
            except ValueError:
                dose_aplicada = None
                
            total_carbs = float(request.form['total_carbs'])
            total_kcal = float(request.form['total_kcal'])
            alimentos_selecionados_json = request.form['alimentos_selecionados']
            observacoes = request.form.get('observacoes')
            
            # 2. DETERMINAR GC PARA O CÁLCULO
            if glicemia_input and float(glicemia_input) > 0:
                gc_atual = float(glicemia_input)
                gc_fornecida = True
            else:
                gc_atual = db_manager.buscar_ultima_glicemia(user_id) or 0.0 
                gc_fornecida = False
            
            # 3. CHAMAR O SERVIÇO DE CÁLCULO DE BÓLUS (ainda necessário para a sugestão)
            resultado_bolus, erro = bolus_service.calcular_bolus_total(
                gc_atual=gc_atual, 
                carboidratos=total_carbs, 
                paciente_id=user_id
            )

            if erro:
                flash(f'Erro no cálculo do Bólus: {erro}', 'warning')
                dose_sugerida = 0.0
            else:
                dose_sugerida = resultado_bolus['bolus_total']
                
                # 🚨 REMOVIDO: A linha "dose_aplicada = dose_sugerida" foi removida.
                # Agora, 'dose_aplicada' contém o valor exato que o usuário digitou no campo.

            # 4. SALVAR A INSULINA APLICADA (Bolus)
            # 🚨 CORREÇÃO: Usa a dose_aplicada do formulário, garantindo que seja um float ou None.
            if dose_aplicada is not None and dose_aplicada > 0:
                 db_manager.salvar_registro_insulina(user_id, dose_aplicada, data_hora_str)

            # 5. SALVAR O REGISTRO DA REFEIÇÃO
            # 🚨 CORREÇÃO: Passa a dose_aplicada do formulário para salvar a refeição.
            db_manager.salvar_refeicao(
                 user_id=user_id, 
                 data_hora_str=data_hora_str, 
                 tipo_refeicao=tipo_refeicao, 
                 total_carbs=total_carbs, 
                 total_kcal=total_kcal, 
                 alimentos_selecionados_json=alimentos_selecionados_json,
    
                observacoes=observacoes,
                dose_aplicada=dose_aplicada
            )

            # 6. SALVAR A GLICEMIA (se o paciente forneceu)
            # Usamos a dose_sugerida na observação, pois foi o que o sistema calculou.
            if gc_fornecida:
                db_manager.salvar_glicemia(
                    user_id, 
                    gc_atual, 
                    data_hora_str, 
                    'Pre_Refeicao', 
                    f"GC medida antes de {tipo_refeicao}. Sugestão de Bólus: {dose_sugerida:.1f} UI"
                )
            
            # Fim do processo, exibe a dose REAL aplicada
            dose_msg = f"{dose_aplicada:.1f} UI" if dose_aplicada is not None else "N/A"
            flash(f"Refeição registrada! Dose de Insulina Aplicada: {dose_msg}", 'success')
            return redirect(url_for('dashboard'))

        except Exception as e:
            print(f'ERRO FATAL NA ROTA REFEIÇÃO: {e}')
            flash(f'Erro fatal ao processar o registro: {e}', 'danger')
            return redirect(url_for('registrar_refeicao'))

    # Lógica para GET (retorna o template)
    alimentos = db_manager.carregar_alimentos()
    now = datetime.now().strftime('%Y-%m-%dT%H:%M')
    
    return render_template('registrar_refeicao.html', alimentos=alimentos, tipos_refeicao=app_core.obter_tipos_refeicao())
    
@app.route('/excluir_registro/<int:id>', methods=['POST'])
@login_required
def excluir_registro(id):
    registro_para_excluir = db_manager.encontrar_registro(id)
    
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

@app.route('/editar_registro/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_registro(id):
    # O DEBUG é importante para confirmar o contexto
    print(f"DEBUG APP: User logado ID: {current_user.id}") 
    
    # 1. Carregar o registro do banco de dados
    registro = db_manager.encontrar_registro(id)
    
    # 2. Verificação de segurança (Tipo Casting aplicado e aprimorado)
    registro_user_id = registro.get('user_id') if registro else None
    
    if not registro or int(registro_user_id) != int(current_user.id):
        flash('Registro não encontrado ou você não tem permissão para editá-lo.', 'danger')
        return redirect(url_for('registros'))

    if request.method == 'POST':
        # --- LÓGICA DE ATUALIZAÇÃO (POST) ---
        
        tipo_principal = registro.get('tipo', '') 
        
        # Define os tipos que serão tratados como Glicemia, inclusive os subtipos
        TIPOS_DE_GLICEMIA = ['Glicemia', 'Pre_Refeicao', 'Pos_Refeicao', 'Jejum', 'Antes_Dormir']

        # =========================================================
        # EDICÃO DE GLICEMIA (Aplicável a todos os subtipos de glicemia)
        # =========================================================
        if tipo_principal in TIPOS_DE_GLICEMIA:
            # Captura todos os campos relevantes do formulário 'editar_glicemia.html'
            valor_glicemia_str = request.form.get('valor_glicemia')
            data_hora_str = request.form.get('data_hora')
            observacoes = request.form.get('observacoes')
            tipo_medicao = request.form.get('tipo_medicao') 
            
            # Captura o campo dose_aplicada (pode vir como string vazia ou None)
            dose_aplicada_str = request.form.get('dose_aplicada')
            
            try:
                # 1. Validação e Conversão de Data/Hora
                data_hora = datetime.fromisoformat(data_hora_str)
                
                # 2. Conversão da Glicemia (tratando vírgula)
                valor_glicemia = float(valor_glicemia_str.replace(',', '.'))
                
                # 3. Conversão da Dose Aplicada (tratando vírgula e vazio)
                if dose_aplicada_str:
                    dose_aplicada = float(dose_aplicada_str.replace(',', '.'))
                else:
                    dose_aplicada = None # Salva como NULL no DB se estiver vazio
                    
            except (ValueError, TypeError):
                flash('Valores de glicemia, dose de insulina ou data/hora inválidos.', 'danger')
                return redirect(url_for('editar_registro', id=id))

            # Atualiza o dicionário com os novos valores
            registro['valor'] = valor_glicemia
            registro['data_hora'] = data_hora.isoformat()
            registro['observacoes'] = observacoes
            registro['tipo_medicao'] = tipo_medicao
            
            # 🚨 ATRIBUIÇÃO GLICEMIA: Adiciona a dose aplicada ao dicionário
            registro['dose_aplicada'] = dose_aplicada
            
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
            data_hora_str = request.form.get('data_hora')
            observacoes = request.form.get('observacoes')
            tipo_refeicao_especifica = request.form.get('tipo_refeicao') 
            
            # Nota: Alimentos JSON geralmente são atualizados via JS e enviados ocultos, 
            # mas vamos garantir a coleta dos campos
            alimentos_json_str = request.form.get('alimentos_json_str', registro.get('alimentos_json', '[]'))
            
            # Captura o campo dose_aplicada (pode vir como string vazia ou None)
            dose_aplicada_str = request.form.get('dose_aplicada')
            
            if not data_hora_str or not tipo_refeicao_especifica:
                flash('Por favor, preencha a Data/Hora e o Tipo de Refeição.', 'danger')
                return redirect(url_for('editar_registro', id=id))
            
            try:
                data_hora = datetime.fromisoformat(data_hora_str)
                
                alimentos_list = json.loads(alimentos_json_str)
                total_carbs = sum(item.get('carbs', 0) for item in alimentos_list)
                total_calorias = sum(item.get('kcal', 0) for item in alimentos_list)
                
                # Conversão da Dose Aplicada (tratando vírgula e vazio)
                if dose_aplicada_str:
                    dose_aplicada = float(dose_aplicada_str.replace(',', '.'))
                else:
                    dose_aplicada = None
                    
            except (ValueError, TypeError, json.JSONDecodeError) as e:
                flash(f'Dados de refeição inválidos: {e}', 'danger')
                return redirect(url_for('editar_registro', id=id))

            # Atualiza o dicionário com os novos valores
            registro['data_hora'] = data_hora.isoformat()
            registro['observacoes'] = observacoes
            registro['alimentos_json'] = alimentos_json_str
            registro['total_carbs'] = total_carbs
            registro['total_calorias'] = total_calorias
            registro['tipo_refeicao'] = tipo_refeicao_especifica
            
            # 🚨 ATRIBUIÇÃO REFEIÇÃO: Adiciona a dose aplicada ao dicionário
            registro['dose_aplicada'] = dose_aplicada

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
        # Pré-processamento comum de data_hora
        if 'data_hora' in registro and isinstance(registro['data_hora'], str):
            try:
                registro['data_hora'] = datetime.fromisoformat(registro['data_hora'])
            except ValueError:
                pass

        tipo_principal = registro.get('tipo', '')
        
        # 🚨 CORREÇÃO PRINCIPAL DO REDIRECIONAMENTO: Agrupa os subtipos de Glicemia
        TIPOS_DE_GLICEMIA = ['Glicemia', 'Pre_Refeicao', 'Pos_Refeicao', 'Jejum', 'Antes_Dormir']

        if tipo_principal in TIPOS_DE_GLICEMIA:
            # Passa a lista completa de tipos de medição para o template
            tipos_medicao = app_core.obter_tipos_medicao() # Assumindo que você tem esta função
            return render_template('editar_glicemia.html', 
                                    registro=registro, 
                                    tipos_medicao=tipos_medicao)
            
        elif tipo_principal == 'Refeição':
            # Lógica de Refeição
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
            flash('Tipo de registro inválido para edição.', 'danger')
            return redirect(url_for('registros'))
# --- ROTAS DE ALIMENTOS ---

@app.route('/alimentos')
@login_required
@admin_only # Use o decorador que criamos para restringir acesso
def alimentos():
    # Lógica para carregar todos os alimentos do DB para a tabela de edição
    alimentos = db_manager.carregar_alimentos() # Exemplo
    
    # Assumindo que você tem um template chamado 'gerenciar_alimentos.html'
    return render_template('gerenciar_alimentos.html', alimentos=alimentos)

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
@admin_only 
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
    # CORREÇÃO: Redirecionar para o endpoint que lista/gerencia os alimentos (ex: 'alimentos')
    # Use 'alimentos' se esta for a rota que exibe a lista.
    return redirect(url_for('alimentos')) 
    
# Remova ou comente a função adicionar_alimento() que não existe mais.
# Se você tiver uma rota de 'adicionar_alimento', remova-a, pois a função
# registrar_alimento_redirect estava chamando o endpoint dela.
# app.py (Adicione esta nova rota)


@app.route('/editar_alimento/<int:id>', methods=['GET', 'POST'])
@admin_only # Garante que apenas Admin ou Gestão possa editar
def editar_alimento(id):
    # 1. Instancia o formulário e carrega o alimento
    form = AlimentoForm()
    alimento = db_manager.carregar_alimento_por_id(id)

    if not alimento:
        flash('Alimento não encontrado.', 'danger')
        return redirect(url_for('alimentos'))

    # 2. Lógica para POST (Salvamento) - WTForms Validation
    if form.validate_on_submit():
        try:
            # Os dados vêm diretamente do form.data (já validados e convertidos para float!)
            dados_atualizados = {
                'id': id,
                'alimento': form.nome.data,
                'medida_caseira': form.medida_caseira.data,
                'peso': form.peso_g.data,
                'kcal': form.kcal.data,
                'carbs': form.carbs_100g.data
            }
            
            if db_manager.atualizar_alimento(dados_atualizados):
                flash('Alimento atualizado com sucesso!', 'success')
                return redirect(url_for('alimentos'))
            else:
                flash('Erro ao atualizar o alimento no banco de dados.', 'danger')

        except Exception as e:
            # Em caso de erro de conversão, validação ou DB
            print(f"Erro ao salvar: {e}")
            flash('Erro ao processar os dados do formulário.', 'danger')

    # 3. Lógica para GET (Ou se a validação falhou)
    elif request.method == 'GET':
        # Preencher o formulário com os dados atuais do DB
        form.nome.data = alimento['alimento']
        form.medida_caseira.data = alimento['medida_caseira']
        form.peso_g.data = alimento['peso']
        form.kcal.data = alimento['kcal']
        form.carbs_100g.data = alimento['carbs']

    # 4. Renderizar o formulário (AGORA PASSANDO O FORM)
    return render_template('editar_alimento.html', alimento=alimento, form=form)
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

# ||||||------- CAlculadora Bolus -----------|||||||#

@app.route('/calculadora_bolus', methods=['GET', 'POST'])
@login_required
def calculadora_bolus():
    if current_user.role != 'paciente':
        flash('A Calculadora de Bolus é exclusiva para o perfil de Paciente.', 'danger')
        return redirect(url_for('dashboard'))

    user_id = current_user.id
    
    # 1. VERIFICAÇÃO DE SEGURANÇA: Parâmetros Clínicos
    # Buscamos os parâmetros para verificação de alerta (mesmo que o Service busque novamente)
    parametros_clinicos = db_manager.obter_parametros_clinicos(user_id)
    
    # Se glicemia_alvo ou ric_manha for nulo/faltar, redireciona para a configuração/alerta.
    if not parametros_clinicos or not parametros_clinicos.get('glicemia_alvo') or not parametros_clinicos.get('ric_manha'):
        flash("ATENÇÃO: Seus parâmetros clínicos estão incompletos. Por favor, solicite ao seu médico que os configure.", 'warning')
        return redirect(url_for('configurar_parametros')) 

    # 2. BUSCA DADOS INICIAIS
    ultima_glicemia = db_manager.buscar_ultima_glicemia(user_id)
    resultado_bolus = None
    
    # Instancia o serviço de cálculo, passando o db_manager
    # (Movemos a instanciação para fora do POST, mas pode ser dentro se preferir)
    bolus_service = BolusService(db_manager) 
    
    # 3. PROCESSAMENTO DO CÁLCULO (POST)
    if request.method == 'POST':
        try:
            # Coleta de dados do formulário
            glicemia_atual = float(request.form['glicemia_atual'])
            carbos = float(request.form['carbos'])
            
            # Não é mais necessário buscar doses_recentes aqui, pois o BolusService fará isso.
            
            # Assumimos que 'hora_refeicao' pode vir do formulário, mas o BolusService
            # que você criou usa a hora atual (datetime.now().hour) para RIC/FSI.
            # Se for necessário passar a hora do formulário, ajuste a linha abaixo:
            # hora_refeicao = request.form.get('hora_refeicao') 
            
            # EXECUTANDO O CÁLCULO
            # Seu BolusService retorna um dicionário de resultados e um erro (None se sucesso)
            resultado_bolus_dict, erro = bolus_service.calcular_bolus_total(
                gc_atual=glicemia_atual,
                carboidratos=carbos,
                paciente_id=user_id # O BolusService busca Parâmetros e IA usando este ID
            )
            
            if erro:
                flash(f"Erro no cálculo: {erro}", 'danger')
                resultado_bolus = None
            else:
                # Usa o dicionário de resultados retornado pelo BolusService
                resultado_bolus = resultado_bolus_dict
                flash(f"Bolus Calculado: {resultado_bolus['bolus_total']:.1f} Unidades.", 'success')

        except ValueError:
            flash("Erro de entrada: Glicemia e Carboidratos devem ser números válidos.", 'danger')
        except Exception as e:
            app.logger.error(f"Erro no cálculo do bolus: {e}")
            flash(f"Ocorreu um erro no cálculo. Detalhe: {e}", 'danger')

    # 4. RENDERIZAÇÃO DO FORMULÁRIO (GET ou após POST)
    return render_template('calculadora_bolus.html',
                           ultima_glicemia=ultima_glicemia,
                           # Note que 'parametros_clinicos' é a versão que passamos no GET/Verificação
                           parametros=parametros_clinicos, 
                           resultado=resultado_bolus)

# |||||| ---------Calcular FS --------- |||||||#

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

# Paciente
@app.route('/paciente')
@login_required
@paciente_required # Decorador para garantir que só pacientes acessem
def dashboard_paciente():
    paciente_id = current_user.id
    
    # O método que carrega o resumo para o template simples
    resumo_dados = db_manager.obter_resumo_paciente(paciente_id) 
    
    # Use o template mais simples que você quer para o paciente
    return render_template('dashboard_paciente.html', resumo_dados=resumo_dados)

# Medico
@app.route('/medico')
@login_required
@medico_required
def dashboard_medico():
    # Carrega dados filtrados pelo médico logado
    resumo = db_manager.obter_resumo_medico_filtrado(current_user.id)
    pacientes = db_manager.obter_pacientes_do_medico(current_user.id) 
    
    # Renderiza o template do médico
    return render_template('dashboard_medico.html', pacientes=pacientes, resumo=resumo)

# No seu arquivo app.py

@app.route('/editar_parametros/<int:paciente_id>', methods=['GET', 'POST'])
@login_required
def editar_parametros(paciente_id):
    # 1. Checagem de segurança (Mantida)
    if current_user.role not in ['admin', 'medico']:
        flash('Acesso negado. Apenas médicos e administradores podem editar parâmetros.', 'danger')
        return redirect(url_for('dashboard_medico'))
    
    # Obter dados do paciente (Mantido)
    paciente = db_manager.obter_usuario_por_id(paciente_id)

    if not paciente or paciente['role'] != 'paciente':
        flash('Paciente não encontrado ou acesso negado.', 'danger')
        return redirect(url_for('dashboard_medico'))

    # Se o paciente está vinculado a este médico, permite a edição
    #if current_user.role == 'medico' and paciente['medico_id'] != current_user.id:
        # Nota: Você pode precisar ajustar a busca por 'medico_id'
        # se o vínculo não estiver salvo na tabela 'users'.
       # flash('Você só pode editar os parâmetros de seus pacientes vinculados.', 'danger')
        #return redirect(url_for('dashboard_medico'))


    if request.method == 'POST':
        # 2. Processar o formulário POST e salvar
        
        # Obtenção de Dados (Nível de Indentação 2)
        data = request.form
        # Usa a função auxiliar para tratar None/vazio/vírgula
        ric_manha = get_float_or_none(data.get('ric_manha'))
        ric_almoco = get_float_or_none(data.get('ric_almoco'))
        ric_jantar = get_float_or_none(data.get('ric_jantar'))
        fator_sensibilidade = get_float_or_none(data.get('fator_sensibilidade'))
        meta_glicemia = get_float_or_none(data.get('meta_glicemia'))

        # Validação: Checa se algum dos campos essenciais retornou None (Nível de Indentação 2)
        if any(v is None for v in [ric_manha, ric_almoco, ric_jantar, fator_sensibilidade, meta_glicemia]):
            flash('Erro: Todos os campos devem ser preenchidos com números válidos (ponto ou vírgula como decimal).', 'danger')
            # Redireciona de volta para a mesma página de edição (Nível de Indentação 3)
            return redirect(url_for('editar_parametros', paciente_id=paciente_id))

        # Se a validação passar, tenta salvar no DB (Nível de Indentação 2)
        if db_manager.salvar_parametros_paciente(paciente_id, ric_manha, ric_almoco, ric_jantar, fator_sensibilidade, meta_glicemia):
            flash(f"Parâmetros de Bolus do paciente {paciente['username']} atualizados com sucesso!", 'success')
            # Redirecionamento de sucesso (Nível de Indentação 3)
            return redirect(url_for('perfil_paciente', paciente_id=paciente_id)) 
        else:
            flash('Erro ao salvar os parâmetros no banco de dados.', 'danger')
            # Redirecionamento de falha no DB (Nível de Indentação 3)
            return redirect(url_for('editar_parametros', paciente_id=paciente_id))

    # 3. Exibir o formulário GET (Nível de Indentação 1 - Retorna o template)
    return render_template('editar_parametros.html', paciente=paciente)
    
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
 
# ||||||| ------Rota para a Lista de Pacientes do Médico (Adaptada para Configuração)---------|||||| #
@app.route('/medico/pacientes')
@login_required
@medico_required
def lista_pacientes():
    medico_id = current_user.id
    
    try:
        # Reutilizamos o método que você já tem
        pacientes = db_manager.obter_pacientes_por_medico(medico_id) 
        
    except Exception as e:
        app.logger.error(f"Erro ao carregar pacientes para o médico {medico_id}: {e}")
        flash('Erro ao carregar lista de pacientes.', 'danger')
        pacientes = []
        
    # ATENÇÃO AQUI: Mudamos o template para o novo nome com o botão "Configurar Bolus"
    # Salve o template anterior com o nome configurar_parametros_medico_lista.html
    return render_template('configurar_parametros_medico_lista.html', pacientes=pacientes)

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

# rota perfil_paciente #

# app.py (função perfil_paciente atualizada)

@app.route('/paciente/<int:paciente_id>') 
@login_required
def perfil_paciente(paciente_id):
    # Lógica de permissão...
    if not current_user.is_medico and not current_user.is_admin:
        flash('Acesso não autorizado.', 'danger')
        return redirect(url_for('dashboard'))
        
    if not db_manager.medico_tem_acesso_a_paciente(current_user.id, paciente_id) and not current_user.is_admin:
        flash('Acesso não autorizado a este paciente.', 'danger')
        return redirect(url_for('dashboard_medico'))
    
    # --- CARREGAMENTO DE DADOS COMPLETOS ---
    paciente = db_manager.carregar_usuario_por_id(paciente_id)
    if not paciente:
        flash('Paciente não encontrado.', 'danger')
        return redirect(url_for('dashboard_medico'))

    # Carrega todos os conjuntos de dados para as ABAS do perfil_paciente.html
    registros_glicemia = db_manager.carregar_registros_glicemia_nutricao(paciente_id, limit=20) 
    ficha_data = db_manager.carregar_ficha_medica(paciente_id)
    agendamentos = db_manager.buscar_agendamentos_paciente(paciente_id)
    exames_anteriores = db_manager.buscar_exames_paciente(paciente_id)
    
    # --- NOVO CARREGAMENTO DE INSULINAS ---
    insulinas_configuradas = db_manager.carregar_insulinas_user(paciente_id)
    nomes_insulina_para_form = sorted(INSULINAS_DISPONIVEIS.keys())
    # -------------------------------------
    
    if not ficha_data:
        ficha_data = {} # Garante que o template não quebre se a ficha não existir
        
    # --- RENDERIZAÇÃO ---
    return render_template(
        'perfil_paciente.html', 
        paciente=paciente, 
        registros_glicemia=registros_glicemia, 
        ficha=ficha_data,
        agendamentos=agendamentos,
        exames_anteriores=exames_anteriores,
        
        # --- NOVAS VARIÁVEIS PASSADAS PARA O TEMPLATE ---
        insulinas_configuradas=insulinas_configuradas,
        nomes_insulina=nomes_insulina_para_form 
    )

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

from flask import request, redirect, url_for, flash
from flask_login import current_user, login_required
# Garanta que você tem current_user e login_required importados

@app.route('/medico/salvar_ficha_exame/<int:paciente_id>', methods=['POST'])
@login_required
def salvar_ficha_exame(paciente_id):
    
    # 1. Verificação de Permissão (Mantida)
    if not current_user.is_medico and not current_user.is_admin:
        flash('Acesso não autorizado.', 'danger')
        return redirect(url_for('dashboard'))

    # 2. Construção do Dicionário (Com medico_id e tratamento seguro)
    # A chamada às funções auxiliares agora funciona porque elas são globais.
    novo_exame = {
        'paciente_id': paciente_id,
        'medico_id': current_user.id, 
        
        'data_exame': request.form.get('data_exame'), 
        
        'hb_a1c': get_float_or_none('hb_a1c'),
        'glicose_jejum': get_int_or_none('glicose_jejum'),
        
        'colesterol_total': get_int_or_none('colesterol_total'),
        'hdl': get_int_or_none('hdl'),
        'tsh': get_float_or_none('tsh'), 
        
        'ldl': get_int_or_none('ldl'),
        'triglicerides': get_int_or_none('triglicerides'),
        
        'obs_medico': request.form.get('obs_medico')
    }
    
    # 3. DEBUG: Confirmação antes de enviar ao DB (Útil para ver o ID do médico)
    print(f"DEBUG: Tentando salvar Exame. Paciente ID: {paciente_id}, Médico ID: {current_user.id}")

    # 4. Chamada da Função do DB
    if db_manager.salvar_exame_laboratorial(novo_exame):
        flash('Ficha de exame salva com sucesso!', 'success')
    else:
        flash('Erro ao salvar ficha de exame. Verifique se todos os campos numéricos estão corretos.', 'danger')

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

# NO SEU ARQUIVO app.py

@app.route('/agendar_consulta', methods=['GET', 'POST'])
@login_required
def agendar_consulta():
    
    # Prepara dados para o Secretário/Admin
    pacientes = None
    medicos = db_manager.carregar_todos_os_usuarios(perfil='medico')
    
    # 🚨 LÓGICA DE POST: Definir QUEM está sendo agendado 🚨
    if request.method == 'POST':
        medico_id = request.form.get('medico_id')
        data_hora = request.form.get('data_agendamento')
        observacoes = request.form.get('observacoes')
        
        # 1. Determina o paciente_id baseado na role
        if current_user.role in ['admin', 'secretario']:
            paciente_id = request.form.get('paciente_id')
        elif current_user.role == 'paciente':
            paciente_id = current_user.id
        else:
            flash('Seu perfil não tem permissão para agendar.', 'danger')
            return redirect(url_for('dashboard'))
            
        # Tenta salvar o agendamento
        if paciente_id and medico_id and data_hora:
            
            # 🚨 CORREÇÃO: Agrupar dados em um dicionário para a função DB 🚨
            agendamento_data = {
                'paciente_id': paciente_id,
                'medico_id': medico_id,
                'data_hora': data_hora,
                'observacoes': observacoes, # Passamos a observação no dicionário
                'status': 'Agendada' 
            }
            
            # 🚨 CHAMADA CORRIGIDA: Passa APENAS o dicionário 🚨
            if db_manager.salvar_agendamento(agendamento_data):
                flash('Consulta agendada com sucesso!', 'success')
                # Redireciona o paciente para suas consultas, e o secretário para o formulário limpo
                return redirect(url_for('minhas_consultas') if current_user.role == 'paciente' else url_for('agendar_consulta'))
            else:
                flash('Erro ao agendar consulta. Tente novamente.', 'danger')
                return redirect(url_for('agendar_consulta'))
        else:
            flash('Todos os campos obrigatórios (Médico, Data, Paciente) devem ser preenchidos.', 'danger')
            return redirect(url_for('agendar_consulta'))


    # 🚨 LÓGICA DE GET: Se for Secretário/Admin, carregar lista de pacientes 🚨
    if current_user.role in ['admin', 'secretario']:
        pacientes = db_manager.carregar_todos_os_usuarios(perfil='paciente')

    return render_template('agendar_consulta.html', medicos=medicos, pacientes=pacientes)

# NO SEU ARQUIVO app.py

@app.route('/agendamentos/status/<int:agendamento_id>', methods=['POST'])
@login_required
def atualizar_status_agendamento(agendamento_id):
    # Checagem de segurança: Apenas Admin, Secretário ou o Médico relacionado devem alterar status
    if current_user.role not in ['admin', 'secretario', 'medico']:
        flash("Acesso negado para alterar status.", 'danger')
        return redirect(url_for('gerenciar_agendamentos'))
    
    # 1. Obter o novo status e o ID do formulário POST
    novo_status = request.form.get('novo_status')
    
    if not novo_status:
        flash("Status inválido.", 'danger')
        return redirect(url_for('gerenciar_agendamentos'))
    
    # 2. Chamar o método do DB
    if db_manager.atualizar_status_agendamento(agendamento_id, novo_status):
        flash(f"Status do agendamento {agendamento_id} atualizado para '{novo_status}'.", 'success')
    else:
        flash("Erro ao atualizar status no banco de dados.", 'danger')
        
    return redirect(url_for('gerenciar_agendamentos'))

@app.route('/gerenciar_pacientes_parametros')
@login_required
def gerenciar_pacientes_parametros():
    # 1. Checagem de segurança: Apenas Admin e Médicos devem acessar
    if current_user.role not in ['admin', 'medico']:
        flash('Acesso negado. Apenas médicos e administradores podem gerenciar parâmetros.', 'danger')
        return redirect(url_for('dashboard'))

    # 2. Lógica para buscar pacientes e seus parâmetros
    user_id = current_user.id
    
    if current_user.role == 'medico':
        # 🚨 BUSCA PARA MÉDICO: Apenas pacientes vinculados
        # Esta função deve retornar os dados que você precisa (ID, nome, RIC, FSI, etc.)
        pacientes = db_manager.obter_pacientes_vinculados(user_id) 
        
    elif current_user.role == 'admin':
        # 🚨 BUSCA PARA ADMIN: Todos os pacientes
        # Você deve ter esta função implementada no DatabaseManager
        pacientes = db_manager.obter_todos_pacientes_com_parametros()
        
    else:
        # Fallback, embora a checagem inicial já resolva
        pacientes = []

    # 3. Passar os dados para o template
    return render_template('gerenciar_pacientes_parametros.html', pacientes=pacientes)

@app.route('/configurar_parametros', methods=['GET', 'POST'])
@login_required
def configurar_parametros():
    user_id = current_user.id
    paciente_alvo_id = None
    
    # 1. LÓGICA DE DEFINIÇÃO DE PACIENTE ALVO
    
    if current_user.role == 'paciente':
        # Para pacientes, o paciente alvo é ele mesmo.
        paciente_alvo_id = user_id
        
        # Pacientes não podem usar POST para salvar, mas podem visualizar.
        if request.method == 'POST':
            flash("Como paciente, você não tem permissão para alterar seus próprios parâmetros clínicos. Somente seu médico pode fazê-lo.", 'danger')
            return redirect(url_for('configurar_parametros'))
    
    elif current_user.role == 'medico':
        # Médicos podem escolher o paciente a configurar via query parameter
        paciente_alvo_id = request.args.get('paciente_id', type=int)
        
        if not paciente_alvo_id:
            # Se nenhum paciente_id foi passado, o médico vê a lista de pacientes (GET).
            pacientes = db_manager.obter_pacientes_do_medico(user_id) 
            
            return render_template('configurar_parametros_medico_lista.html', 
                                    pacientes=pacientes)
            
        # O médico só pode configurar pacientes vinculados a ele.
        if not db_manager.verificar_vinculo_medico_paciente(user_id, paciente_alvo_id):
            flash("Acesso negado. O paciente não está vinculado à sua conta.", 'danger')
            return redirect(url_for('configurar_parametros'))

    elif current_user.role == 'cuidador':
        # Cuidadores (ou outros) não devem alterar, apenas visualizar ou serem bloqueados.
        flash("Seu perfil de Cuidador não permite a configuração de parâmetros clínicos.", 'danger')
        return redirect(url_for('dashboard')) 
        
    # Se chegamos até aqui, temos um paciente_alvo_id e permissão de visualização/edição.
    
    # --- LÓGICA DE PROCESSAMENTO DO FORMULÁRIO (POST) ---
    if request.method == 'POST' and current_user.role == 'medico' and paciente_alvo_id:
        try:
            # 2. Coleta de dados (Garantir que todos os campos sejam floats ou 0)
            
            # ATENÇÃO: Corrigido 'glicemia_alvo' para 'meta_glicemia' para corresponder à coluna do DB
            parametros_a_salvar = {
                'meta_glicemia': float(request.form.get('glicemia_alvo') or 0), 
                'ric_manha': float(request.form.get('ric_manha') or 0),
                'fsi_manha': float(request.form.get('fsi_manha') or 0),
                'ric_almoco': float(request.form.get('ric_almoco') or 0),
                'fsi_almoco': float(request.form.get('fsi_almoco') or 0),
                'ric_jantar': float(request.form.get('ric_jantar') or 0),
                'fsi_jantar': float(request.form.get('fsi_jantar') or 0),
                # Mantenha os demais parâmetros que você usa...
            }
            
            # ID de quem está fazendo a alteração (o médico logado)
            alterado_por_id = current_user.id 
            
            # 🚨 CORREÇÃO CRÍTICA: Passando o ID de Auditoria.
            # Assumindo que você ajustou 'salvar_parametros_clinicos' para aceitar o alterado_por_id
            if db_manager.salvar_parametros_clinicos(paciente_alvo_id, 
                                                     parametros_a_salvar, 
                                                     alterado_por_id):
                
                flash(f"Parâmetros clínicos para o paciente ID {paciente_alvo_id} salvos com sucesso!", 'success')
                return redirect(url_for('configurar_parametros', paciente_id=paciente_alvo_id))
            else:
                # Retorna o erro do DB (rollback já foi feito na função do DB)
                raise Exception("Falha ao salvar no banco de dados.")
                
        except ValueError:
            # Captura erro se o campo for texto não numérico
            flash("Erro: Todos os campos devem ser números válidos. Use ponto (.) para decimais.", 'danger')
        except Exception as e:
            # Captura outros erros, incluindo o erro propagado se o DB falhar
            app.logger.error(f"Erro ao salvar parâmetros: {e}")
            flash("Ocorreu um erro interno. Tente novamente.", 'danger')
            
            
    # --- LÓGICA DE EXIBIÇÃO DO FORMULÁRIO (GET/PÓS-POST) ---
    
    # 3. Busca dos parâmetros atuais (para pré-preencher o formulário)
    parametros_atuais = db_manager.obter_parametros_clinicos(paciente_alvo_id)
    
    # 4. Determina qual template renderizar
    if current_user.role == 'medico' and paciente_alvo_id:
        # Médico editando o paciente específico
        paciente_alvo = db_manager.carregar_usuario_por_id(paciente_alvo_id) 
        
        return render_template('configurar_parametros_medico_edicao.html',
                                paciente=paciente_alvo,
                                parametros=parametros_atuais)
                                
    elif current_user.role == 'paciente':
        # Paciente vendo seu próprio status
        return render_template('configurar_parametros_paciente.html', 
                                parametros=parametros_atuais)
                                
    # Fallback caso a lógica de médico sem paciente_id não tenha redirecionado (caso 1.1)
    return redirect(url_for('dashboard'))

@app.route('/lista_pacientes_alerta')
@login_required
@gestao_required # Ou use admin_only, dependendo da sua regra de negócio
def lista_pacientes_alerta():
    # 1. Chamar o novo método do DB
    pacientes_em_alerta = db_manager.obter_pacientes_em_alerta_detalhado()
    
    return render_template('lista_pacientes_alerta.html', 
                           pacientes=pacientes_em_alerta,
                           titulo="Pacientes com Glicemia Fora do Alvo (Últimas 48h)")

# app.py (Importe as Insulinas - Crie um dicionário com os dados que você forneceu)




@app.route('/configuracao_insulina', methods=['GET', 'POST'])
@login_required
def configuracao_insulina():
    user_id = current_user.id
    
    if request.method == 'POST':
        nome = request.form.get('nome_insulina')
        concentracao = request.form.get('concentracao')
        dose_manha = request.form.get('dose_manha')
        dose_noite = request.form.get('dose_noite')
        
        # Mapeia o nome para o tipo de ação usando o dicionário
        tipo_acao = INSULINAS_DISPONIVEIS.get(nome)
        
        if nome and tipo_acao:
            try:
                # O método já lida com desativar as outras do mesmo tipo
                db_manager.adicionar_insulina_config(
                    user_id, nome, tipo_acao, concentracao, 
                    float(dose_manha) if dose_manha else None, 
                    float(dose_noite) if dose_noite else None
                )
                flash(f'Insulina {nome} configurada e ativada com sucesso.', 'success')
            except Exception as e:
                flash(f'Erro ao salvar configuração: {e}', 'error')
        else:
            flash('Por favor, selecione uma insulina e preencha a concentração.', 'error')
            
        return redirect(url_for('configuracao_insulina'))

    # GET Request: Carregar dados
    insulinas_ativas = db_manager.carregar_insulinas_user(user_id)
    
    # Filtra as insulinas disponíveis para o formulário
    nomes_insulina_para_form = sorted(INSULINAS_DISPONIVEIS.keys())

    return render_template('configuracao_insulina.html', 
                           insulinas_ativas=insulinas_ativas,
                           nomes_insulina=nomes_insulina_para_form)

@app.route('/configurar_insulina_paciente/<int:paciente_id>', methods=['POST'])
@login_required
def configurar_insulina_paciente(paciente_id):
    # Verificação de permissão: Apenas médicos (assumindo que current_user.role == 'Medico')
    if current_user.role != 'Medico':
         flash('Acesso negado. Apenas médicos podem configurar insulinas.', 'danger')
         return redirect(url_for('perfil_paciente', paciente_id=paciente_id))

    nome = request.form.get('nome_insulina')
    concentracao = request.form.get('concentracao')
    dose_manha = request.form.get('dose_manha')
    dose_noite = request.form.get('dose_noite')
    
    tipo_acao = INSULINAS_DISPONIVEIS.get(nome)
    
    if nome and tipo_acao:
        try:
            # Chama a função do DatabaseManager para salvar a nova configuração
            db_manager.adicionar_insulina_config(
                paciente_id, nome, tipo_acao, concentracao, 
                float(dose_manha) if dose_manha else None, 
                float(dose_noite) if dose_noite else None
            )
            flash(f'Insulina {nome} configurada e ativada com sucesso para o paciente.', 'success')
        except Exception as e:
            flash(f'Erro ao salvar configuração: {e}', 'error')
    else:
        flash('Por favor, selecione uma insulina, preencha a concentração e as doses relevantes.', 'error')
        
    return redirect(url_for('perfil_paciente', paciente_id=paciente_id))


if __name__ == '__main__':
    app.run(debug=True)