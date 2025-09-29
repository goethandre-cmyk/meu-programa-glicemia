from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from functools import wraps
import json
import logging
import plotly.graph_objects as go
import numpy as np
import os
# Certifique-se de que DatabaseManager está disponível
from database_manager import DatabaseManager # Assumindo a importação real aqui
from models import User # <--- IMPORTAÇÃO DA CLASSE USER DE models.py
from relatorios import relatorios_bp # ou simplesmente 'from relatorios import relatorios_bp' dependendo da estrutura

# --- Configuração da Aplicação ---
app = Flask(__name__)
app.register_blueprint(relatorios_bp)
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

# --- Inicialização da AppCore com a instância GLOBAL do DatabaseManager
app_core = AppCore(db_manager)

# --- Carregador de Usuário para o Flask-Login ---
@login_manager.user_loader
def load_user(user_id):
    if db_manager:
        user_data = db_manager.carregar_usuario_por_id(int(user_id))
        if user_data:
            # O objeto User é criado a partir da classe importada de models.py
            return User(
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
    return None

# --- DECORADOR DE ACESSO EXCLUSIVO PARA MÉDICOS (MANTIDO) ---
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

# --- NOVO DECORADOR DE ACESSO PARA GESTÃO (ADMIN/MÉDICO/SECRETÁRIO) ---
def gestao_required(f):
    """
    Requer que o usuário logado tenha a função 'admin', 'medico' ou 'secretario'.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Você precisa estar logado para acessar esta página.', 'warning')
            return redirect(url_for('login'))
            
        # Usa as propriedades da classe User importada
        if not (current_user.is_admin or current_user.is_medico or current_user.is_secretario):
            flash('Acesso negado. Você não tem permissão para gerenciar esta área.', 'danger')
            return redirect(url_for('dashboard')) 
            
        return f(*args, **kwargs)
    return decorated_function

# --- Lista de Tipos de Diabetes para o <select> (mantida) ---
TIPOS_DIABETES = ['Tipo 1', 'Tipo 2', 'LADA', 'MODY', 'Gestacional', 'Outro/Não Especificado']

# --- Funções de Ajuda (get_status_class mantida) ---
def get_status_class(valor_glicemia):
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

# --- ROTAS DA APLICAÇÃO ---
@app.route('/')
def home():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

# Rotas de Login, Logout e Cadastro (mantidas)
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user_data = db_manager.carregar_usuario(username)
        if user_data and check_password_hash(user_data['password_hash'], password):
            user = User(
                id=user_data.get('id'), username=user_data.get('username'), password_hash=user_data.get('password_hash'),
                role=user_data.get('role', 'user').lower(), email=user_data.get('email'), razao_ic=user_data.get('razao_ic', 1.0),
                fator_sensibilidade=user_data.get('fator_sensibilidade', 1.0), data_nascimento=user_data.get('data_nascimento'), sexo=user_data.get('sexo')
            )
            login_user(user)
            app_core.salvar_log_acao(f'Login', user.username)
            flash('Login realizado com sucesso!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Nome de usuário ou senha inválidos.', 'danger')
            app.logger.warning(f'Tentativa de login falha para o usuário {username}')
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
    # Lógica de cadastro (mantida)
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        password_confirm = request.form['password_confirm']
        role = request.form.get('role', 'paciente').lower() 

        if len(username) < 3 or len(password) < 6:
            flash('Nome de usuário deve ter no mínimo 3 caracteres e senha no mínimo 6.', 'danger')
            return redirect(url_for('cadastro'))

        if password != password_confirm:
            flash('A senha e a confirmação de senha não coincidem.', 'danger')
            return redirect(url_for('cadastro'))

        hashed_password = generate_password_hash(password)
        
        novo_usuario = {
            'username': username, 'password_hash': hashed_password, 'role': role, 'email': request.form.get('email'),
            'nome_completo': request.form.get('nome_completo'), 'telefone': request.form.get('telefone'),
            'data_nascimento': request.form.get('data_nascimento'), 'sexo': request.form.get('sexo'),
            'razao_ic': float(request.form.get('razao_ic', 1.0)), 'fator_sensibilidade': float(request.form.get('fator_sensibilidade', 1.0)),
            'documento': None, 'crm': None, 'cns': None, 'especialidade': None
        }
        
        if role == 'medico':
            novo_usuario['documento'] = request.form.get('documento')
            novo_usuario['crm'] = request.form.get('crm')
            novo_usuario['cns'] = request.form.get('cns')
            novo_usuario['especialidade'] = request.form.get('especialidade')

            if not all([novo_usuario['nome_completo'], novo_usuario['documento'], novo_usuario['crm'], novo_usuario['especialidade']]):
                flash('Todos os campos de registro profissional (Médico) são obrigatórios.', 'danger')
                return redirect(url_for('cadastro'))

        if db_manager.salvar_usuario(novo_usuario):
            flash('Cadastro realizado com sucesso! Faça login para começar.', 'success')
            app.logger.info(f'Novo usuário cadastrado: {username} ({role})')
            return redirect(url_for('login'))
        else:
            flash('Nome de usuário já existe. Tente outro.', 'danger')
            return redirect(url_for('cadastro'))
            
    return render_template('cadastro.html', especialidades=ESPECIALIDADES_MEDICAS)

@app.context_processor
def inject_now():
    return {'current_year': datetime.now().year}
@app.route('/')
def index():
    """
    Rota inicial. Redireciona:
    - Usuários logados para o dashboard
    - Usuários não logados para a página de login
    """
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))  # ou 'dashboard_gestao', se for específico
    else:
        return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    # 1. Verifica se é Admin/Secretário e redireciona para a DASHBOARD DE GESTÃO (novo ponto de partida)
    if current_user.is_admin or current_user.is_secretario:
        return redirect(url_for('dashboard_gestao'))
    
    # 2. Se for MÉDICO, redireciona para o painel específico
    if current_user.is_medico:
        return redirect(url_for('dashboard_medico'))
        
    # 3. Se for PACIENTE ou outro usuário, a execução continua aqui.
    resumo_dados = carregar_dados_dashboard(current_user.id)
    return render_template('dashboard_paciente.html', resumo_dados=resumo_dados)

# NOVA ROTA: Dashboard de Gestão (Admin/Secretário)

@app.route('/dashboard_gestao')
@login_required
@gestao_required # Usa o novo decorador
def dashboard_gestao():
    # 1. Obter os dados necessários
    # É mais eficiente calcular os totais diretamente no DB (se possível), mas mantendo sua lógica:
    total_usuarios = len(db_manager.carregar_todos_os_usuarios())
    
    # 2. Criar o dicionário 'resumo' com os dados para o template
    resumo_dados = {
        'total_usuarios': total_usuarios,
        # Você pode adicionar outras métricas de gestão aqui, se necessário:
        # 'total_medicos': db_manager.contar_medicos(),
        # 'total_pacientes': db_manager.contar_pacientes(),
    }

    # 3. Passar a variável 'resumo_dados' para o template com o nome 'resumo'
    # O template espera: {{ resumo.total_usuarios }}
    return render_template('dashboard_gestao.html', resumo=resumo_dados)

# Rota do Dashboard Médico (MANTIDA)
@app.route('/dashboard_medico')
@login_required
@medico_required
def dashboard_medico():
    pacientes = db_manager.obter_pacientes_por_medico(current_user.id)
    resumo_dados = {'total_pacientes': len(pacientes) if pacientes else 0}
    return render_template('dashboard_medico.html', pacientes=pacientes, resumo_dados=resumo_dados)


# --- ROTAS DA ÁREA ADMINISTRATIVA E DE GESTÃO ---

@app.route('/gerenciar_usuarios')
@login_required
@gestao_required # DECORADOR APLICADO: Permite Admin ou Secretário
def gerenciar_usuarios():
    # Verificação interna removida
    usuarios = db_manager.carregar_todos_os_usuarios()
    return render_template('gerenciar_usuarios.html', usuarios=usuarios)

# Rotas de edição, exclusão e vínculo de usuários (mantidas com checagem interna para Admin-Only, quando apropriado)
@app.route('/editar_usuario/<username>', methods=['GET', 'POST'])
@login_required
def editar_usuario(username):
    # 1. AUTORIZAÇÃO E BUSCA DO USUÁRIO
    
    usuario = db_manager.carregar_usuario(username)
    if not usuario:
        flash('Usuário não encontrado.', 'danger')
        return redirect(url_for('gerenciar_usuarios'))

    # Lógica de Autorização Corrigida e Mais Granular
    user_role = usuario.get('role')
    
    # Restrição de acesso:
    # 1. Usuário logado é o próprio usuário a ser editado? (Permite edição do próprio perfil)
    is_self_edit = (current_user.username == username)
    # 2. Usuário logado tem permissão de gestão? (Admin/Secretario/Medico)
    is_manager = current_user.role in ['admin', 'secretario', 'medico']

    # Regras de Permissão:
    if not is_self_edit and not is_manager:
        flash('Acesso não autorizado. Você só pode editar seu próprio perfil.', 'danger')
        return redirect(url_for('dashboard'))
    
    # Regra Adicional: Médicos/Secretários não podem editar uns aos outros (a menos que sejam Admin)
    if current_user.role in ['medico', 'secretario'] and user_role in ['medico', 'secretario'] and not is_self_edit and current_user.role != 'admin':
        flash('Você não tem permissão para editar outros perfis profissionais.', 'danger')
        return redirect(url_for('gerenciar_usuarios'))
        
    # --- FIM DA AUTORIZAÇÃO ---

    medicos = db_manager.carregar_medicos()

    if request.method == 'POST':
        # 2. COLETA DE DADOS DO FORMULÁRIO (POST)
        
        # Lógica de vinculação de médico
        if user_role == 'paciente':
            medico_id_selecionado = request.form.get('medico_vinculado')
            if medico_id_selecionado:
                # É crucial que o ID seja um INT
                db_manager.vincular_paciente_medico(usuario['id'], int(medico_id_selecionado))
        
        nome_completo = request.form.get('nome_completo')
        # O role pode ser alterado apenas pelo Admin, caso contrário, usa o valor atual.
        role = request.form.get('role', user_role).lower()
        email = request.form.get('email')
        nova_senha = request.form.get('senha')
        confirmar_senha = request.form.get('confirmar_senha')
        data_nascimento = request.form.get('data_nascimento')
        sexo = request.form.get('sexo')
        
        # Lógica de atualização de senha
        if nova_senha:
            if nova_senha != confirmar_senha:
                flash('A senha e a confirmação de senha não coincidem.', 'danger')
                return render_template('editar_usuario.html', usuario=usuario, medicos=medicos)
            
            if len(nova_senha) < 6:
                 flash('A nova senha deve ter no mínimo 6 caracteres.', 'danger')
                 return render_template('editar_usuario.html', usuario=usuario, medicos=medicos)
                 
            usuario['password_hash'] = generate_password_hash(nova_senha)
            flash('Senha alterada com sucesso!', 'info')

        # Atualização dos campos comuns
        usuario['nome_completo'] = nome_completo
        usuario['role'] = role # O role atualizado
        usuario['email'] = email
        usuario['data_nascimento'] = data_nascimento
        usuario['sexo'] = sexo
        
        # Atualização dos campos de Paciente
        usuario['razao_ic'] = float(request.form.get('razao_ic', 0.0))
        usuario['fator_sensibilidade'] = float(request.form.get('fator_sensibilidade', 0.0))
        usuario['meta_glicemia'] = float(request.form.get('meta_glicemia', 0.0))

        # ⭐️ CORREÇÃO CRÍTICA: Atualização dos campos de Profissional (Médico/Secretário/Admin)
        if role in ['medico', 'secretario', 'admin']:
            usuario['documento'] = request.form.get('documento')
            usuario['crm'] = request.form.get('crm')
            usuario['cns'] = request.form.get('cns') # Adicionado cns, se for o caso
            
            if role == 'medico':
                usuario['especialidade'] = request.form.get('especialidade')
            else:
                usuario['especialidade'] = None # Limpa se não for médico
        # ⭐️ FIM DA CORREÇÃO CRÍTICA

        if db_manager.atualizar_usuario(usuario):
            flash('Usuário atualizado com sucesso!', 'success')
            return redirect(url_for('gerenciar_usuarios'))
        else:
            # Esta falha pode ocorrer por restrição de UNIQUE (username ou email duplicado)
            flash('Erro ao atualizar usuário. Verifique se o Nome de Usuário ou E-mail já existe.', 'danger')

    # Para requisição GET, renderiza o template (garantindo que o template tem os campos de médico/secretário)
    return render_template('editar_usuario.html', 
                           usuario=usuario, 
                           medicos=medicos, 
                           especialidades=ESPECIALIDADES_MEDICAS)


@app.route('/excluir_usuario/<username>', methods=['POST'])
@login_required
def excluir_usuario(username):
    # Regras de negócio existentes (corretas)
    if not current_user.is_admin:
        flash('Acesso não autorizado.', 'danger')
        return redirect(url_for('dashboard'))

    if current_user.username == username:
        flash('Você não pode excluir a sua própria conta.', 'danger')
        return redirect(url_for('gerenciar_usuarios'))

    # CHAMADA PARA A NOVA FUNÇÃO SEGURA:
    if db_manager.excluir_usuario_e_dados(username): # <<< MUDANÇA AQUI
        flash(f'Usuário {username} e todos os dados relacionados excluídos com sucesso!', 'success')
    else:
        # Nota: O erro pode ser que o usuário não existe ou houve uma falha de DB/FK
        flash(f'Erro ao excluir o usuário {username}. Possível violação de dados ou usuário não encontrado.', 'danger')

    return redirect(url_for('gerenciar_usuarios'))

@app.route('/vincular_cuidador_paciente', methods=['POST'])
@login_required
def vincular_cuidador_paciente():
    # Lógica de vínculo (mantida)
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
    # Lógica de vínculo (mantida)
    if not current_user.is_admin:
        flash('Acesso não autorizado.', 'danger')
        return redirect(url_for('dashboard'))

    paciente = db_manager.carregar_usuario(username)
    if not paciente:
        flash('Paciente não encontrado.', 'danger')
        return redirect(url_for('gerenciar_usuarios'))

    cuidadores = db_manager.carregar_cuidadores()
    
    return render_template('vincular_cuidador.html', paciente=paciente, cuidadores=cuidadores)


# --- ROTAS DE REGISTRO DO PACIENTE (mantidas) ---

@app.route('/registros')
@login_required
def registros():
    registros_list = db_manager.carregar_registros(current_user.id)
    
    registros_formatados = []
    for registro in registros_list:
        tipo = registro.get('tipo')
        tipo_exibicao = registro.get('tipo_refeicao', tipo) 
        
        data_hora_str = registro.get('data_hora')
        if data_hora_str and isinstance(data_hora_str, str):
            try:
                # Converte a string de data_hora para objeto datetime
                registro['data_hora'] = datetime.fromisoformat(data_hora_str)
            except ValueError:
                pass 

        # 💥 CORREÇÃO PRINCIPAL: Garante que os totais sejam 0.0 se forem None
        # O Jinja2 precisa de um float ou int aqui para o método .format() funcionar.
        
        # Calorias: Pega o valor, se for None, usa 0.0
        registro['total_calorias'] = registro.get('total_calorias') if registro.get('total_calorias') is not None else 0.0
        
        # Carboidratos: Pega o valor, se for None, usa 0.0
        registro['total_carboidratos'] = registro.get('total_carboidratos') if registro.get('total_carboidratos') is not None else 0.0
        
        registro['tipo_exibicao'] = tipo_exibicao
        registros_formatados.append(registro)
    
    return render_template(
        'registros.html', 
        registros=registros_formatados, 
        current_user=current_user, 
        get_status_class=get_status_class
    )
    
@app.route('/registrar_glicemia', methods=['GET'])
@login_required
def registrar_glicemia():
    return render_template('registrar_glicemia.html') 
 
@app.route('/salvar_glicemia', methods=['POST'])
@login_required
def salvar_glicemia():
    # Lógica de salvar glicemia (mantida)
    valor_glicemia = request.form.get('valor')
    data_hora_str = request.form.get('data_hora')
    observacoes = request.form.get('observacoes')

    if not valor_glicemia or not data_hora_str:
        flash('Por favor, preencha todos os campos obrigatórios.', 'danger')
        return redirect(url_for('registros'))
    
    try:
        data_hora = datetime.fromisoformat(data_hora_str)
        valor_glicemia = float(valor_glicemia.replace(',', '.'))
    except (ValueError, TypeError):
        flash('Valores inválidos para glicemia ou data/hora.', 'danger')
        return redirect(url_for('registros'))

    dados_registro = {
        'user_id': current_user.id, 'data_hora': data_hora.isoformat(), 'tipo': 'Glicemia', 'valor': valor_glicemia,
        'observacoes': observacoes, 'total_carbs': None, 'total_calorias': None, 'alimentos_json': None, 'tipo_refeicao': None,
    }
    
    if db_manager.salvar_registro(dados_registro):
        flash('Registro de glicemia salvo com sucesso!', 'success')
        app_core.salvar_log_acao(f'Registro de glicemia salvo: {valor_glicemia}', current_user.username)
    else:
        flash('Erro ao salvar registro de glicemia.', 'danger')
        
    return redirect(url_for('registros'))
    
@app.route('/registrar_refeicao', methods=['POST'])
@login_required
def salvar_refeicao():
    """Rota POST para processar e salvar o registro complexo de refeição."""
    
    # 1. Obter dados simples do formulário
    data_hora_str = request.form.get('data_hora')
    tipo_refeicao = request.form.get('tipo')
    observacoes = request.form.get('observacoes')
    
    # 2. Obter totais calculados pelo JS (Hidden Inputs)
    # Mantemos os nomes lidos do formulário
    total_carbs_lido = request.form.get('total_carbs', '0.0')
    total_kcal_lido = request.form.get('total_kcal', '0.0')
    
    # 3. Obter a lista JSON de alimentos selecionados
    alimentos_json_str = request.form.get('alimentos_selecionados')
    
    if not data_hora_str or not tipo_refeicao:
        flash('Data, Hora e Tipo de Refeição são obrigatórios.', 'warning')
        return redirect(url_for('refeicao'))

    try:
        # Conversão de tipos
        data_hora = datetime.strptime(data_hora_str, '%Y-%m-%dT%H:%M')
        
        # Conversão dos totais para float
        total_carbs_float = float(total_carbs_lido)
        total_kcal_float = float(total_kcal_lido)
        
        # Deserializar a lista de alimentos
        alimentos_detalhes = json.loads(alimentos_json_str)
        
        # 4. Preparar o objeto de registro para o DB
        registro_refeicao = {
            'user_id': current_user.id,
            'data_hora': data_hora,
            'tipo': tipo_refeicao,
            'observacoes': observacoes,
            'detalhes_alimentos': alimentos_detalhes, 
            'tipo_registro': 'refeicao',
            
            # 💥 CORREÇÃO APLICADA AQUI: 
            # Usamos os nomes esperados pelo seu app.py/registros.html 
            # para garantir o mapeamento correto no DB.
            'total_carboidratos': total_carbs_float, 
            'total_calorias': total_kcal_float,      
        }
        
        # 5. Salvar no Banco de Dados
        db_manager.salvar_registro(registro_refeicao)
        
        flash('Refeição registrada com sucesso!', 'success')
        return redirect(url_for('dashboard')) 
        
    except ValueError:
        flash('Formato de Data/Hora ou Totais de Nutrientes inválido.', 'danger')
        return redirect(url_for('refeicao'))
    except json.JSONDecodeError:
        flash('Erro ao processar a lista de alimentos. Tente novamente.', 'danger')
        return redirect(url_for('refeicao'))
    except Exception as e:
        app.logger.error(f"Erro ao salvar refeição: {e}")
        flash('Erro interno ao salvar o registro da refeição.', 'danger')
        return redirect(url_for('refeicao'))
    
@app.route('/excluir_registo/<int:id>', methods=['POST'])
@login_required
def excluir_registo(id):
    # Lógica de exclusão de registro (mantida)
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
    
@app.route('/editar_registo/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_registo(id):
    # Lógica de edição de registro (mantida e completada)
    registro = db_manager.encontrar_registro(id)
    if not registro or registro.get('user_id') != current_user.id:
        flash('Registro não encontrado ou você não tem permissão para editá-lo.', 'danger')
        return redirect(url_for('registros'))

    if request.method == 'POST':
        if registro.get('tipo') == 'Glicemia':
            valor_glicemia = request.form.get('valor_glicemia')
            data_hora_str = request.form.get('data_hora')
            observacoes = request.form.get('observacoes')
            
            try:
                data_hora = datetime.fromisoformat(data_hora_str)
                valor_glicemia = float(valor_glicemia.replace(',', '.'))
            except (ValueError, TypeError):
                flash('Valores de glicemia ou data/hora inválidos.', 'danger')
                return redirect(url_for('editar_registo', id=id))

            registro['valor'] = valor_glicemia
            registro['data_hora'] = data_hora.isoformat()
            registro['observacoes'] = observacoes
            
            if db_manager.atualizar_registro(registro):
                flash('Registro de glicemia atualizado com sucesso!', 'success')
                app_core.salvar_log_acao(f'Registro de glicemia {id} atualizado', current_user.username)
            else:
                flash('Erro ao atualizar registro.', 'danger')
                
            return redirect(url_for('registros'))

        elif registro.get('tipo') == 'Refeição':
            data_hora_str = request.form.get('data_hora')
            observacoes = request.form.get('observacoes')
            
            alimentos_json_str = request.form.get('alimentos_selecionados') 
            tipo_refeicao_especifica = request.form.get('tipo_refeicao') 
            
            if not data_hora_str or not alimentos_json_str:
                flash('Por favor, preencha todos os campos obrigatórios.', 'danger')
                return redirect(url_for('editar_registo', id=id))
            
            try:
                data_hora = datetime.fromisoformat(data_hora_str)
                alimentos_list = json.loads(alimentos_json_str)
                
                # Cálculo revisado
                total_carbs = sum(item.get('carbs', 0) * item.get('quantidade', 1) for item in alimentos_list)
                total_calorias = sum(item.get('kcal', 0) * item.get('quantidade', 1) for item in alimentos_list)
                
            except (ValueError, TypeError, json.JSONDecodeError) as e:
                flash(f'Dados de refeição inválidos: {e}', 'danger')
                return redirect(url_for('editar_registo', id=id))

            registro['data_hora'] = data_hora.isoformat()
            registro['observacoes'] = observacoes
            registro['alimentos_json'] = alimentos_json_str
            registro['total_carbs'] = total_carbs
            registro['total_calorias'] = total_calorias
            registro['tipo_refeicao'] = tipo_refeicao_especifica
            
            if db_manager.atualizar_registro(registro):
                flash('Registro de refeição atualizado com sucesso!', 'success')
                app_core.salvar_log_acao(f'Registro de refeição {id} atualizado', current_user.username)
            else:
                flash('Erro ao atualizar registro de refeição.', 'danger')
            return redirect(url_for('registros'))
        
        else:
            flash('Tipo de registro inválido.', 'danger')
            return redirect(url_for('registros'))

    else: 
        if registro.get('tipo') == 'Glicemia':
            if 'data_hora' in registro and isinstance(registro['data_hora'], str):
                try:
                    registro['data_hora'] = datetime.fromisoformat(registro['data_hora'])
                except ValueError:
                    pass
            return render_template('editar_glicemia.html', registro=registro)
        
        elif registro.get('tipo') == 'Refeição':
            alimentos = db_manager.carregar_alimentos()
            # Assumindo a existência do template editar_refeicao.html
            return render_template('editar_refeicao.html', registro=registro, alimentos=alimentos, tipos_refeicao=app_core.obter_tipos_refeicao())


# --- ROTAS DE ALIMENTOS ---

@app.route('/alimentos')
@login_required
@gestao_required # DECORADOR APLICADO
def alimentos():
    lista_alimentos = db_manager.carregar_alimentos()
    return render_template('alimentos.html', alimentos=lista_alimentos)

@app.route('/excluir_alimento/<int:id>', methods=['POST'])
@login_required
@gestao_required # DECORADOR APLICADO
def excluir_alimento(id):
    sucesso = db_manager.excluir_alimento(id)
    if sucesso:
        flash('Alimento excluído com sucesso!', 'success')
    else:
        flash('Erro ao excluir o alimento.', 'danger')
    return redirect(url_for('alimentos'))

@app.route('/adicionar_alimento', methods=['GET', 'POST'])
@login_required
@gestao_required # DECORADOR APLICADO
def adicionar_alimento():
    if request.method == 'POST':
        try:
            nome = request.form['nome']
            medida_caseira = request.form['medida_caseira']
            peso_g = float(request.form['peso_g'].replace(',', '.'))
            kcal = float(request.form['kcal'].replace(',', '.'))
            carbs_100g = float(request.form['carbs_100g'].replace(',', '.')) 
            
            novo_alimento = {
                'alimento': nome, 'medida_caseira': medida_caseira, 'peso': peso_g, 
                'kcal': kcal, 'carbs': carbs_100g
            }
            
            if db_manager.salvar_alimento(novo_alimento):
                flash('Alimento adicionado com sucesso!', 'success')
            else:
                flash('Erro ao adicionar o alimento.', 'danger')
        except (ValueError, TypeError):
            flash('Dados do alimento inválidos. Por favor, verifique os valores numéricos.', 'danger')
        
        return redirect(url_for('alimentos'))

    alimentos = db_manager.carregar_alimentos()
    return render_template('adicionar_alimento.html', alimentos=alimentos)

@app.route('/registrar_alimento')
@login_required
def registrar_alimento_redirect():
    return redirect(url_for('adicionar_alimento'))


# --- ROTAS DE UTILIDADE GERAL (No seu arquivo principal, ex: app.py) ---

@app.route('/refeicao')
@login_required
def refeicao():
    """Rota GET para o formulário de registro de refeição."""
    # O HTML já tem a lista de tipos de refeição fixa, mas é bom ter uma fallback.
    return render_template('registrar_refeicao.html') # Usando o novo template

# Ajustando a rota de busca para aceitar POST, conforme o JS espera

@app.route('/buscar_alimentos', methods=['GET', 'POST'])
def buscar_alimentos():
    query = request.args.get('query', '') or request.form.get('termo_pesquisa', '')
    
    if len(query) >= 3:
        # DB agora retorna chaves simples e em minúsculas: 'alimento', 'kcal', 'cho'
        resultados_originais = db_manager.buscar_alimentos_por_nome(query) 

        resultados_padronizados = []
        for item in resultados_originais:
            
            # ATENÇÃO: Os carboidratos agora vêm na chave 'cho'
            resultados_padronizados.append({
                # Mapeamento do DB para o Frontend:
                'nome': item.get('alimento', 'undefined'),       
                'Carbs': item.get('cho', 0.0),    # <--- AQUI VEM DE 'cho'
                'Kcal': item.get('kcal', 0.0),                  
                'Porcao': item.get('medida_caseira', '100g'), 
                
                # Chaves Internas/Cálculo
                'cho': item.get('cho', 0.0),      # <--- E AQUI VEM DE 'cho'
                'kcal': item.get('kcal', 0.0),                  
                'alimento': item.get('alimento', 'undefined'), 
                
                'id': item.get('id', None),
                'porcao_peso': item.get('peso', 100.0) 
            })
        
        return jsonify(resultados=resultados_padronizados)
    
    return jsonify(resultados=[])

@app.route("/calculadora-bolus")
def calculadora_bolus():
    return render_template("calculadora.html")

# --- ROTAS DA ÁREA MÉDICA ---

# Rota para o Cadastro de Novo Paciente
@app.route('/medico/novo_paciente', methods=['GET', 'POST'])
@login_required 
@gestao_required
def novo_paciente():
    TIPOS_DIABETES = ['Tipo 1', 'Tipo 2', 'Gestacional', 'Outro'] # Assumindo que esta lista está definida
    
    if request.method == 'POST':
        # 1. Obter os dados do formulário
        nome_completo = request.form.get('nome_completo')
        email = request.form.get('email')
        senha = request.form.get('senha')
        data_nascimento_str = request.form.get('data_nascimento') 
        tipo_diabetes = request.form.get('tipo_diabetes')

        # 2. Obter o ID do Médico Logado
        medico_id = current_user.id # <--- AQUI ESTÁ O VÍNCULO!

        if not nome_completo or not email or not senha or not data_nascimento_str or not tipo_diabetes:
            flash('Por favor, preencha todos os campos do formulário.', 'warning')
            return render_template('cadastrar_paciente_medico.html', tipos_diabetes=TIPOS_DIABETES)

        try:
            hashed_password = generate_password_hash(senha)
            datetime.strptime(data_nascimento_str, '%Y-%m-%d').date()
            
            # Dados do Usuário
            novo_usuario_data = {
                'username': email, 'email': email, 'password_hash': hashed_password,
                'nome_completo': nome_completo, 'data_nascimento': data_nascimento_str, 
            }
            # Dados da Ficha Inicial (Anamnese simplificada)
            ficha_inicial_data = {
                'tipo_diabetes': tipo_diabetes, 
                'data_diagnostico': datetime.now().strftime('%Y-%m-%d') # Usa a data de cadastro como data de diagnóstico inicial
            }

            # *** IMPORTANTE: USAR A FUNÇÃO QUE CRIA O PACIENTE E VINCULA O ID DO MÉDICO ***
            if db_manager.criar_paciente_e_ficha_inicial(novo_usuario_data, medico_id, ficha_inicial_data):
                flash(f'Paciente {nome_completo} cadastrado e **vinculado** com sucesso!', 'success')
                return redirect(url_for('lista_pacientes'))
            else:
                flash('Erro: O nome de usuário/e-mail já existe ou houve falha no DB.', 'danger')
                return render_template('cadastrar_paciente_medico.html', tipos_diabetes=TIPOS_DIABETES)

        except Exception as e:
            app.logger.error(f"Erro ao cadastrar paciente: {e}") 
            flash('Erro interno ao cadastrar paciente. Verifique o log do servidor.', 'danger')
            return render_template('cadastrar_paciente_medico.html', tipos_diabetes=TIPOS_DIABETES)

    # Se for GET
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

# Rotas restantes (perfil_paciente, ficha_medica, agendamentos, etc.) mantidas com as verificações de permissão mais complexas ou o novo @gestao_required:

@app.route('/pacientes')
@login_required
def pacientes():
    if not current_user.is_medico:
        flash('Acesso não autorizado. Esta página é exclusiva para médicos.', 'danger')
        return redirect(url_for('dashboard'))
    return redirect(url_for('lista_pacientes'))

@app.route('/relatorio_medico')
@login_required
@medico_required
def relatorio_medico():
    return render_template('relatorio_medico.html')

@app.route('/paciente/<int:paciente_id>')
@login_required
def perfil_paciente(paciente_id):
    if not (current_user.is_medico or current_user.is_admin):
        flash('Acesso não autorizado.', 'danger')
        return redirect(url_for('dashboard'))
    if not current_user.is_admin and not db_manager.medico_tem_acesso_a_paciente(current_user.id, paciente_id):
        flash('Acesso não autorizado a este paciente.', 'danger')
        return redirect(url_for('dashboard_medico'))
    
    paciente = db_manager.carregar_usuario_por_id(paciente_id)
    registros = db_manager.carregar_registros(paciente_id)
    ficha_medica = db_manager.carregar_ficha_medica(paciente_id)
    return render_template('perfil_paciente.html', paciente=paciente, registros_glicemia=registros, ficha_medica=ficha_medica)

@app.route('/ficha_medica/<int:paciente_id>', methods=['GET', 'POST'])
@login_required
def ficha_medica(paciente_id):
    paciente = db_manager.carregar_usuario_por_id(paciente_id)
    if not paciente or paciente.get('role') not in ['paciente', 'user']:
        flash('Paciente não encontrado.', 'danger')
        return redirect(url_for('dashboard'))
    if not current_user.is_admin and not db_manager.medico_tem_acesso_a_paciente(current_user.id, paciente_id):
        flash('Acesso negado. Você não tem permissão para visualizar a ficha deste paciente.', 'danger')
        return redirect(url_for('dashboard'))
        
    ficha_medica_data = db_manager.carregar_ficha_medica(paciente_id)
    if not ficha_medica_data: ficha_medica_data = {'paciente_id': paciente_id}

    if request.method == 'POST':
        ficha_medica_data['tipo_diabetes'] = request.form.get('tipo_diabetes')
        ficha_medica_data['insulina_basal'] = request.form.get('insulina_basal')
        ficha_medica_data['insulina_bolus'] = request.form.get('insulina_bolus')
        ficha_medica_data['observacoes'] = request.form.get('observacoes')
        ficha_medica_data['data_diagnostico'] = request.form.get('data_diagnostico')

        db_manager.salvar_ficha_medica(ficha_medica_data)
        flash('Ficha médica atualizada com sucesso!', 'success')
        return redirect(url_for('perfil_paciente', paciente_id=paciente_id))

    return render_template('ficha_medica.html', paciente=paciente, ficha=ficha_medica_data, tipos_diabetes=TIPOS_DIABETES)

@app.route('/salvar_ficha_medica', methods=['POST'])
@login_required
@gestao_required # DECORADOR APLICADO
def salvar_ficha_medica():
    try:
        paciente_id = int(request.form['paciente_id'])
        ficha_data = {
            'paciente_id': paciente_id, 'condicao_atual': request.form['condicao_atual'],
            'alergias': request.form['alergias'], 'historico_familiar': request.form['historico_familiar'],
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
    return render_template('ficha_acompanhamento.html', paciente=paciente, exames_anteriores=exames_anteriores)

@app.route('/medico/salvar_ficha_exame/<int:paciente_id>', methods=['POST'])
@login_required
@gestao_required # DECORADOR APLICADO
def salvar_ficha_exame(paciente_id):
    novo_exame = {
        'paciente_id': paciente_id, 'data_exame': request.form.get('data_exame'), 
        'hb_a1c': float(request.form.get('hb_a1c', 0.0)), 'glicose_jejum': int(request.form.get('glicose_jejum', 0)),
        'ldl': int(request.form.get('ldl', 0)), 'triglicerides': int(request.form.get('triglicerides', 0)),
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
@gestao_required 
def gerenciar_agendamentos():
    # 1. APENAS admins veem TUDO
    if current_user.is_admin:
        agendamentos = db_manager.buscar_todos_agendamentos()
    # 2. Médicos e Secretários só veem os DELES
    else:
        # Se for Médico, usa o próprio ID
        if current_user.is_medico:
            medico_id = current_user.id
        # Se for Secretário, usa o ID do Médico Mestre (medico_id do próprio secretário)
        elif current_user.is_secretario and current_user.medico_id:
            medico_id = current_user.medico_id
        else:
            flash('Você não está vinculado a um médico para gerenciar agendamentos.', 'warning')
            return redirect(url_for('dashboard'))

        # Chamada à função de filtro específica
        agendamentos = db_manager.buscar_agendamentos_por_medico(medico_id)

    return render_template('gerenciar_agendamentos.html', agendamentos=agendamentos)



@app.route('/agendar_para_paciente', methods=['GET', 'POST'])
@login_required
@gestao_required # DECORADOR APLICADO
def agendar_para_paciente():
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
# No seu app.py, adicione a rota de cadastro de profissional

@app.route('/cadastrar_profissional', methods=['GET', 'POST'])
@login_required 
@gestao_required # Garante que apenas Admins ou Gestores possam acessar
def cadastrar_profissional():
    # Carrega todos os médicos para a lista de seleção (dropdown)
    # Assumindo que você tem uma função no db_manager para isso.
    medicos = db_manager.carregar_todos_os_usuarios(perfil='medico') 

    if request.method == 'GET':
        # Passa a lista de médicos para o template
        return render_template('cadastro_profissional.html', medicos=medicos)

    if request.method == 'POST':
        # 1. Capture os dados do formulário
        nome_completo = request.form.get('nome_completo')
        email = request.form.get('email')
        senha = request.form.get('senha')
        role = request.form.get('role', 'medico') 
        
        # Novo campo: Captura o ID do Médico Mestre selecionado (usado apenas para Secretário)
        medico_mestre_id = request.form.get('medico_mestre_id') # Recebe o ID como string
        
        # ... (restante da validação) ...

        try:
            hashed_password = generate_password_hash(senha)
            novo_usuario_data = {
                'username': email, 'email': email, 'password_hash': hashed_password,
                'role': role, 'nome_completo': nome_completo,
            }
            
            # 2. LÓGICA CRÍTICA DE VÍNCULO (II.8):
            # Se o papel for 'secretario', adiciona o medico_id para ser salvo
            if role == 'secretario' and medico_mestre_id:
                # O campo medico_id do Secretário é o ID do seu Médico Mestre
                novo_usuario_data['medico_id'] = int(medico_mestre_id)
            
            # Assumindo que salvar_usuario é capaz de receber e salvar o 'medico_id'
            # no dicionário (você precisará adaptar salvar_usuario no db_manager para aceitar 'medico_id').
            if db_manager.salvar_usuario(novo_usuario_data):
                flash(f'Profissional {nome_completo} ({role}) cadastrado com sucesso!', 'success')
                return redirect(url_for('gerenciar_usuarios'))
            else:
                flash('Erro: O e-mail já está em uso ou houve falha no banco de dados.', 'danger')

        except Exception as e:
            app.logger.error(f"Erro ao cadastrar profissional: {e}")
            flash('Erro interno ao cadastrar profissional. Tente novamente.', 'danger')
        
        # Retorna o template em caso de falha no POST, garantindo que os médicos sejam passados novamente
        return render_template('cadastro_profissional.html', medicos=medicos)

if __name__ == '__main__':
    app.run(debug=True)
