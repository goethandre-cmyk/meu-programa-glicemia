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

# --- Inicialização das Classes ---
db_path = os.path.join('data', 'glicemia.json')
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
    
@app.route('/salvar_refeicao', methods=['POST'])
@login_required
def salvar_refeicao():
    data_hora_str = request.form.get('data_hora')
    observacoes = request.form.get('observacoes')
    alimentos_json_str = request.form.get('alimentos')
    tipo_refeicao_especifica = request.form.get('tipo_refeicao_especifica') 

    if not data_hora_str or not alimentos_json_str or not tipo_refeicao_especifica:
        flash('Por favor, preencha todos os campos obrigatórios.', 'danger')
        return redirect(url_for('refeicao'))
    
    try:
        data_hora = datetime.fromisoformat(data_hora_str)
        alimentos_list = json.loads(alimentos_json_str)
        
        total_carbs = sum(item.get('carbs', 0) for item in alimentos_list)
        total_calorias = sum(item.get('kcal', 0) for item in alimentos_list)
        
    except (ValueError, TypeError, json.JSONDecodeError):
        flash('Dados de refeição inválidos.', 'danger')
        return redirect(url_for('refeicao'))

    dados_registro = {
        'user_id': current_user.id,
        'data_hora': data_hora.isoformat(), # <-- CORREÇÃO: Salva como string
        'tipo': 'Refeição', 
        'alimentos_refeicao': alimentos_list,
        'total_carbs': total_carbs,
        'total_calorias': total_calorias,
        'observacoes': observacoes,
        'tipo_refeicao': tipo_refeicao_especifica,
        'valor': None,
        'descricao': None,
        'refeicao': None,
    }
    
    if db_manager.salvar_registro(dados_registro):
        flash(f'Registro de {tipo_refeicao_especifica} salvo com sucesso!', 'success')
        app_core.salvar_log_acao(f'Registro de {tipo_refeicao_especifica} salvo', current_user.username)
    else:
        flash('Erro ao salvar registro de refeição.', 'danger')
        
    return redirect(url_for('registros'))
    
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
            registro['data_hora'] = data_hora.isoformat() # <-- CORREÇÃO: Salva como string
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
            alimentos_json_str = request.form.get('alimentos')
            tipo_refeicao_especifica = request.form.get('tipo_refeicao_especifica')
            
            if not data_hora_str or not alimentos_json_str or not tipo_refeicao_especifica:
                flash('Por favor, preencha todos os campos obrigatórios.', 'danger')
                return redirect(url_for('editar_registo', id=id))
            
            try:
                data_hora = datetime.fromisoformat(data_hora_str)
                alimentos_list = json.loads(alimentos_json_str)
                
                total_carbs = sum(item.get('carbs', 0) for item in alimentos_list)
                total_calorias = sum(item.get('kcal', 0) for item in alimentos_list)
                
            except (ValueError, TypeError, json.JSONDecodeError) as e:
                flash(f'Dados de refeição inválidos: {e}', 'danger')
                return redirect(url_for('editar_registo', id=id))

            registro['data_hora'] = data_hora.isoformat() # <-- CORREÇÃO: Salva como string
            registro['observacoes'] = observacoes
            registro['alimentos_refeicao'] = alimentos_list
            registro['total_carbs'] = total_carbs
            registro['total_calorias'] = total_calorias
            registro['tipo_refeicao'] = tipo_refeicao_especifica
            
            if db_manager.atualizar_registro(registro):
                flash('Registro de refeição atualizado com sucesso!', 'success')
                app_core.salvar_log_acao(f'Registro de refeição {id} atualizado', current_user.username)
            else:
                flash('Erro ao atualizar registro de refeição.', 'danger')
            return redirect(url_for('registros'))

    else: # Lógica para carregar o formulário (GET)
        if registro.get('tipo') == 'Glicemia':
            # --- CORREÇÃO: Converte a string de data para um objeto datetime para exibir no formulário ---
            if 'data_hora' in registro and isinstance(registro['data_hora'], str):
                try:
                    registro['data_hora'] = datetime.fromisoformat(registro['data_hora'])
                except ValueError:
                    pass
            # --- Fim da correção ---
            return render_template('editar_glicemia.html', registro=registro)
        elif registro.get('tipo') == 'Refeição':
            # --- CORREÇÃO: Converte a string de data para um objeto datetime para exibir no formulário ---
            if 'data_hora' in registro and isinstance(registro['data_hora'], str):
                try:
                    registro['data_hora'] = datetime.fromisoformat(registro['data_hora'])
                except ValueError:
                    pass
            # --- Fim da correção ---
            alimentos = db_manager.carregar_alimentos()
            return render_template(
                'editar_refeicao.html',
                registro=registro,
                alimentos_disponiveis=alimentos,
                tipos_refeicao=app_core.obter_tipos_refeicao(),
            )
            
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

