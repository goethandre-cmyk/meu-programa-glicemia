# relatorios.py (Versão Reescrita e Otimizada)
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user 
# from app import db_manager # <-- REMOVA OU COMENTE ESTA LINHA
from db_instance import db_manager # <--- NOVO: Importa a instância global

relatorios_bp = Blueprint('relatorios', __name__)
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

@relatorios_bp.route('/dados_glicemia_json')
@login_required
def dados_glicemia_json():
    """Endpoint API: Retorna dados de glicemia (mg/dL) para gráfico de linha."""
    if not verificar_permissao_relatorio():
        return jsonify({'error': 'Acesso negado'}), 403

    try:
        # Chama a função otimizada do DB Manager
        dados_brutos = db_manager.obter_dados_glicemia_para_grafico(current_user.id)
        
        labels = [d['data_hora'] for d in dados_brutos]
        data_valores = [d['valor'] for d in dados_brutos]
        
        return jsonify({
            'labels': labels,
            'data': data_valores
        })
    except Exception as e:
        print(f"Erro ao obter dados de glicemia: {e}")
        return jsonify({'error': 'Erro no servidor ao buscar dados.'}), 500


@relatorios_bp.route('/dados_carbs_diarios_json')
@login_required
def dados_carbs_diarios_json():
    """Endpoint API: Retorna o total de carboidratos consumidos por dia para gráfico de barra."""
    if not verificar_permissao_relatorio():
        return jsonify({'error': 'Acesso negado'}), 403

    try:
        # Chama a função otimizada do DB Manager
        dados_brutos = db_manager.obter_carbs_diarios_para_grafico(current_user.id)
        
        labels = [d['data'] for d in dados_brutos]
        data_valores = [d['total_carbs'] for d in dados_brutos]
        
        return jsonify({
            'labels': labels,
            'data': data_valores
        })
    except Exception as e:
        print(f"Erro ao obter dados de carboidratos: {e}")
        return jsonify({'error': 'Erro no servidor ao buscar dados.'}), 500


@relatorios_bp.route('/dados_calorias_diarias_json')
@login_required
def dados_calorias_diarias_json():
    """Endpoint API: Retorna o total de calorias consumidas por dia para gráfico de barra."""
    if not verificar_permissao_relatorio():
        return jsonify({'error': 'Acesso negado'}), 403

    try:
        # Chama a função otimizada do DB Manager
        dados_brutos = db_manager.obter_calorias_diarias_para_grafico(current_user.id)
        
        labels = [d['data'] for d in dados_brutos]
        data_valores = [d['total_calorias'] for d in dados_brutos]
        
        return jsonify({
            'labels': labels,
            'data': data_valores
        })
    except Exception as e:
        # Se você corrigiu o problema SQL, este bloco não deve mais ser executado.
        print(f"Erro ao obter dados de calorias: {e}")
        return jsonify({'error': 'Erro no servidor ao buscar dados.'}), 500
    
@relatorios_bp.route('/relatorios')
@login_required
def relatorios_page():
    """Renderiza a página principal de relatórios."""
    # O template relatorios.html usará os endpoints JSON acima para carregar os gráficos.
    return render_template('relatorios.html') 