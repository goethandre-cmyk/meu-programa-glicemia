# relatorios.py (Versão Reescrita e Otimizada)

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user 
# Importe db_manager de onde ele estiver definido (ex: app.py ou config)
# from . import db_manager  # Exemplo, ajuste conforme sua estrutura

# 1. DEFINIÇÃO DO BLUEPRINT (ESSENCIAL PARA CORRIGIR O NAMERROR)
relatorios_bp = Blueprint('relatorios', __name__)

# --- Funções Auxiliares (Para evitar repetição de código) ---

def verificar_permissao_relatorio():
    """Verifica se o usuário logado tem permissão para acessar relatórios."""
    return current_user.is_authenticated and (current_user.is_paciente or current_user.is_medico)

def buscar_dados_registros():
    """Busca registros de glicemia e refeição para o usuário logado."""
    if not verificar_permissao_relatorio():
        return None, None
    
    # Assume que db_manager e carregar_registros_por_usuario estão disponíveis no escopo
    # O segundo retorno ('_') é o de refeição e o primeiro é o de glicemia.
    registros_glicemia, registros_refeicao = db_manager.carregar_registros_por_usuario(
        current_user.id, 
        dias=30
    )
    return registros_glicemia, registros_refeicao

# --------------------------------------------------------------------------
# --- ROTAS DE RELATÓRIO ---
# --------------------------------------------------------------------------

@relatorios_bp.route('/relatorios')
@login_required
def relatorios():
    """
    Rota principal que renderiza o template 'relatorios.html'.
    Garante que apenas pacientes e médicos autenticados tenham acesso.
    """
    if verificar_permissao_relatorio():
        return render_template('relatorios.html')
    else:
        flash('Você não tem permissão para acessar esta página.', 'danger')
        return redirect(url_for('dashboard'))


@relatorios_bp.route('/dados_glicemia_json')
@login_required
def dados_glicemia_json():
    """Endpoint API: Retorna dados de glicemia (mg/dL) para gráfico de linha."""
    registros_glicemia, _ = buscar_dados_registros()
    
    if registros_glicemia is None:
        return jsonify({'error': 'Acesso negado ou dados não disponíveis'}), 403

    labels = []
    data_valores = []
    
    for registro in registros_glicemia:
        # Formata Data e Hora para o eixo X do gráfico (já feito no código original)
        data_hora = registro['data_hora'].strftime('%d/%m %H:%M')
        labels.append(data_hora)
        data_valores.append(registro['valor'])
            
    return jsonify({
        'labels': labels,
        'data': data_valores
    })


@relatorios_bp.route('/dados_carbs_diarios_json')
@login_required
def dados_carbs_diarios_json():
    """Endpoint API: Retorna o total de carboidratos consumidos por dia para gráfico de barra."""
    _, registros_refeicao = buscar_dados_registros()
    
    if registros_refeicao is None:
        return jsonify({'error': 'Acesso negado ou dados não disponíveis'}), 403
    
    labels = []
    data_valores = []
    
    # O formato do retorno do DB está otimizado para gráficos:
    for registro_dia in registros_refeicao:
        labels.append(registro_dia['_id']) 
        data_valores.append(registro_dia.get('total_carbs', 0.0)) # Usa .get para segurança
            
    return jsonify({
        'labels': labels,
        'data': data_valores
    })


@relatorios_bp.route('/dados_calorias_diarias_json')
@login_required
def dados_calorias_diarias_json():
    """Endpoint API: Retorna o total de calorias consumidas por dia para gráfico de barra."""
    _, registros_refeicao = buscar_dados_registros()
    
    if registros_refeicao is None:
        return jsonify({'error': 'Acesso negado ou dados não disponíveis'}), 403
    
    labels = []
    data_valores = []
    
    for registro_dia in registros_refeicao:
        labels.append(registro_dia['_id']) 
        data_valores.append(registro_dia.get('total_calorias', 0.0)) # Usa .get para segurança
            
    return jsonify({
        'labels': labels,
        'data': data_valores
    })