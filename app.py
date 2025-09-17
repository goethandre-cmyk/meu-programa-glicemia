from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from functools import wraps
from datetime import datetime, date
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

# --- Inicialização Unificada da Aplicação ---
db_manager = DatabaseManager(db_path='app.db')
auth_manager = AuthManager(db_manager)
app_core = AppCore(db_manager)


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
    """Página inicial. Redireciona para o dashboard correto se o usuário já estiver logado."""
    if 'username' in session:
        role = session.get('role')
        if role == 'medico' or role == 'admin':
            return redirect(url_for('dashboard_medico'))
        else:
            return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Gerencia o login de usuários."""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        usuario_logado, mensagem = auth_manager.verificar_login(username, password)
        if usuario_logado:
            session['username'] = username
            session['role'] = usuario_logado['role']
            flash("Login bem-sucedido!", "success")
            app_core.salvar_log_acao('Login bem-sucedido', username)
            # Lógica corrigida para redirecionar para o dashboard correto com base na role
            if session.get('role') == 'medico' or session.get('role') == 'admin':
                return redirect(url_for('dashboard_medico'))
            else:
                return redirect(url_for('dashboard'))
        else:
            flash(mensagem, "error")
            app_core.salvar_log_acao('Tentativa de login falhada', username)
    return render_template('login.html')

@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    """Permite o cadastro de novos usuários pacientes."""
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
    # A rota dashboard_medico já lida com médicos/admins, então essa rota é exclusiva para pacientes
    username = session['username']
    resumo_dados = app_core.get_resumo_dashboard(username)
    return render_template('dashboard.html',
                           username=username,
                           resumo_dados=resumo_dados,
                           total_calorias_diarias=resumo_dados.get('total_calorias_diarias', 0.0))

@app.route('/dashboard_medico')
@roles_required(['medico', 'admin'])
def dashboard_medico():
    """Dashboard para o médico, com uma lista de pacientes."""
    pacientes = db_manager.carregar_pacientes()
    return render_template('dashboard_medico.html', usuarios=pacientes)

@app.route('/guia_insulina')
@login_required
def guia_insulina():
    """Exibe a página com o guia de insulina."""
    return render_template('guia_insulina.html')

@app.route('/perfil', methods=['GET', 'POST'])
@login_required
def perfil():
    """Permite ao usuário visualizar e editar seu perfil."""
    username = session['username']
    usuario_atual = db_manager.carregar_usuario(username)

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
            auth_manager.atualizar_perfil_usuario(username, dados_perfil)
            flash("Perfil atualizado com sucesso!", "success")
            app_core.salvar_log_acao("Perfil de usuário atualizado.", username)
            return redirect(url_for('perfil'))
        except (ValueError, KeyError):
            flash("Por favor, insira valores válidos para todos os campos.", "error")
            return redirect(url_for('perfil'))
    else:
        return render_template('perfil.html', usuario=usuario_atual)

@app.route('/ficha_medica/<username>', methods=['GET', 'POST'])
@roles_required(['medico', 'admin'])
def ficha_medica(username):
    """Permite ao médico/admin visualizar e editar a ficha médica de um paciente."""
    paciente = db_manager.carregar_ficha_medica(username)
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
        db_manager.salvar_ficha_medica(dados_ficha)
        flash('Ficha médica atualizada com sucesso!', 'success')
        return redirect(url_for('perfil_paciente', username=username))

    return render_template('ficha_medica.html', paciente=paciente)

@app.route('/registrar_glicemia', methods=['GET', 'POST'])
@login_required
def registrar_glicemia():
    """Permite registrar uma medição de glicemia e uma refeição."""
    if request.method == 'POST':
        try:
            dados_processados = _processar_dados_registro(request.form)
            user = db_manager.carregar_usuario(session['username'])

            app_core.adicionar_registro(
                usuario=session['username'],
                tipo="Refeição",
                **dados_processados
            )

            if dados_processados['valor'] > 300:
                flash("Atenção: Glicemia elevada. Consulte um profissional de saúde.", "warning")
            elif dados_processados['valor'] < 70:
                flash("Atenção: Hipoglicemia detetada. Considere consumir 15g de carboidratos de ação rápida.", "warning")
            else:
                flash("Registo adicionado com sucesso!", "success")

            app_core.salvar_log_acao(f'Registro de glicemia e refeição: {dados_processados["valor"]}', session['username'])
            return redirect(url_for('registros'))

        except (ValueError, KeyError) as e:
            flash(f"Por favor, insira valores numéricos válidos. Erro: {e}", "error")
            return redirect(url_for('registrar_glicemia'))

    return render_template('registrar_glicemia.html')

@app.route('/cadastrar_usuario', methods=['GET', 'POST'])
@roles_required(['medico', 'admin'])
def cadastrar_usuario():
    """Permite ao médico/admin cadastrar um novo usuário com role e dados específicos."""
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
            app_core.salvar_log_acao(f'Novo usuário {username} cadastrado', session['username'])
            # Redireciona para a página que mostra todos os usuários
            return redirect(url_for('gerenciar_usuarios'))
        else:
            flash(mensagem, "warning")
            return redirect(url_for('cadastrar_usuario'))

    return render_template('cadastrar_usuario.html')

@app.route('/editar_usuario/<username>', methods=['GET', 'POST'])
@roles_required(['medico', 'admin'])
def editar_usuario(username):
    """Permite ao médico/admin editar as informações de um usuário existente."""
    usuario_a_editar = db_manager.carregar_usuario(username)
    
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

            auth_manager.atualizar_perfil_usuario(username, dados_atualizacao, nova_senha)
            flash(f"Perfil do usuário {username} atualizado com sucesso!", "success")
            app_core.salvar_log_acao(f'Perfil do usuário {username} editado', session['username'])
            # Redireciona para a página que mostra todos os usuários
            return redirect(url_for('gerenciar_usuarios'))
        except (ValueError, KeyError) as e:
            flash(f"Erro ao processar o formulário: {e}", "error")
            return redirect(url_for('editar_usuario', username=username))

    return render_template('editar_usuario.html', usuario=usuario_a_editar, username=username)

@app.route('/excluir_usuario/<username>', methods=['GET'])
@roles_required(['medico', 'admin'])
def excluir_usuario(username):
    """Permite ao médico/admin excluir um usuário."""
    if username == session.get('username'):
        flash("Não é possível excluir a si mesmo.", "warning")
        return redirect(url_for('gerenciar_usuarios'))

    sucesso = db_manager.excluir_usuario(username)
    if sucesso:
        flash(f"Usuário {username} e todos os seus dados foram excluídos com sucesso.", "success")
        app_core.salvar_log_acao(f'Usuário {username} e dados relacionados excluídos', session['username'])
    else:
        flash(f"Usuário {username} não encontrado.", "error")
    
    return redirect(url_for('gerenciar_usuarios'))

@app.route('/registrar_alimento', methods=['GET', 'POST'])
@login_required
def registrar_alimento():
    """Permite ao usuário registrar um novo alimento."""
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
            if app_core.salvar_alimento_json(novo_alimento_data):
                flash(f"Alimento '{nome}' salvo com sucesso!", "success")
                app_core.salvar_log_acao(f'Novo alimento registrado: {nome}', session['username'])
            else:
                flash(f"O alimento '{nome}' já existe na base de dados.", "error")
        except (ValueError, KeyError) as e:
            flash(f"Erro ao processar os dados: {e}", "error")
        
        return redirect(url_for('registrar_alimento'))
    return render_template('registrar_alimento.html')

@app.route('/buscar_alimentos', methods=['POST'])
@login_required
def buscar_alimento():
    """Busca alimentos com base em um termo de pesquisa (para uso com AJAX)."""
    termo = request.form.get('termo_pesquisa')
    if not termo or len(termo) < 3:
        return jsonify({'resultados': []})
    try:
        resultados = app_core.pesquisar_alimentos(termo)
        return jsonify({'resultados': resultados})
    except Exception as e:
        print(f"Erro ao buscar alimentos: {e}")
        return jsonify({'erro': 'Erro interno ao buscar alimentos.'}), 500

@app.route('/registros')
@login_required
def registros():
    """Exibe a lista de registros de glicemia e refeições do usuário."""
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

@app.route('/calcular_bolus', methods=['GET', 'POST'])
@login_required
def calcular_bolus():
    """Calcula a dose de insulina (bolus) com base em dados do perfil e glicemia/carbs."""
    resultado_bolus = None
    glicemia_momento = None
    carboidratos_refeicao = None
    
    if request.method == 'POST':
        try:
            glicemia_momento = float(request.form['glicemia_momento'])
            carboidratos_refeicao = float(request.form['carboidratos_refeicao'])
            usuario = db_manager.carregar_usuario(session['username'])
            razao_ic = usuario.get('razao_ic')
            fator_sensibilidade = usuario.get('fator_sensibilidade')
            meta_glicemia = usuario.get('meta_glicemia', 100)

            if razao_ic is None or fator_sensibilidade is None:
                flash("Por favor, preencha a Razão IC e o Fator de Sensibilidade no seu perfil para usar esta calculadora.", "warning")
            else:
                resultado_bolus = calcular_bolus_detalhado(
                    carboidratos_refeicao, glicemia_momento, meta_glicemia, razao_ic, fator_sensibilidade
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
        except (ValueError, KeyError):
            flash("Valores inválidos. Por favor, insira números válidos.", "error")
    return render_template('calcular_fs.html', resultado_fs=resultado_fs)

@app.route('/editar_registo/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_registo(id):
    """Permite ao usuário editar um registro de glicemia existente."""
    registo_para_editar = app_core.encontrar_registro(id)

    if not registo_para_editar or registo_para_editar['username'] != session['username']:
        flash('Registro não encontrado ou você não tem permissão para editá-lo.', 'danger')
        return redirect(url_for('registros'))

    if isinstance(registo_para_editar.get('data_hora'), datetime):
        registo_para_editar['data_hora_str'] = registo_para_editar['data_hora'].isoformat()

    if request.method == 'POST':
        try:
            dados_processados = _processar_dados_registro(request.form)
            app_core.atualizar_registro(id, tipo="Refeição", **dados_processados)
            flash('Registro atualizado com sucesso!', 'success')
            app_core.salvar_log_acao(f'Registro {id} editado', session['username'])
            return redirect(url_for('registros'))
        except (ValueError, KeyError) as e:
            flash(f'Erro ao processar os dados: {e}', 'danger')
            return redirect(url_for('editar_registo', id=id))

    return render_template('editar_registo.html',
                           registo=registo_para_editar,
                           alimentos_refeicao=registo_para_editar.get('alimentos_refeicao', []),
                           total_carbs=registo_para_editar.get('total_carbs', 0.0))

@app.route('/relatorios')
@login_required
def relatorios():
    """Renderiza a página com todos os gráficos de relatórios."""
    return render_template('relatorios.html')

# --- Rotas para dados JSON (gráficos) ---

@app.route('/dados_glicemia_json')
@login_required
def dados_glicemia_json():
    """Fornece dados de glicemia para o gráfico em formato JSON."""
    user_id = db_manager.carregar_usuario(session['username'])['id']
    dados_glicemia = db_manager.obter_dados_glicemia_json(user_id)
    return jsonify(dados_glicemia)

@app.route('/dados_calorias_diarias_json')
@login_required
def dados_calorias_diarias_json():
    """Fornece dados de calorias diárias para um gráfico em formato JSON."""
    user_id = db_manager.carregar_usuario(session['username'])['id']
    dados_calorias = db_manager.obter_dados_calorias_diarias(user_id)
    return jsonify(dados_calorias)

@app.route('/dados_carbs_diarios_json')
@login_required
def dados_carbs_diarios_json():
    """Fornece dados de carboidratos diários para um gráfico em formato JSON."""
    user_id = db_manager.carregar_usuario(session['username'])['id']
    dados_carbs = db_manager.obter_dados_carbs_diarios(user_id)
    return jsonify(dados_carbs)

@app.route('/perfil_paciente/<username>')
@roles_required(['medico', 'admin'])
def perfil_paciente(username):
    """Permite ao médico/admin visualizar o perfil e os registros de um paciente específico."""
    paciente = db_manager.carregar_ficha_medica(username)
    if not paciente:
        flash("Paciente não encontrado.", "error")
        # Redireciona para a página de gerenciamento, que é a lista de todos os usuários
        return redirect(url_for('gerenciar_usuarios'))
    
    registros = app_core.mostrar_registros(usuario_filtro=username)

    return render_template(
        'perfil_paciente.html',
        paciente=paciente,
        registros=registros,
        get_status_class=get_status_class
    )

@app.route('/importar_alimentos')
@login_required
@roles_required(['admin'])
def importar_alimentos():
    """
    IMPORTAÇÃO DE DADOS: Rota para importar alimentos a partir de um arquivo CSV.
    Esta rota é para ser usada UMA ÚNICA VEZ para carregar os dados.
    """
    filename = 'seus_alimentos.csv'
    registros_importados = db_manager.importar_alimentos_csv(filename)
    if registros_importados > 0:
        flash(f"{registros_importados} alimentos importados com sucesso!", "success")
    else:
        flash("Nenhum alimento foi importado. Verifique o arquivo.", "warning")
    # Redireciona para o dashboard correto
    role = session.get('role')
    if role == 'medico' or role == 'admin':
        return redirect(url_for('dashboard_medico'))
    else:
        return redirect(url_for('dashboard'))

@app.route('/gerenciar_usuarios')
@roles_required(['medico', 'admin'])
def gerenciar_usuarios():
    """Rota para o médico/admin visualizar e gerenciar todos os usuários."""
    usuarios = db_manager.carregar_todos_usuarios()
    return render_template('gerenciar_usuarios.html', usuarios=usuarios)


# --- Inicialização da Aplicação ---
if __name__ == '__main__':
    # Use a rota `/importar_alimentos` para carregar seus dados do CSV.
    app.run(debug=True)