@app.route('/editar_alimento/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_alimento(id):
    alimento = db_manager.encontrar_alimento(id)
    if not alimento:
        flash('Alimento não encontrado.', 'danger')
        return redirect(url_for('alimentos'))

    if request.method == 'POST':
        nome = request.form.get('nome')
        medida_caseira = request.form.get('medida_caseira')
        peso_g = request.form.get('peso_g')
        kcal = request.form.get('kcal')
        carbs_100g = request.form.get('carbs_100g')
        
        try:
            peso_g = float(peso_g.replace(',', '.')) if peso_g else None
            kcal = float(kcal.replace(',', '.')) if kcal else None
            carbs_100g = float(carbs_100g.replace(',', '.')) if carbs_100g else None
        except (ValueError, TypeError):
            flash('Valores inválidos para peso, Kcal ou Carboidratos.', 'danger')
            return redirect(url_for('editar_alimento', id=id))
            
        alimento_atualizado = {
            'id': id,
            'nome': nome,
            'medida_caseira': medida_caseira,
            'peso_g': peso_g,
            'kcal': kcal,
            'carbs_100g': carbs_100g
        }
        
        if db_manager.atualizar_alimento(alimento_atualizado):
            flash('Alimento atualizado com sucesso!', 'success')
            return redirect(url_for('alimentos'))
        else:
            flash('Erro ao atualizar o alimento.', 'danger')
            return redirect(url_for('editar_alimento', id=id))

    return render_template('editar_alimento.html', alimento=alimento)

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

    return render_template('registrar_alimento.html')

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
def agendamentos():
    if current_user.is_medico or current_user.is_admin:
        agendamentos = db_manager.carregar_agendamentos_medico(current_user.id)
    else:
        agendamentos = db_manager.carregar_agendamentos_paciente(current_user.id)
    
    return render_template('agendamentos.html', agendamentos=agendamentos)

# No seu arquivo app.py

# No seu arquivo app.py

@app.route('/agendar', methods=['GET', 'POST'])
@login_required
def agendar():
    if request.method == 'POST':
        # Esta parte é para a lógica de salvar o agendamento
        try:
            paciente_id_str = request.form.get('paciente_id')
            medico_id_str = request.form.get('medico_id')
            data_hora_str = request.form.get('data_hora')
            observacoes = request.form.get('observacoes')

            # Validação dos dados antes da conversão
            if not medico_id_str or not data_hora_str:
                flash('Por favor, preencha todos os campos obrigatórios.', 'danger')
                return redirect(url_for('agendamentos'))

            # Se o campo paciente_id não for preenchido, usa o ID do usuário atual
            if not paciente_id_str:
                paciente_id = current_user.id
            else:
                paciente_id = int(paciente_id_str)

            medico_id = int(medico_id_str)
            data_hora = datetime.fromisoformat(data_hora_str)
            
            dados_agendamento = {
                'paciente_id': paciente_id,
                'medico_id': medico_id,
                'data_hora': data_hora.isoformat(),
                'observacoes': observacoes
            }
            
            if db_manager.salvar_agendamento(dados_agendamento):
                flash('Agendamento salvo com sucesso!', 'success')
            else:
                flash('Erro ao salvar agendamento.', 'danger')

        except (ValueError, TypeError) as e:
            # Captura erros de formato de dados, mas não a ausência
            flash('Dados do agendamento inválidos. Verifique o formato da data e hora.', 'danger')

        return redirect(url_for('agendamentos'))

    else: # request.method == 'GET'
        medicos = db_manager.carregar_medicos()
        
        if current_user.is_paciente:
            return render_template('agendar.html', medicos=medicos)
        
        else:
            pacientes = db_manager.carregar_todos_os_usuarios()
            return render_template('agendar_consulta_admin.html', medicos=medicos, pacientes=pacientes)
        
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