from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import json
import logging
import plotly.graph_objects as go
import numpy as np
import os
from database_manager import DatabaseManager

# --- Configuração da Aplicação ---
app = Flask(__name__)
app.secret_key = 'sua_chave_secreta_aqui' 
app.logger.setLevel(logging.INFO)

# Adicione a função ao ambiente Jinja2
app.jinja_env.globals['from_json'] = json.loads

# Adicione o resto do seu código, como a função de filtro
def from_json_filter(json_string):
    if json_string:
        try:
            return json.loads(json_string)
        except (json.JSONDecodeError, TypeError):
            return []
    return []

# Em seguida, adicione a função como um filtro
app.jinja_env.filters['from_json'] = from_json_filter

# --- Inicialização das Classes ---
db_path = os.path.join('data', 'glicemia.db')
db_manager = DatabaseManager()
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Funções de ajuda para os templates (AppCore) - renomeada para evitar conflito
class AppCore:
    def __init__(self, db_manager):
        self.db_manager = db_manager

    def salvar_log_acao(self, acao, usuario):
        self.db_manager.salvar_log_acao(acao, usuario)

    def obter_tipos_refeicao(self):
        return ['Jejum', 'Lanche', 'Almoço', 'Janta']
    
    def encontrar_registro(self, registro_id):
        return self.db_manager.encontrar_registro(registro_id)

    def excluir_registro(self, registro_id):
        return self.db_manager.excluir_registro(registro_id)

    def carregar_dados_analise(self, user_id):
        # Implementação da função de análise
        pass

# --- Classes de Suporte ---
class User(UserMixin):
    # Adicionamos mais campos para que o objeto User tenha todos os dados do banco de dados
    def __init__(self, id, username, password_hash, role='user', email=None, razao_ic=1.0, fator_sensibilidade=1.0, data_nascimento=None, sexo=None):
        self.id = id
        self.username = username
        self.password_hash = password_hash
        self.role = role
        self.email = email
        self.razao_ic = razao_ic
        self.fator_sensibilidade = fator_sensibilidade
        self.data_nascimento = data_nascimento
        self.sexo = sexo
    @property
    def is_medico(self):
        return self.role == 'medico'

    @property
    def is_admin(self):
        return self.role == 'admin'

    @property
    def is_paciente(self):
        return self.role == 'user'

    # Adicione a nova propriedade is_cuidador aqui
    @property
    def is_cuidador(self):
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
                role=user_data.get('role'),
                email=user_data.get('email'),
                razao_ic=user_data.get('razao_ic', 1.0),
                fator_sensibilidade=user_data.get('fator_sensibilidade', 1.0),
                data_nascimento=user_data.get('data_nascimento'),
                sexo=user_data.get('sexo')
            )
    return None

def get_status_class(valor_glicemia):
    """Retorna uma classe CSS baseada no valor da glicemia."""
    # A API retorna o valor como string, então é bom convertê-lo para float
    try:
        valor = float(valor_glicemia)
    except (ValueError, TypeError):
        return 'bg-secondary' # Retorna uma cor neutra se o valor for inválido

    # Valores de referência para glicemia (em mg/dL)
    if valor < 70:
        return 'bg-danger'  # Vermelho para hipoglicemia
    elif 70 <= valor <= 130:
        return 'bg-success' # Verde para normal
    elif 130 < valor <= 180:
        return 'bg-warning' # Amarelo para pré-hiper
    else:
        return 'bg-danger' # Vermelho para hiperglicemia
    
# --- ROTAS DA APLICAÇÃO ---
# Rota Home
@app.route('/')
def home():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

