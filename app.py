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
    flash,
    get_flashed_messages
)
# Alteração aqui: importa a classe 'datetime' diretamente
from datetime import datetime, timedelta, date # NOVO: Importando 'date' para lidar com datas
import bcrypt

# Importa as classes e funções utilitárias do seu módulo logica.py
from logica import (
    DataManager,
    AuthManager,
    AppCore,
    get_cor_glicemia,
    get_cor_classificacao,
    calcular_fator_sensibilidade,
    calcular_bolus_detalhado
)

app = Flask(__name__)
# Chave secreta para a segurança das sessões.
app.secret_key = '0edd34d5d0228451a8b702f7902892c5'

# Instâncias globais das classes de lógica.
data_manager = DataManager()
auth_manager = AuthManager(data_manager)
app_core = AppCore(data_manager)

# --- Funções Decoradoras (Middleware) ---
def login_required(f):
    """
    Decorador para proteger rotas que exigem autenticação.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash("Por favor, faça login para aceder a esta página.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- Rotas da Aplicação ---
@app.route('/')
def home():
    """Redireciona para o dashboard se o usuário estiver logado, ou para o login caso contrário."""
    if 'username' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Gerencia o login de usuários, validando credenciais e criando a sessão."""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        usuario_logado, mensagem = auth_manager.verificar_login(username, password)

        if usuario_logado:
            session['username'] = username
            session['role'] = usuario_logado.get('role', 'user')
            flash("Login bem-sucedido!", "success")
            app_core.salvar_log_acao('Login bem-sucedido', username)
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
        razao_ic = request.form.get('razao_ic')
        fator_sensibilidade = request.form.get('fator_sensibilidade')

        sucesso, mensagem = auth_manager.salvar_usuario(
            username,
            password,
            email=email,
            razao_ic=razao_ic,
            fator_sensibilidade=fator_sensibilidade
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
    """Encerra a sessão do usuário, removendo o username e a role da sessão."""
    session.pop('username', None)
    session.pop('role', None)
    flash("Sessão encerrada.", "info")
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    username = session['username']
    
    # Busca todos os registros do usuário
    registros = app_core.mostrar_registros(usuario_filtro=username)
    
    # Inicializa as variáveis de resumo
    resumo_dados = {
        'media_ultima_semana': None,
        'hipoglicemia_count': 0,
        'hiperglicemia_count': 0,
        'ultimo_registro': None,
        'tempo_desde_ultimo': None
    }
    
    # NOVO: Inicializa o total de calorias
    total_calorias_diarias = 0.0

    if registros:
        # Encontra o último registro
        ultimo_registro = registros[0]
        resumo_dados['ultimo_registro'] = ultimo_registro
        
        # Calcula o tempo desde o último registro
        agora = datetime.now()
        delta = agora - ultimo_registro['data_hora']
        
        # Converte o delta em texto amigável
        if delta.days > 0:
            resumo_dados['tempo_desde_ultimo'] = f"{delta.days} dias atrás"
        elif delta.seconds >= 3600:
            horas = delta.seconds // 3600
            resumo_dados['tempo_desde_ultimo'] = f"{horas} horas atrás"
        else:
            minutos = delta.seconds // 60
            resumo_dados['tempo_desde_ultimo'] = f"{minutos} minutos atrás"

        # Filtra registros da última semana e calcula média, hipo e hiper
        sete_dias_atras = agora - timedelta(days=7)
        glicemias_ultima_semana = [
            reg['valor'] 
            for reg in registros 
            if reg['data_hora'] > sete_dias_atras
        ]
        
        if glicemias_ultima_semana:
            media = sum(glicemias_ultima_semana) / len(glicemias_ultima_semana)
            resumo_dados['media_ultima_semana'] = round(media, 2)
        
        # Conta episódios de hipoglicemia e hiperglicemia
        for reg in registros:
            if reg['valor'] < 70:
                resumo_dados['hipoglicemia_count'] += 1
            if reg['valor'] > 180:
                resumo_dados['hiperglicemia_count'] += 1

        # NOVO: Calcula o total de calorias do dia
        hoje = date.today()
        for reg in registros:
            if 'total_calorias' in reg and reg['data_hora'].date() == hoje:
                total_calorias_diarias += reg['total_calorias']
    
    # NOVO: Passa o valor de calorias para o template
    return render_template('dashboard.html', 
                            username=username, 
                            resumo_dados=resumo_dados,
                            total_calorias_diarias=round(total_calorias_diarias, 2)
                          )

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

    if request.method == 'POST':
        try:
            usuarios = data_manager.carregar_usuarios()
            usuario_atual = usuarios.get(username, {})

            usuario_atual['email'] = request.form.get('email')
            usuario_atual['data_nascimento'] = request.form.get('data_nascimento')
            usuario_atual['sexo'] = request.form.get('sexo')
            usuario_atual['razao_ic'] = float(request.form.get('razao_ic')) if request.form.get('razao_ic') else None
            usuario_atual['fator_sensibilidade'] = float(request.form.get('fator_sensibilidade')) if request.form.get('fator_sensibilidade') else None

            data_manager.salvar_usuarios(usuarios)

            flash("Perfil atualizado com sucesso!", "success")
            app_core.salvar_log_acao("Perfil de usuário atualizado.", username)
            return redirect(url_for('perfil'))
        except (ValueError, KeyError):
            flash("Por favor, insira valores válidos para todos os campos.", "error")
            return redirect(url_for('perfil'))

    else:
        usuarios = data_manager.carregar_usuarios()
        usuario_atual = usuarios.get(username, {})
        return render_template('perfil.html', usuario=usuario_atual)

@app.route('/registrar_glicemia', methods=['GET', 'POST'])
@login_required
def registrar_glicemia():
    """Permite ao usuário registrar uma medição de glicemia e uma refeição."""
    if request.method == 'POST':
        try:
            valor = float(request.form.get('valor', 0))
            refeicao = request.form.get('refeicao', '')
            observacoes = request.form.get('observacoes', '')
            data_hora_str = request.form.get('data_hora')

            data_hora = datetime.strptime(data_hora_str, '%Y-%m-%dT%H:%M')

            alimentos_selecionados = request.form.getlist('alimento_selecionado[]')
            carbs_list = request.form.getlist('carbs[]')

            alimentos_refeicao = []
            total_carbs = 0

            for i in range(len(alimentos_selecionados)):
                alimento_nome = alimentos_selecionados[i]
                carbs_valor = float(carbs_list[i]) if carbs_list[i] else 0
                if alimento_nome:
                    alimentos_refeicao.append({'nome': alimento_nome, 'carbs': carbs_valor})
                    total_carbs += carbs_valor
            
            # NOVO: Calcular total de calorias (1g de carboidrato = 4 kcal)
            total_calorias = total_carbs * 4

            descricao_completa = f"{refeicao}: "
            if alimentos_refeicao:
                alimentos_descricao = [f"{a['nome']} - Carbs: {a['carbs']}g" for a in alimentos_refeicao]
                descricao_completa += f"{', '.join(alimentos_descricao)}. "

            descricao_completa += f"Total Carbs: {total_carbs}g. {observacoes}"

            # NOVO: Passar total_calorias para o método de adicionar registro
            app_core.adicionar_registro(
                tipo="Refeição",
                valor=valor,
                descricao=descricao_completa,
                usuario=session['username'],
                data_hora=data_hora,
                refeicao=refeicao,
                alimentos_refeicao=alimentos_refeicao,
                total_carbs=total_carbs,
                total_calorias=total_calorias, # NOVO: Campo de calorias
                observacoes=observacoes
            )

            if valor > 300:
                flash("Atenção: Glicemia elevada. A redução da glicose deve ser gradual (idealmente 50-70 mg/dL por hora). Consulte um profissional de saúde.", "warning")
            elif valor < 70:
                flash("Atenção: Hipoglicemia detetada. Considere consumir 15g de carboidratos de ação rápida (por exemplo, 3-4 pastilhas de glicose ou 1/2 copo de sumo de fruta).", "warning")
            else:
                flash("Registo adicionado com sucesso!", "success")

            app_core.salvar_log_acao(f'Registro de glicemia e refeição: {valor}', session['username'])
            return redirect(url_for('registros'))

        except ValueError:
            flash("Por favor, insira valores numéricos válidos.", "error")
            return redirect(url_for('registrar_glicemia'))

    return render_template('registrar_glicemia.html')

@app.route('/gerenciar_usuarios')
@login_required
def gerenciar_usuarios():
    """Rota para administradores gerenciarem usuários."""
    if session.get('role') == 'admin':
        usuarios = data_manager.carregar_usuarios()
        return render_template('gerenciar_usuarios.html', usuarios=usuarios)
    else:
        flash("Acesso não autorizado.", "error")
        return redirect(url_for('dashboard'))

# --- ROTAS PARA GERENCIAR USUÁRIOS COMO ADMIN ---
@app.route('/cadastrar_usuario', methods=['GET', 'POST'])
@login_required
def cadastrar_usuario():
    """Permite ao admin cadastrar um novo usuário com role e dados específicos."""
    if not session.get('role') == 'admin':
        flash("Acesso não autorizado.", "error")
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form.get('email')
        role = request.form.get('role')
        razao_ic = request.form.get('razao_ic')
        fator_sensibilidade = request.form.get('fator_sensibilidade')

        sucesso, mensagem = auth_manager.salvar_usuario(
            username, password, email=email, role=role,
            razao_ic=razao_ic, fator_sensibilidade=fator_sensibilidade
        )

        if sucesso:
            flash("Novo usuário cadastrado com sucesso!", "success")
            app_core.salvar_log_acao(f'Novo usuário {username} cadastrado pelo admin', session['username'])
            return redirect(url_for('gerenciar_usuarios'))
        else:
            flash(mensagem, "warning")
            return redirect(url_for('cadastrar_usuario'))

    return render_template('cadastrar_usuario.html')

@app.route('/editar_usuario/<username>', methods=['GET', 'POST'])
@login_required
def editar_usuario(username):
    """Permite ao admin editar as informações de um usuário existente."""
    if not session.get('role') == 'admin':
        flash("Acesso não autorizado.", "error")
        return redirect(url_for('dashboard'))

    usuarios = data_manager.carregar_usuarios()
    usuario_a_editar = usuarios.get(username)
    if not usuario_a_editar:
        flash("Usuário não encontrado.", "error")
        return redirect(url_for('gerenciar_usuarios'))

    if request.method == 'POST':
        try:
            nova_senha = request.form.get('password')

            usuario_a_editar['email'] = request.form.get('email')
            usuario_a_editar['role'] = request.form.get('role')
            razao_ic_str = request.form.get('razao_ic')
            fator_sensibilidade_str = request.form.get('fator_sensibilidade')

            if nova_senha:
                hashed_password = bcrypt.hashpw(nova_senha.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                usuario_a_editar['password'] = hashed_password

            usuario_a_editar['razao_ic'] = float(razao_ic_str) if razao_ic_str else None
            usuario_a_editar['fator_sensibilidade'] = float(fator_sensibilidade_str) if fator_sensibilidade_str else None

            data_manager.salvar_usuarios(usuarios)

            flash(f"Perfil do usuário {username} atualizado com sucesso!", "success")
            app_core.salvar_log_acao(f'Perfil do usuário {username} editado', session['username'])
            return redirect(url_for('gerenciar_usuarios'))
        except (ValueError, KeyError) as e:
            flash(f"Erro ao processar o formulário: {e}", "error")
            return redirect(url_for('editar_usuario', username=username))

    return render_template('editar_usuario.html', usuario=usuario_a_editar, username=username)

@app.route('/excluir_usuario/<username>', methods=['GET'])
@login_required
def excluir_usuario(username):
    """Permite ao admin excluir um usuário."""
    if not session.get('role') == 'admin':
        flash("Acesso não autorizado.", "error")
        return redirect(url_for('dashboard'))

    if username == session.get('username'):
        flash("Não é possível excluir a si mesmo.", "warning")
        return redirect(url_for('gerenciar_usuarios'))

    usuarios = data_manager.carregar_usuarios()
    if username in usuarios:
        del usuarios[username]
        data_manager.salvar_usuarios(usuarios)
        flash(f"Usuário {username} excluído com sucesso.", "success")
        app_core.salvar_log_acao(f'Usuário {username} excluído', session['username'])
    else:
        flash("Usuário não encontrado.", "error")

    return redirect(url_for('gerenciar_usuarios'))

# --- FIM DAS ROTAS DE ADMIN ---

@app.route('/registrar_alimento', methods=['GET', 'POST'])
@login_required
def registrar_alimento():
    """Permite ao usuário registrar um novo alimento na base de dados."""
    if request.method == 'POST':
        try:
            nome = request.form['nome_alimento']
            tipo = request.form.get('tipo_alimento', 'Usuário')
            carbs = float(request.form.get('carbs', 0))
            protein = float(request.form.get('protein', 0))
            fat = float(request.form.get('fat', 0))
            acucares = float(request.form.get('acucares', 0))
            gord_sat = float(request.form.get('gord_sat', 0))
            sodio = float(request.form.get('sodio', 0))
            medida_caseira = request.form.get('medida_caseira', '')
            peso_g = float(request.form.get('peso_g', 0))
        except (ValueError, KeyError):
            flash("Por favor, insira valores numéricos válidos.", "error")
            return redirect(url_for('registrar_alimento'))

        app_core.salvar_alimento_csv(nome, tipo, carbs, protein, fat, acucares, gord_sat, sodio, medida_caseira, peso_g)
        flash(f"Alimento '{nome}' salvo com sucesso!", "success")
        app_core.salvar_log_acao(f'Novo alimento registrado: {nome}', session['username'])
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
                            get_cor_glicemia=get_cor_glicemia,
                            get_cor_classificacao=get_cor_classificacao)

@app.route('/excluir_registo/<id>', methods=['POST'])
@login_required
def excluir_registo(id):
    """Exclui um registro específico pelo seu ID."""
    sucesso = app_core.excluir_registro(id)
    if sucesso:
        flash('Registro excluído com sucesso!', 'success')
    else:
        flash('Erro ao excluir o registro.', 'danger')

    return redirect(url_for('registros'))

@app.route('/grafico_glicemia')
@login_required
def grafico_glicemia():
    """Exibe a página com os gráficos de glicemia."""
    return render_template('grafico_glicemia.html')

# NOVO: Rota para fornecer dados de calorias para o gráfico
@app.route('/dados_calorias_diarias')
@login_required
def dados_calorias_diarias():
    """Fornece dados de calorias diárias para um gráfico em formato JSON."""
    registros = app_core.mostrar_registros(usuario_filtro=session['username'])
    
    calorias_por_dia = {}
    
    # Processa apenas os registros que têm total de calorias
    for reg in registros:
        if 'total_calorias' in reg and isinstance(reg['data_hora'], datetime):
            dia = reg['data_hora'].strftime('%d/%m')
            # Soma as calorias para o dia correspondente
            calorias_por_dia[dia] = calorias_por_dia.get(dia, 0) + reg['total_calorias']
            
    # Prepara os dados para o JSON
    rotulos = sorted(calorias_por_dia.keys())
    valores = [calorias_por_dia[dia] for dia in rotulos]
    
    return jsonify({'rotulos_dias': rotulos, 'valores_calorias': valores})

@app.route('/calcular_bolus', methods=['GET', 'POST'])
@login_required
def calcular_bolus():
    """Permite ao usuário calcular a dose de insulina (bolus) com base em seus dados de perfil."""
    if request.method == 'POST':
        try:
            glicemia_momento = float(request.form['glicemia_momento'])
            carboidratos_refeicao = float(request.form['carboidratos_refeicao'])

            usuario = data_manager.carregar_usuarios().get(session['username'])

            razao_ic = usuario.get('razao_ic')
            fator_sensibilidade = usuario.get('fator_sensibilidade')
            meta_glicemia = usuario.get('meta_glicemia', 100)

            if razao_ic is None or fator_sensibilidade is None:
                flash("Por favor, preencha a Razão IC e o Fator de Sensibilidade no seu perfil para usar esta calculadora.", "warning")
                return redirect(url_for('perfil'))

            resultado_bolus = calcular_bolus_detalhado(
                carboidratos_refeicao,
                glicemia_momento,
                meta_glicemia,
                razao_ic,
                fator_sensibilidade
            )

            session['resultado_bolus'] = resultado_bolus
            session['glicemia_momento'] = glicemia_momento
            session['carboidratos_refeicao'] = carboidratos_refeicao

            app_core.salvar_log_acao(f'Cálculo de bolus: {resultado_bolus["bolus_total"]} UI', session['username'])
            return redirect(url_for('calcular_bolus'))

        except (ValueError, KeyError) as e:
            flash(f"Valores inválidos. Por favor, insira números válidos. Erro: {e}", "error")
            return redirect(url_for('calcular_bolus'))

    resultado_bolus = session.pop('resultado_bolus', None)
    glicemia_momento = session.pop('glicemia_momento', None)
    carboidratos_refeicao = session.pop('carboidratos_refeicao', None)

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

@app.route('/editar_registo/<id>', methods=['GET', 'POST'])
@login_required
def editar_registo(id):
    """Permite ao usuário editar um registro de glicemia existente."""
    registo_para_editar = app_core.encontrar_registro(id)

    if not registo_para_editar:
        flash('Registro não encontrado.', 'danger')
        return redirect(url_for('registros'))

    if isinstance(registo_para_editar.get('data_hora'), datetime):
        registo_para_editar['data_hora_str'] = registo_para_editar['data_hora'].isoformat()

    if request.method == 'POST':
        try:
            valor = float(request.form.get('valor', 0))
            data_hora_str = request.form.get('data_hora')
            refeicao_tipo = request.form.get('refeicao')
            observacoes = request.form.get('observacoes', '')

            alimentos_refeicao = []
            total_carbs = 0.0
            alimentos_selecionados = request.form.getlist('alimento_selecionado[]')
            carbs_list = request.form.getlist('carbs[]')

            for i in range(len(alimentos_selecionados)):
                alimento = alimentos_selecionados[i]
                carbs = float(carbs_list[i]) if carbs_list[i] else 0.0
                if alimento:
                    alimentos_refeicao.append({'nome': alimento, 'carbs': carbs})
                    total_carbs += carbs
            
            # NOVO: Calcular total de calorias
            total_calorias = total_carbs * 4

            descricao = f"{refeicao_tipo}: "
            if alimentos_refeicao:
                alimentos_descricao = [f"{a['nome']} - Carbs: {a['carbs']}g" for a in alimentos_refeicao]
                descricao += " - ".join(alimentos_descricao)
            descricao += f" Total Carbs: {total_carbs}g. {observacoes}"

            # NOVO: Passar total_calorias para o método de atualizar
            app_core.atualizar_registro(
                id,
                tipo="Refeição",
                valor=valor,
                descricao=descricao,
                data_hora=datetime.fromisoformat(data_hora_str),
                refeicao=refeicao_tipo,
                alimentos_refeicao=alimentos_refeicao,
                total_carbs=total_carbs,
                total_calorias=total_calorias, # NOVO: Campo de calorias
                observacoes=observacoes
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
    """Gera a página de relatórios com os dados de glicemia para o gráfico."""
    registros = app_core.mostrar_registros(usuario_filtro=session['username'])

    datas = [reg['data_hora'] for reg in registros if 'valor' in reg]
    valores = [reg['valor'] for reg in registros if 'valor' in reg]
    datas_formatadas = [d.strftime('%d/%m %H:%M') for d in datas]

    return render_template('relatorios.html', labels=datas_formatadas, data=valores)

# --- Inicialização da Aplicação ---
if __name__ == '__main__':
    app.run(debug=True)