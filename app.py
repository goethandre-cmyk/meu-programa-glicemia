# app.py

# --- Importações e Configuração Inicial ---
import os
import json
from functools import wraps
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    jsonify,
    flash
)
import sqlite3
from datetime import datetime
import bcrypt

# Importa as classes e funções utilitárias do seu módulo logica.py
from logica import (
    DatabaseManager,
    AuthManager,
    AppCore,
    get_cor_glicemia,
    get_cor_classificacao,
    calcular_fator_sensibilidade,
    calcular_bolus_detalhado,
    _processar_dados_registro,
    get_status_class
)

app = Flask(__name__)
app.secret_key = '0edd34d5d0228451a8b702f7902892c5'

# Instâncias globais das classes de lógica.
# Corrigido: Agora criamos duas instâncias, uma para cada banco de dados
db_manager_glicemia = DatabaseManager(db_path='glicemia.db')
db_manager_usuarios = DatabaseManager(db_path='banco_de_dados.db')

# Corrigido: As classes de lógica são inicializadas com a instância do banco de dados correta
auth_manager = AuthManager(db_manager_usuarios)
app_core = AppCore(db_manager_glicemia)


# --- Funções Decoradoras (Middleware) ---
def login_required(f):
    """Decorador para rotas que exigem autenticação."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash("Por favor, faça login para aceder a esta página.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def roles_required(roles_list):
    """Decorador para rotas que exigem uma role específica."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if session.get('role') not in roles_list:
                flash("Acesso não autorizado.", "error")
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# --- Rotas da Aplicação ---
@app.route('/')
def index():
    """Rota para a página inicial. Redireciona para o dashboard se o usuário já estiver logado."""
    if 'username' in session:
        if session.get('role') == 'medico':
            return redirect(url_for('dashboard_medico'))
        else:
            return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Gerencia o login de usuários, validando credenciais e criando a sessão."""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        usuario_logado, mensagem = auth_manager.verificar_login(username, password)
        if usuario_logado:
            session['username'] = username
            session['role'] = usuario_logado.get('role', 'paciente')
            flash("Login bem-sucedido!", "success")
            app_core.salvar_log_acao('Login bem-sucedido', username)
            if session['role'] == 'medico':
                return redirect(url_for('dashboard_medico'))
            else:
                return redirect(url_for('dashboard'))
        else:
            flash(mensagem, "error")
            app_core.salvar_log_acao('Tentativa de login falhada', username)
    return render_template('login.html')

@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    """Permite o cadastro de novos usuários com seus dados iniciais."""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form.get('email')
        razao_ic = float(request.form.get('razao_ic')) if request.form.get('razao_ic') else None
        fator_sensibilidade = float(request.form.get('fator_sensibilidade')) if request.form.get('fator_sensibilidade') else None

        sucesso, mensagem = auth_manager.salvar_usuario(
            username, password, email=email, razao_ic=razao_ic, fator_sensibilidade=fator_sensibilidade
        )

        if sucesso:
            flash("Cadastro realizado com sucesso! Faça login para continuar.", "success")
            app_core.salvar_log_acao('Cadastro de novo usuário', username)
            return redirect(url_for('login'))
        else:
            flash(mensagem, "warning")
            app_core.salvar_log_acao('Tentativa de cadastro falhada', username)
    return render_template('cadastro.html')

@app.route('/logout')
def logout():
    """Encerra a sessão do usuário."""
    session.pop('username', None)
    session.pop('role', None)
    flash("Sessão encerrada.", "info")
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    """Dashboard para usuários pacientes."""
    if session.get('role') == 'medico':
        return redirect(url_for('dashboard_medico'))
    username = session['username']
    resumo_dados = app_core.get_resumo_dashboard(username)
    return render_template('dashboard.html',
                           username=username,
                           resumo_dados=resumo_dados,
                           total_calorias_diarias=resumo_dados.get('total_calorias_diarias', 0.0))

@app.route('/dashboard_medico')
@roles_required(['medico'])
def dashboard_medico():
    """Dashboard para o médico, mostrando uma lista de todos os pacientes."""
    # Corrigido: usa o db_manager de usuários
    pacientes = db_manager_usuarios.carregar_pacientes()
    return render_template('dashboard_medico.html', usuarios=pacientes)

@app.route('/guia_insulina')
@login_required
def guia_insulina():
    """Exibe a página com o guia de insulina."""
    return render_template('guia_insulina.html')

@app.route('/perfil', methods=['GET', 'POST'])
@login_required
def perfil():
    """Permite ao usuário visualizar e editar suas informações de perfil."""
    username = session['username']
    # Corrigido: usa o db_manager de usuários
    usuario_atual = db_manager_usuarios.carregar_usuario(username)

    if not usuario_atual:
        flash("Usuário não encontrado.", "error")
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        try:
            dados_perfil = {
                'email': request.form.get('email'),
                'data_nascimento': request.form.get('data_nascimento'),
                'sexo': request.form.get('sexo'),
                'razao_ic': float(request.form.get('razao_ic')) if request.form.get('razao_ic') else None,
                'fator_sensibilidade': float(request.form.get('fator_sensibilidade')) if request.form.get('fator_sensibilidade') else None,
            }
            # Corrigido: usa o db_manager de usuários
            db_manager_usuarios.atualizar_perfil_usuario(username, dados_perfil)
            flash("Perfil atualizado com sucesso!", "success")
            app_core.salvar_log_acao("Perfil de usuário atualizado.", username)
            return redirect(url_for('perfil'))
        except (ValueError, KeyError):
            flash("Por favor, insira valores válidos para todos os campos.", "error")
            return redirect(url_for('perfil'))
    else:
        return render_template('perfil.html', usuario=usuario_atual)

# --- INÍCIO: Novas Rotas para a Ficha Médica ---
@app.route('/ficha_medica/<username>', methods=['GET', 'POST'])
@roles_required(['medico'])
def ficha_medica(username):
    """
    Permite ao médico visualizar e editar a ficha médica de um paciente.
    A busca e a atualização são feitas na nova tabela 'fichas_medicas'.
    """
    # Corrigido: usa o db_manager de usuários
    paciente = db_manager_usuarios.carregar_ficha_medica(username)
    if not paciente:
        flash('Paciente não encontrado ou não é paciente.', 'danger')
        return redirect(url_for('dashboard_medico'))

    if request.method == 'POST':
        dados_ficha = {
            'paciente_id': paciente['id'],
            'condicao_atual': request.form.get('condicao_atual'),
            'alergias': request.form.get('alergias'),
            'historico_familiar': request.form.get('historico_familiar'),
            'medicamentos_uso': request.form.get('medicamentos_uso')
        }
        # Corrigido: usa o db_manager de usuários
        db_manager_usuarios.salvar_ficha_medica(dados_ficha)
        flash('Ficha médica atualizada com sucesso!', 'success')
        return redirect(url_for('perfil_paciente', username=username))

    return render_template('ficha_medica.html', paciente=paciente)
# --- FIM: Novas Rotas para a Ficha Médica ---


@app.route('/registrar_glicemia', methods=['GET', 'POST'])
@login_required
def registrar_glicemia():
    """Permite ao usuário registrar uma medição de glicemia e uma refeição."""
    if request.method == 'POST':
        try:
            dados_processados = _processar_dados_registro(request.form)

            # Corrigido: usa o app_core, que já tem a instância de glicemia
            app_core.adicionar_registro(
                usuario=session['username'],
                tipo="Refeição",
                **dados_processados
            )

            if dados_processados['valor'] > 300:
                flash("Atenção: Glicemia elevada. A redução da glicose deve ser gradual (idealmente 50-70 mg/dL por hora). Consulte um profissional de saúde.", "warning")
            elif dados_processados['valor'] < 70:
                flash("Atenção: Hipoglicemia detetada. Considere consumir 15g de carboidratos de ação rápida (por exemplo, 3-4 pastilhas de glicose ou 1/2 copo de sumo de fruta).", "warning")
            else:
                flash("Registo adicionado com sucesso!", "success")

            app_core.salvar_log_acao(f'Registro de glicemia e refeição: {dados_processados["valor"]}', session['username'])
            return redirect(url_for('registros'))

        except (ValueError, KeyError) as e:
            flash(f"Por favor, insira valores numéricos válidos. Campos como 'valor', 'carboidratos' ou 'data e hora' podem estar incorretos. Erro: {e}", "error")
            return redirect(url_for('registrar_glicemia'))

    return render_template('registrar_glicemia.html')

@app.route('/cadastrar_usuario', methods=['GET', 'POST'])
@roles_required(['medico'])
def cadastrar_usuario():
    """Permite ao médico cadastrar um novo usuário com role e dados específicos."""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form.get('email')
        role = request.form.get('role')

        sucesso, mensagem = auth_manager.salvar_usuario(
            username, password, email=email, role=role
        )

        if sucesso:
            flash("Novo usuário cadastrado com sucesso!", "success")
            app_core.salvar_log_acao(f'Novo usuário {username} cadastrado pelo médico', session['username'])
            return redirect(url_for('dashboard_medico'))
        else:
            flash(mensagem, "warning")
            return redirect(url_for('cadastrar_usuario'))

    return render_template('cadastrar_usuario.html')

@app.route('/editar_usuario/<username>', methods=['GET', 'POST'])
@roles_required(['medico'])
def editar_usuario(username):
    """Permite ao médico editar as informações de um usuário existente."""
    # Corrigido: usa o db_manager de usuários
    usuario_a_editar = db_manager_usuarios.carregar_usuario(username)
    
    if not usuario_a_editar:
        flash("Usuário não encontrado.", "error")
        return redirect(url_for('dashboard_medico'))

    if request.method == 'POST':
        try:
            dados_atualizacao = {
                'email': request.form.get('email'),
                'role': request.form.get('role'),
                'data_nascimento': request.form.get('data_nascimento'),
                'sexo': request.form.get('sexo'),
                'razao_ic': float(request.form.get('razao_ic')) if request.form.get('razao_ic') else None,
                'fator_sensibilidade': float(request.form.get('fator_sensibilidade')) if request.form.get('fator_sensibilidade') else None,
                'meta_glicemia': float(request.form.get('meta_glicemia')) if request.form.get('meta_glicemia') else None
            }
            nova_senha = request.form.get('password')

            # Corrigido: usa o db_manager de usuários
            db_manager_usuarios.atualizar_perfil_usuario(username, dados_atualizacao, nova_senha)
            flash(f"Perfil do usuário {username} atualizado com sucesso!", "success")
            app_core.salvar_log_acao(f'Perfil do usuário {username} editado', session['username'])
            return redirect(url_for('dashboard_medico'))
        except (ValueError, KeyError) as e:
            flash(f"Erro ao processar o formulário: {e}", "error")
            return redirect(url_for('editar_usuario', username=username))

    return render_template('editar_usuario.html', usuario=usuario_a_editar, username=username)

@app.route('/excluir_usuario/<username>', methods=['GET'])
@roles_required(['medico'])
def excluir_usuario(username):
    """Permite ao médico excluir um usuário."""
    if username == session.get('username'):
        flash("Não é possível excluir a si mesmo.", "warning")
        return redirect(url_for('dashboard_medico'))

    # Corrigido: usa o db_manager de usuários
    sucesso = db_manager_usuarios.excluir_usuario(username)
    if sucesso:
        flash(f"Usuário {username} e todos os seus dados foram excluídos com sucesso.", "success")
        app_core.salvar_log_acao(f'Usuário {username} e dados relacionados excluídos', session['username'])
    else:
        flash(f"Usuário {username} não encontrado.", "error")
    
    return redirect(url_for('dashboard_medico'))

@app.route('/registrar_alimento', methods=['GET', 'POST'])
@login_required
def registrar_alimento():
    """Permite ao usuário registrar um novo alimento na base de dados."""
    if request.method == 'POST':
        try:
            nome = request.form['nome_alimento']
            medida_caseira = request.form.get('medida_caseira', '')
            peso_g = float(request.form.get('peso_g', 0))
            carbs = float(request.form.get('cho', 0))
            kcal = float(request.form.get('kcal', 0))
            
            novo_alimento_data = {
                "ALIMENTO": nome,
                "MEDIDA CASEIRA": medida_caseira,
                "PESO (g/ml)": peso_g,
                "Kcal": kcal,
                "CHO (g)": carbs
            }

        except (ValueError, KeyError) as e:
            flash(f"Erro ao processar os dados: {e}", "error")
            return redirect(url_for('registrar_alimento'))

        # Corrigido: usa o app_core, que já tem a instância de glicemia
        if app_core.salvar_alimento_json(novo_alimento_data):
            flash(f"Alimento '{nome}' salvo com sucesso!", "success")
            app_core.salvar_log_acao(f'Novo alimento registrado: {nome}', session['username'])
        else:
            flash(f"O alimento '{nome}' já existe na base de dados. Por favor, use outro nome.", "error")

        return redirect(url_for('registrar_alimento'))

    return render_template('registrar_alimento.html')

@app.route('/buscar_alimento', methods=['POST'])
@login_required
def buscar_alimento():
    """Busca alimentos com base em um termo de pesquisa para uso em AJAX."""
    termo = request.form.get('termo_pesquisa')

    if not termo or len(termo) < 3:
        return jsonify({'resultados': []})

    try:
        # Corrigido: usa o app_core, que já tem a instância de glicemia
        resultados = app_core.pesquisar_alimentos(termo)
        return jsonify({'resultados': resultados})

    except Exception as e:
        print(f"Erro ao buscar alimentos: {e}")
        return jsonify({'erro': 'Erro interno ao buscar alimentos.'}), 500

@app.route('/registros')
@login_required
def registros():
    """Exibe a lista de registros de glicemia e refeições do usuário."""
    # Corrigido: usa o app_core, que já tem a instância de glicemia
    registros = app_core.mostrar_registros(usuario_filtro=session['username'])
    
    return render_template('registros.html',
                           registros=registros,
                           get_status_class=get_status_class,
                           get_cor_glicemia=get_cor_glicemia,
                           get_cor_classificacao=get_cor_classificacao)

@app.route('/excluir_registo/<int:id>', methods=['POST'])
@login_required
def excluir_registo(id):
    """Exclui um registro específico pelo seu ID."""
    # Corrigido: usa o app_core, que já tem a instância de glicemia
    sucesso = app_core.excluir_registro(id)
    if sucesso:
        flash('Registro excluído com sucesso!', 'success')
        app_core.salvar_log_acao(f'Registro de ID {id} excluído', session['username'])
    else:
        flash('Erro ao excluir o registro.', 'danger')

    return redirect(url_for('registros'))

@app.route('/grafico_glicemia')
@login_required
def grafico_glicemia():
    """Exibe a página com os gráficos de glicemia."""
    return render_template('grafico_glicemia.html')

@app.route('/dados_calorias_diarias')
@login_required
def dados_calorias_diarias():
    """Fornece dados de calorias diárias para um gráfico em formato JSON."""
    # Corrigido: usa o app_core, que já tem a instância de glicemia
    registros = app_core.mostrar_registros(usuario_filtro=session['username'])
    
    calorias_por_dia = {}
    
    for reg in registros:
        if 'total_calorias' in reg and isinstance(reg['data_hora'], datetime):
            dia = reg['data_hora'].strftime('%d/%m')
            calorias_por_dia[dia] = calorias_por_dia.get(dia, 0) + reg['total_calorias']
            
    rotulos = sorted(calorias_por_dia.keys())
    valores = [calorias_por_dia[dia] for dia in rotulos]
    
    return jsonify({'rotulos_dias': rotulos, 'valores_calorias': valores})

@app.route('/calcular_bolus', methods=['GET', 'POST'])
@login_required
def calcular_bolus():
    """Permite ao usuário calcular a dose de insulina (bolus) com base em seus dados de perfil."""
    resultado_bolus = None
    glicemia_momento = None
    carboidratos_refeicao = None
    
    if request.method == 'POST':
        try:
            glicemia_momento = float(request.form['glicemia_momento'])
            carboidratos_refeicao = float(request.form['carboidratos_refeicao'])

            # Corrigido: usa o db_manager de usuários
            usuario = db_manager_usuarios.carregar_usuario(session['username'])
            razao_ic = usuario.get('razao_ic')
            fator_sensibilidade = usuario.get('fator_sensibilidade')
            meta_glicemia = usuario.get('meta_glicemia', 100)

            if razao_ic is None or fator_sensibilidade is None:
                flash("Por favor, preencha a Razão IC e o Fator de Sensibilidade no seu perfil para usar esta calculadora.", "warning")
            else:
                resultado_bolus = calcular_bolus_detalhado(
                    carboidratos_refeicao,
                    glicemia_momento,
                    meta_glicemia,
                    razao_ic,
                    fator_sensibilidade
                )
                flash("Cálculo realizado com sucesso!", "success")
                app_core.salvar_log_acao(f'Cálculo de bolus: {resultado_bolus["bolus_total"]} UI', session['username'])

        except (ValueError, KeyError) as e:
            flash(f"Valores inválidos. Por favor, insira números válidos. Erro: {e}", "error")

    return render_template(
        'calculadora_bolus.html',
        resultado_bolus=resultado_bolus,
        glicemia_momento=glicemia_momento,
        carboidratos_refeicao=carboidratos_refeicao
    )

@app.route('/calcular_fs', methods=['GET', 'POST'])
@login_required
def calcular_fs():
    """Permite ao usuário calcular o Fator de Sensibilidade à Insulina (FS)."""
    resultado_fs = None

    if request.method == 'POST':
        try:
            dtdi = float(request.form['dtdi'])
            tipo_insulina = request.form['tipo_insulina']

            resultado_fs = calcular_fator_sensibilidade(dtdi, tipo_insulina)
            
            app_core.salvar_log_acao(f'Cálculo de Fator de Sensibilidade: {resultado_fs} mg/dL', session['username'])
            flash("Cálculo realizado com sucesso!", "success")

        except (ValueError, KeyError) as e:
            flash("Valores inválidos. Por favor, insira números válidos.", "error")

    return render_template('calcular_fs.html', resultado_fs=resultado_fs)

@app.route('/editar_registo/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_registo(id):
    """Permite ao usuário editar um registro de glicemia existente."""
    # Corrigido: usa o app_core, que já tem a instância de glicemia
    registo_para_editar = app_core.encontrar_registro(id)

    if not registo_para_editar:
        flash('Registro não encontrado.', 'danger')
        return redirect(url_for('registros'))

    if isinstance(registo_para_editar.get('data_hora'), datetime):
        registo_para_editar['data_hora_str'] = registo_para_editar['data_hora'].isoformat()

    if request.method == 'POST':
        try:
            dados_processados = _processar_dados_registro(request.form)

            # Corrigido: usa o app_core, que já tem a instância de glicemia
            app_core.atualizar_registro(
                id,
                tipo="Refeição",
                **dados_processados
            )

            flash('Registro atualizado com sucesso!', 'success')
            app_core.salvar_log_acao(f'Registro {id} editado', session['username'])
            return redirect(url_for('registros'))

        except (ValueError, KeyError) as e:
            flash(f'Erro ao processar os dados: {e}', 'danger')
            return redirect(url_for('editar_registo', id=id))

    else:
        return render_template('editar_registo.html',
                               registo=registo_para_editar,
                               alimentos_refeicao=registo_para_editar.get('alimentos_refeicao', []),
                               total_carbs=registo_para_editar.get('total_carbs', 0.0))

@app.route('/relatorios')
@login_required
def relatorios():
    """Renderiza a página com todos os gráficos de relatórios."""
    return render_template('relatorios.html')

# Novas Rotas para dados JSON
@app.route('/dados_glicemia_json')
@login_required
def dados_glicemia_json():
    """Fornece dados de glicemia para o gráfico em formato JSON."""
    # Corrigido: usa o app_core, que já tem a instância de glicemia
    registros = app_core.mostrar_registros(usuario_filtro=session['username'])
    
    dados_filtrados = sorted([
        {'data_hora': reg['data_hora'].isoformat(), 'valor': reg['valor']}
        for reg in registros if 'valor' in reg
    ], key=lambda x: x['data_hora'])

    labels = [datetime.fromisoformat(d['data_hora']).strftime('%d/%m %H:%M') for d in dados_filtrados]
    data = [d['valor'] for d in dados_filtrados]

    return jsonify({'labels': labels, 'data': data})

@app.route('/dados_calorias_diarias_json')
@login_required
def dados_calorias_diarias_json():
    """Fornece dados de calorias diárias para um gráfico em formato JSON."""
    # Corrigido: usa o app_core, que já tem a instância de glicemia
    registros = app_core.mostrar_registros(usuario_filtro=session['username'])
    
    calorias_por_dia = {}
    
    for reg in registros:
        if 'total_calorias' in reg and isinstance(reg['data_hora'], datetime):
            dia = reg['data_hora'].strftime('%d/%m')
            calorias_por_dia[dia] = calorias_por_dia.get(dia, 0) + reg['total_calorias']
            
    rotulos = sorted(calorias_por_dia.keys())
    valores = [calorias_por_dia[dia] for dia in rotulos]
    
    return jsonify({'labels': rotulos, 'data': valores})

@app.route('/dados_carbs_diarios_json')
@login_required
def dados_carbs_diarios_json():
    """Fornece dados de carboidratos diários para um gráfico em formato JSON."""
    # Corrigido: usa o app_core, que já tem a instância de glicemia
    registros = app_core.mostrar_registros(usuario_filtro=session['username'])
    
    carbs_por_dia = {}
    
    for reg in registros:
        if 'total_carbs' in reg and isinstance(reg['data_hora'], datetime):
            dia = reg['data_hora'].strftime('%d/%m')
            carbs_por_dia[dia] = carbs_por_dia.get(dia, 0) + reg['total_carbs']
            
    rotulos = sorted(carbs_por_dia.keys())
    valores = [carbs_por_dia[dia] for dia in rotulos]
    
    return jsonify({'labels': rotulos, 'data': valores})

@app.route('/perfil_paciente/<username>')
@roles_required(['medico'])
def perfil_paciente(username):
    """
    Permite ao médico visualizar o perfil e os registros de um paciente específico.
    Agora busca também os dados da ficha médica.
    """
    # Corrigido: usa o db_manager de usuários
    paciente = db_manager_usuarios.carregar_ficha_medica(username)
    if not paciente:
        flash("Paciente não encontrado.", "error")
        return redirect(url_for('dashboard_medico'))
    
    # Corrigido: usa o app_core, que já tem a instância de glicemia
    registros = app_core.mostrar_registros(usuario_filtro=username)

    return render_template(
        'perfil_paciente.html',
        paciente=paciente,
        registros=registros,
        get_status_class=get_status_class
    )

def criar_usuarios_iniciais():
    """Cria um usuário médico e um usuário de teste se eles não existirem."""
    conn = sqlite3.connect('banco_de_dados.db')
    cursor = conn.cursor()
    
    # Verifica se o médico já existe
    cursor.execute('SELECT id FROM usuarios WHERE username = ?', ('medico',))
    if cursor.fetchone() is None:
        print("Criando usuário médico...")
        hashed_password = bcrypt.hashpw('medico'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        cursor.execute('INSERT INTO usuarios (username, password, role) VALUES (?, ?, ?)',
                       ('medico', hashed_password, 'medico'))
    
    # Verifica se o paciente de teste já existe
    cursor.execute('SELECT id FROM usuarios WHERE username = ?', ('davi',))
    if cursor.fetchone() is None:
        print("Criando usuário paciente de teste...")
        hashed_password = bcrypt.hashpw('davi'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        cursor.execute('INSERT INTO usuarios (username, password, role) VALUES (?, ?, ?)',
                       ('davi', hashed_password, 'paciente'))

    conn.commit()
    conn.close()

# --- Inicialização da Aplicação ---
if __name__ == '__main__':
    
    criar_usuarios_iniciais()
    app.run(debug=True)