# Rota de Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user_data = db_manager.carregar_usuario(username)
        
        # Adiciona verificação de depuração para o hash da senha
        if user_data:
            print(f"Tentativa de login para o usuário: {username}")
            print(f"Hash no banco de dados: {user_data.get('password_hash')}")
            print(f"Senha do formulário: {password}")
        
        if user_data and check_password_hash(user_data['password_hash'], password):
            user = User(
                id=user_data.get('id'),
                username=user_data.get('username'),
                password_hash=user_data.get('password_hash'),
                role=user_data.get('role'),
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
    return render_template('login.html')

# Rota de Logout
@app.route('/logout')
@login_required
def logout():
    app_core.salvar_log_acao(f'Logout', current_user.username)
    logout_user()
    flash('Você foi desconectado.', 'info')
    return redirect(url_for('login'))

# Rota de Cadastro
@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        password_confirm = request.form['password_confirm'] # <--- Adicionado

        # Validação de nome de usuário e senha
        if len(username) < 3 or len(password) < 6:
            flash('Nome de usuário deve ter no mínimo 3 caracteres e senha no mínimo 6.', 'danger')
            return render_template('cadastro.html')

        # <--- Adicionado: Validação para a confirmação de senha
        if password != password_confirm:
            flash('A senha e a confirmação de senha não coincidem.', 'danger')
            return render_template('cadastro.html')
        
        # Garante que o hash é gerado corretamente...
        hashed_password = generate_password_hash(password)
        
        novo_usuario = {
            'username': username,
            'password_hash': hashed_password,
            'role': 'user',
            'razao_ic': 1.0,
            'fator_sensibilidade': 1.0,
            'email': request.form.get('email'),
            'data_nascimento': request.form.get('data_nascimento'),
            'sexo': request.form.get('sexo')
        }
        
        if db_manager.salvar_usuario(novo_usuario):
            flash('Cadastro realizado com sucesso!', 'success')
            app.logger.info(f'Novo usuário cadastrado: {username}')
            return redirect(url_for('login'))
        else:
            flash('Nome de usuário já existe.', 'danger')
            return redirect(url_for('cadastro'))
            
    return render_template('cadastro.html')

# Rota do Dashboard
@app.route('/dashboard')
@login_required
def dashboard():
    # Simplifica a lógica de redirecionamento para o dashboard correto
    if current_user.is_medico or current_user.is_admin:
        return redirect(url_for('dashboard_medico'))
    else: # Por padrão, qualquer outro usuário vai para o dashboard do paciente
        registros = db_manager.carregar_registros(current_user.id)
        
        ultimo_registro = None
        if registros:
            registros_glicemia = [r for r in registros if r.get('tipo') == 'Glicemia']
            if registros_glicemia:
                registros_glicemia.sort(key=lambda x: x.get('data_hora'), reverse=True)
                ultimo_registro = registros_glicemia[0]
                
                # --- LÓGICA DE TRATAMENTO DE ERRO ADICIONADA AQUI ---
                # Garante que 'data_hora' seja uma string antes de tentar a conversão.
                data_hora_str = ultimo_registro.get('data_hora')
                if data_hora_str and isinstance(data_hora_str, str):
                    try:
                        ultimo_registro['data_hora'] = datetime.fromisoformat(data_hora_str)
                    except ValueError:
                        # Se a string não estiver no formato ISO 8601,
                        # defina o valor como None ou outra representação
                        ultimo_registro['data_hora'] = None
                else:
                    # Se não for uma string válida, defina como None para evitar o erro
                    ultimo_registro['data_hora'] = None
                # --- FIM DA LÓGICA DE TRATAMENTO DE ERRO ---

        resumo_dados = {
            'ultimo_registro': ultimo_registro,
        }
        
        return render_template('dashboard_paciente.html', resumo_dados=resumo_dados)

@app.route('/gerenciar_usuarios')
@login_required
def gerenciar_usuarios():
    # Verifica se o usuário tem permissão de administrador ou secretário
    if not (current_user.is_admin or current_user.role == 'secretario'):
        flash('Acesso não autorizado.', 'danger')
        return redirect(url_for('dashboard'))

    # Lógica para carregar todos os usuários do banco de dados
    usuarios = db_manager.carregar_todos_os_usuarios()
    
    return render_template('gerenciar_usuarios.html', usuarios=usuarios)

# Rota para editar um usuário existente
@app.route('/editar_usuario/<username>', methods=['GET', 'POST'])
@login_required
def editar_usuario(username):
    # Verificação de permissão (apenas admins podem editar)
    if not current_user.is_admin:
        flash('Acesso não autorizado.', 'danger')
        return redirect(url_for('dashboard'))

    # Carrega o usuário do banco de dados
    usuario = db_manager.carregar_usuario(username)
    if not usuario:
        flash('Usuário não encontrado.', 'danger')
        return redirect(url_for('gerenciar_usuarios'))

    # Carrega a lista de médicos para o dropdown no formulário
    medicos = db_manager.carregar_medicos()

    # Processa o formulário enviado
    if request.method == 'POST':
        # --- Lógica para vincular o paciente ao médico ---
        # Se o usuário editado for um paciente, processa a vinculação
        if usuario.get('role') == 'paciente':
            medico_id_selecionado = request.form.get('medico_vinculado')
            if medico_id_selecionado:
                # Chama o novo método para fazer a vinculação
                db_manager.vincular_paciente_medico(usuario['id'], int(medico_id_selecionado))
        
        # Coletar dados do formulário de forma segura
        nome_completo = request.form.get('nome_completo')
        role = request.form.get('role')
        email = request.form.get('email')
        nova_senha = request.form.get('senha')
        confirmar_senha = request.form.get('confirmar_senha')
        data_nascimento = request.form.get('data_nascimento')
        sexo = request.form.get('sexo')
        
        # Validações de senha
        if nova_senha:
            if nova_senha != confirmar_senha:
                flash('A senha e a confirmação de senha não coincidem.', 'danger')
                return render_template('editar_usuario.html', usuario=usuario, medicos=medicos)
            
            usuario['password_hash'] = generate_password_hash(nova_senha)

        # Atualiza os outros campos do usuário
        usuario['nome_completo'] = nome_completo
        usuario['role'] = role
        usuario['email'] = email
        usuario['data_nascimento'] = data_nascimento
        usuario['sexo'] = sexo
        
        # Atualiza dados numéricos
        usuario['razao_ic'] = float(request.form.get('razao_ic', 0.0))
        usuario['fator_sensibilidade'] = float(request.form.get('fator_sensibilidade', 0.0))
        usuario['meta_glicemia'] = float(request.form.get('meta_glicemia', 0.0))
        
        # Salva as alterações no banco de dados
        if db_manager.atualizar_usuario(usuario):
            flash('Usuário atualizado com sucesso!', 'success')
            return redirect(url_for('gerenciar_usuarios'))
        else:
            flash('Erro ao atualizar usuário.', 'danger')

    # Renderiza o formulário de edição, passando a lista de médicos
    return render_template('editar_usuario.html', usuario=usuario, medicos=medicos)

# Rota para excluir um usuário
@app.route('/excluir_usuario/<username>', methods=['POST'])
@login_required
def excluir_usuario(username):
    # Verificação de permissão: apenas administradores podem excluir usuários
    if not current_user.is_admin:
        flash('Acesso não autorizado.', 'danger')
        return redirect(url_for('dashboard'))

    # Verifica se o usuário tentando excluir não é o próprio
    if current_user.username == username:
        flash('Você não pode excluir a sua própria conta.', 'danger')
        return redirect(url_for('gerenciar_usuarios'))

    # Tenta excluir o usuário do banco de dados
    if db_manager.excluir_usuario(username):
        flash(f'Usuário {username} excluído com sucesso!', 'success')
    else:
        flash(f'Erro ao excluir o usuário {username}.', 'danger')

    return redirect(url_for('gerenciar_usuarios'))

# Rotas do Paciente (sem alterações, exceto o import jsonify)
@app.route('/registros')
@login_required
def registros():
    registros_list = db_manager.carregar_registros(current_user.id)
    
    registros_formatados = []
    for registro in registros_list:
        tipo = registro.get('tipo')
        if tipo == 'Refeição':
            tipo_exibicao = registro.get('tipo_refeicao', 'Refeição') 
        else:
            tipo_exibicao = tipo
        
        # --- CORREÇÃO: Conversão de data de string para datetime para exibição ---
        data_hora_str = registro.get('data_hora')
        if data_hora_str and isinstance(data_hora_str, str):
            try:
                registro['data_hora'] = datetime.fromisoformat(data_hora_str)
            except ValueError:
                pass 
        # --- Fim da correção ---

        registro['tipo_exibicao'] = tipo_exibicao
        registros_formatados.append(registro)
    
    return render_template(
        'registros.html',
        registros=registros_formatados,
        current_user=current_user,
        get_status_class=get_status_class 
    )
    
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

@app.route('/registrar_glicemia', methods=['GET'])
@login_required
def registrar_glicemia():
    """Renderiza o formulário para registro de glicemia."""
    return render_template('registrar_glicemia.html') 
 
@app.route('/salvar_glicemia', methods=['POST'])
@login_required
def salvar_glicemia():
    valor_glicemia = request.form.get('valor')
    data_hora_str = request.form.get('data_hora')
    observacoes = request.form.get('observacoes')

    if not valor_glicemia or not data_hora_str:
        flash('Por favor, preencha todos os campos obrigatórios.', 'danger')
        return redirect(url_for('registros'))
    
    try:
        # Converte para datetime para validação, mas não para salvar
        data_hora = datetime.fromisoformat(data_hora_str)
        valor_glicemia = float(valor_glicemia.replace(',', '.'))
    except (ValueError, TypeError):
        flash('Valores inválidos para glicemia ou data/hora.', 'danger')
        return redirect(url_for('registros'))

    dados_registro = {
        'user_id': current_user.id,
        'data_hora': data_hora.isoformat(), # <-- CORREÇÃO: Salva como string
        'tipo': 'Glicemia',
        'valor': valor_glicemia,
        'observacoes': observacoes,
        'total_carbs': None,
        'total_calorias': None,
        'alimentos_refeicao': None,
        'tipo_refeicao': None,
    }
    
    if db_manager.salvar_registro(dados_registro):
        flash('Registro de glicemia salvo com sucesso!', 'success')
        app_core.salvar_log_acao(f'Registro de glicemia salvo: {valor_glicemia}', current_user.username)
    else:
        flash('Erro ao salvar registro de glicemia.', 'danger')
        
    return redirect(url_for('registros'))
    
@app.route('/registrar_refeicao', methods=['GET', 'POST'])
@login_required
def registrar_refeicao():
    if request.method == 'POST':
        try:
            # 1. Obter os dados do formulário
            data_hora_str = request.form['data_hora']
            tipo = request.form['tipo']
            observacoes = request.form.get('observacoes')
            
            # Os totais são enviados diretamente do JavaScript
            total_carbs = float(request.form['total_carbs'])
            total_kcal = float(request.form['total_kcal'])
            
            # O JavaScript enviou a lista de alimentos selecionados como uma string JSON
            alimentos_selecionados_json = request.form['alimentos_selecionados']
            
            # 2. Descodificar a string JSON de volta para uma lista Python
            alimentos_selecionados = json.loads(alimentos_selecionados_json)
            
            # 3. Criar um dicionário com todos os dados
            registro_data = {
                'user_id': current_user.id,
                'data_hora': data_hora_str,
                'tipo': tipo,
                'valor': None, # `valor` pode ser None para refeições
                'observacoes': observacoes,
                'alimentos_json': alimentos_selecionados_json, # Salve a string JSON
                'total_calorias': total_kcal,
                'total_carbs': total_carbs
            }
            
            # 4. Chamar a função `salvar_registro` passando APENAS o dicionário
            db_manager.salvar_registro(registro_data)
            
            flash('Refeição registrada com sucesso!', 'success')
            return redirect(url_for('dashboard'))

        except Exception as e:
            flash(f'Erro ao registrar a refeição: {e}', 'danger')
            return redirect(url_for('registrar_refeicao'))

    # Se a requisição for GET, carrega a lista de alimentos para o template
    alimentos = db_manager.carregar_alimentos()
    
    # Define a data e hora atuais para o campo do formulário
    now = datetime.now().strftime('%Y-%m-%dT%H:%M')
    
    return render_template('registrar_refeicao.html', alimentos=alimentos, now=now)
    
@app.route('/excluir_registo/<int:id>', methods=['POST'])
@login_required
def excluir_registo(id):
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
    
@app.route('/alimentos')
@login_required
def alimentos():
    lista_alimentos = db_manager.carregar_alimentos()
    return render_template('alimentos.html', alimentos=lista_alimentos)

@app.route('/buscar_alimentos', methods=['GET'])
def buscar_alimentos():
    query = request.args.get('query', '')
    if query:
        resultados = app_core.buscar_alimentos_por_nome(query)
        return jsonify(resultados)
    return jsonify([])

@app.route('/editar_registo/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_registo(id):
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

        elif registro.get('tipo') in ['Jejum', 'Café da Manhã', 'Almoço', 'Janta', 'Lanche', 'Colação']:
            data_hora_str = request.form.get('data_hora')
            observacoes = request.form.get('observacoes')
            
            # CORREÇÃO: Pega o JSON e o tipo de refeição do formulário
            alimentos_json_str = request.form.get('alimentos_selecionados') 
            tipo_refeicao_especifica = request.form.get('tipo')
            
            if not data_hora_str or not alimentos_json_str:
                flash('Por favor, preencha todos os campos obrigatórios.', 'danger')
                return redirect(url_for('editar_registo', id=id))
            
            try:
                data_hora = datetime.fromisoformat(data_hora_str)
                alimentos_list = json.loads(alimentos_json_str)
                
                # CORREÇÃO: Use as chaves corretas do JSON enviado pelo frontend
                total_carbs = sum(item.get('CHO (g)', 0) for item in alimentos_list)
                total_calorias = sum(item.get('KCAL', 0) for item in alimentos_list)
                
            except (ValueError, TypeError, json.JSONDecodeError) as e:
                flash(f'Dados de refeição inválidos: {e}', 'danger')
                return redirect(url_for('editar_registo', id=id))

            registro['data_hora'] = data_hora.isoformat()
            registro['observacoes'] = observacoes
            registro['alimentos_json'] = alimentos_json_str
            registro['total_carbs'] = total_carbs
            registro['total_calorias'] = total_calorias
            registro['tipo'] = tipo_refeicao_especifica
            
            if db_manager.atualizar_registro(registro):
                flash('Registro de refeição atualizado com sucesso!', 'success')
                app_core.salvar_log_acao(f'Registro de refeição {id} atualizado', current_user.username)
            else:
                flash('Erro ao atualizar registro de refeição.', 'danger')
            return redirect(url_for('registros'))
        
        else:
            flash('Tipo de registro inválido.', 'danger')
            return redirect(url_for('registros'))

    # Lógica para carregar o formulário (GET)
    else: 
        if registro.get('tipo') == 'Glicemia':
            if 'data_hora' in registro and isinstance(registro['data_hora'], str):
                try:
                    registro['data_hora'] = datetime.fromisoformat(registro['data_hora'])
                except ValueError:
                    pass
            return render_template('editar_glicemia.html', registro=registro)
        
        elif registro.get('tipo') in ['Jejum', 'Café da Manhã', 'Almoço', 'Janta', 'Lanche', 'Colação']:
            if 'data_hora' in registro and isinstance(registro['data_hora'], str):
                try:
                    registro['data_hora'] = datetime.fromisoformat(registro['data_hora'])
                except ValueError:
                    pass
            
            if 'alimentos_json' in registro and registro['alimentos_json']:
                registro['alimentos_list'] = json.loads(registro['alimentos_json'])
            else:
                registro['alimentos_list'] = []
            
            alimentos = db_manager.carregar_alimentos()
            return render_template(
                'editar_refeicao.html',
                registro=registro,
                alimentos_disponiveis=alimentos,
                tipos_refeicao=['Jejum', 'Café da Manhã', 'Almoço', 'Janta', 'Lanche', 'Colação'],
            )
        
        else:
            flash('Tipo de registro inválido.', 'danger')
            return redirect(url_for('registros'))

@app.route('/excluir_alimento/<int:id>', methods=['POST'])
@login_required
def excluir_alimento(id):
    sucesso = db_manager.excluir_alimento(id)
    if sucesso:
        flash('Alimento excluído com sucesso!', 'success')
    else:
        flash('Erro ao excluir o alimento.', 'danger')
    return redirect(url_for('alimentos'))

@app.route('/registrar_alimento', methods=['GET', 'POST'])
@login_required
def registrar_alimento():
    if not (current_user.role in ['secretario', 'admin']):
        flash('Acesso não autorizado.', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        try:
            # Captura os dados do formulário HTML
            nome_alimento = request.form['nome_alimento']
            medida_caseira = request.form['medida_caseira']
            peso_g = float(request.form['peso_g'].replace(',', '.'))
            kcal = float(request.form['kcal'].replace(',', '.'))
            cho = float(request.form['cho'].replace(',', '.'))
            
            # Mapeia os dados do formulário para o formato da sua tabela 'alimentos'
            novo_alimento = {
                'alimento': nome_alimento, # 'alimento' é o nome da coluna no BD
                'medida_caseira': medida_caseira,
                'peso': peso_g, # 'peso' é o nome da coluna no BD
                'kcal': kcal,
                'carbs': cho # 'carbs' é o nome da coluna no BD
            }
            
            # Chama o método de salvar_alimento (que vamos criar)
            if db_manager.salvar_alimento(novo_alimento):
                flash('Alimento adicionado com sucesso!', 'success')
            else:
                flash('Erro ao adicionar o alimento.', 'danger')
        except (ValueError, TypeError):
            flash('Dados do alimento inválidos. Por favor, verifique os valores numéricos.', 'danger')
        
        # Redireciona para a página de listagem de alimentos
        return redirect(url_for('alimentos'))

    # Se a requisição for GET, carrega a lista de alimentos
    alimentos = db_manager.carregar_alimentos()
    return render_template('registrar_alimento.html', alimentos=alimentos)

@app.route('/adicionar_alimento', methods=['GET', 'POST'])
@login_required
def adicionar_alimento():
    if request.method == 'POST':
        try:
            nome = request.form['nome']
            medida_caseira = request.form['medida_caseira']
            peso_g = float(request.form['peso_g'].replace(',', '.'))
            kcal = float(request.form['kcal'].replace(',', '.'))
            carbs_100g = float(request.form['carbs_100g'].replace(',', '.'))
            
            novo_alimento = {
                'nome': nome,
                'medida_caseira': medida_caseira,
                'peso_g': peso_g,
                'kcal': kcal,
                'carbs_100g': carbs_100g
            }
            
            if db_manager.salvar_alimento(novo_alimento):
                flash('Alimento adicionado com sucesso!', 'success')
            else:
                flash('Erro ao adicionar o alimento.', 'danger')
        except (ValueError, TypeError):
            flash('Dados do alimento inválidos. Por favor, verifique os valores numéricos.', 'danger')
        
        return redirect(url_for('alimentos'))

    return render_template('adicionar_alimento.html')

# ---- ROTAS DA ÁREA MÉDICA ----

# Rota do Dashboard Médico
@app.route('/dashboard_medico')
@login_required
def dashboard_medico():
    if not current_user.is_medico and not current_user.is_admin:
        flash('Acesso não autorizado.', 'danger')
        return redirect(url_for('dashboard'))
    
    # Lógica para o dashboard médico (ex: listar pacientes)
    pacientes = db_manager.obter_pacientes_por_medico(current_user.id)
    
    # 1. Crie o dicionário resumo_dados aqui
    resumo_dados = {
        'total_pacientes': len(pacientes) if pacientes else 0,
        # Você pode adicionar outros dados de resumo aqui se precisar
    }
    
    # 2. Passe as duas variáveis para o template
    return render_template('dashboard_medico.html', pacientes=pacientes, resumo_dados=resumo_dados)

# Rota do Relatório Medico
@app.route('/relatorio_medico')
@login_required
def relatorio_medico():
    # Verifica se o usuário tem permissão de acesso
    if not (current_user.is_medico or current_user.is_admin):
        # Opcional: redireciona para a página de dashboard do paciente ou para uma página de erro
        return redirect(url_for('dashboard_paciente'))
    
    # Adicione a lógica para buscar os dados de relatório específicos para médicos aqui
    # Por exemplo: pacientes = db_manager.carregar_todos_os_pacientes()
    
    return render_template('relatorio_medico.html')

# Rota de Vinculo Cuidador/Paciente
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

# No seu arquivo app.py

@app.route('/vincular_cuidador/<username>')
@login_required
def vincular_cuidador(username):
    """
    Exibe o formulário para vincular um cuidador a um paciente.
    Apenas acessível a administradores.
    """
    # 1. Verificação de permissão
    if not current_user.is_admin:
        flash('Acesso não autorizado.', 'danger')
        return redirect(url_for('dashboard'))

    # 2. Carregar o paciente
    paciente = db_manager.carregar_usuario(username)
    if not paciente:
        flash('Paciente não encontrado.', 'danger')
        return redirect(url_for('gerenciar_usuarios'))

    # 3. Carregar a lista de cuidadores
    cuidadores = db_manager.carregar_cuidadores()
    
    # 4. Renderizar o template
    return render_template('vincular_cuidador.html', paciente=paciente, cuidadores=cuidadores)

@app.route('/paciente/<int:paciente_id>')
@login_required
def perfil_paciente(paciente_id):
    if not current_user.is_medico and not current_user.is_admin:
        flash('Acesso não autorizado.', 'danger')
        return redirect(url_for('dashboard'))
        
    # Verificar se o médico tem acesso a este paciente
    if not db_manager.medico_tem_acesso_a_paciente(current_user.id, paciente_id) and not current_user.is_admin:
        flash('Acesso não autorizado a este paciente.', 'danger')
        return redirect(url_for('dashboard_medico'))
    
    paciente = db_manager.carregar_usuario_por_id(paciente_id)
    registros = db_manager.carregar_registros(paciente_id)
    ficha_medica = db_manager.carregar_ficha_medica(paciente_id)
    
    return render_template('perfil_paciente.html', paciente=paciente, registros_glicemia=registros, ficha_medica=ficha_medica)

@app.route('/salvar_ficha_medica', methods=['POST'])
@login_required
def salvar_ficha_medica():
    # Apenas médicos e administradores podem salvar fichas médicas
    if not (current_user.is_medico or current_user.is_admin):
        flash('Acesso não autorizado.', 'danger')
        return redirect(url_for('dashboard'))

    try:
        # Pega os dados do formulário
        paciente_id = int(request.form['paciente_id'])
        paciente_username = request.form['paciente_username']
        
        # Cria um dicionário com os dados da ficha médica
        ficha_data = {
            'paciente_id': paciente_id,
            'condicao_atual': request.form['condicao_atual'],
            'alergias': request.form['alergias'],
            'historico_familiar': request.form['historico_familiar'],
            'medicamentos_uso': request.form['medicamentos_uso']
        }
        
        # Chama o método da base de dados para salvar a ficha
        if db_manager.salvar_ficha_medica(ficha_data):
            flash('Ficha médica salva com sucesso!', 'success')
        else:
            flash('Erro ao salvar a ficha médica.', 'danger')

        return redirect(url_for('perfil_paciente', username=paciente_username))

    except Exception as e:
        flash(f'Ocorreu um erro: {e}', 'danger')
        return redirect(url_for('dashboard'))
    
@app.route('/agendamentos')
@login_required
def agendamentos_redirect():
    return redirect(url_for('gerenciar_agendamentos'))

# /////// AGENDA DO PACIENTE ///////
@app.route('/minhas_consultas')
@login_required
def minhas_consultas():
    # Apenas pacientes podem acessar esta rota
    if not current_user.is_paciente:
        flash('Acesso não autorizado. Esta página é para pacientes.', 'danger')
        return redirect(url_for('dashboard'))

    agendamentos = db_manager.buscar_agendamentos_paciente(current_user.id)
    return render_template('minhas_consultas.html', agendamentos=agendamentos)

@app.route('/atualizar_status_paciente/<int:id>', methods=['POST'])
@login_required
def atualizar_status_paciente(id):
    # Lógica de atualização de status para um paciente
    # Apenas pacientes podem usar esta rota para atualizar o status de suas próprias consultas
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
    # Verifica se o usuário logado tem permissão (médico, secretário ou admin)
    if not current_user.is_medico and not current_user.is_admin:
        flash('Acesso não autorizado.', 'danger')
        return redirect(url_for('dashboard'))

    agendamentos = db_manager.buscar_todos_agendamentos()
    return render_template('gerenciar_agendamentos.html', agendamentos=agendamentos)

@app.route('/agendar_para_paciente', methods=['GET', 'POST'])
@login_required
def agendar_para_paciente():
    # Lógica para garantir que apenas médicos e administradores podem acessar
    if not current_user.is_medico and not current_user.is_admin:
        flash('Acesso não autorizado.', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        try:
            paciente_username = request.form['paciente_username']
            medico_username = request.form['medico_username']
            data_hora = request.form['data_hora']
            observacoes = request.form.get('observacoes', '')

            # Busque os IDs dos usuários pelos usernames
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

    # Para requisição GET, carrega a lista de pacientes e médicos para o template
    pacientes = db_manager.carregar_todos_os_usuarios('paciente')
    medicos = db_manager.carregar_todos_os_usuarios('medico')
    
    return render_template('agendar_para_paciente.html', pacientes=pacientes, medicos=medicos)

@app.route('/agendar_consulta', methods=['GET', 'POST'])
@login_required
def agendar_consulta():
    if request.method == 'POST':
        # Aqui a lógica de agendamento é mais simples, pois o paciente
        # está agendando para si mesmo.
        medico_id = request.form.get('medico_id')
        data_hora = request.form.get('data_agendamento')
        observacoes = request.form.get('observacoes')
        paciente_id = current_user.id # O ID do paciente é o ID do usuário logado

        if db_manager.salvar_agendamento(paciente_id, medico_id, data_hora, observacoes):
            flash('Consulta agendada com sucesso!', 'success')
            return redirect(url_for('minhas_consultas'))
        else:
            flash('Erro ao agendar consulta. Tente novamente.', 'danger')
            return redirect(url_for('agendar_consulta'))

    # Para requisição GET, carrega a lista de médicos
    medicos = db_manager.carregar_todos_os_usuarios(perfil='medico')
    return render_template('agendar_consulta.html', medicos=medicos)

@app.route('/calcular_fs')
@login_required
def calcular_fs():
    return render_template('calcular_fs.html')

@app.route('/guia_insulina')
@login_required
def guia_insulina():
    return render_template('guia_insulina.html')

# Rota para a lista de pacientes de um médico
@app.route('/pacientes')
@login_required
def pacientes():
    # Verifica se o usuário logado é um médico
    if not current_user.is_medico:
        flash('Acesso não autorizado. Esta página é exclusiva para médicos.', 'danger')
        return redirect(url_for('dashboard'))

    # Usa o método corrigido para obter os pacientes vinculados ao médico atual
    pacientes = db_manager.obter_pacientes_por_medico(current_user.id)

    # Renderiza o template, passando a lista de pacientes
    return render_template('pacientes.html', pacientes=pacientes)

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
        
    # Carrega a ficha médica existente ou cria uma vazia se não existir
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
        return redirect(url_for('ficha_medica', paciente_id=paciente_id))

    return render_template('ficha_medica.html', paciente=paciente, ficha=ficha_medica_data)

# ---- FIM DAS ROTAS DA ÁREA MÉDICA ----

if __name__ == '__main__':
    app.run(debug=True)