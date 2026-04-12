"""
Arquivo de archive: cópias das funções arquivadas no batch 2.

Origem: database_manager.py
Motivo: funções de migração/legacy que serão substituídas por stubs
para permitir limpeza incremental. Mantém o código original para
auditoria e reabilitação rápida.
"""
import json
from datetime import datetime
import os


def _load_json_data_original(db_path):
    """Cópia do _load_json_data original para referência."""
    json_path = os.path.join(os.path.dirname(db_path), 'data.json')
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print("Aviso: Arquivo data.json está corrompido ou vazio.")
            return {}
    return {}


def migrar_fichas_medicas_antigas_original(get_db_connection):
    """Cópia da função migrar_fichas_medicas_antigas original."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT paciente_id, condicao_atual, alergias, historico_familiar, medicamentos_uso
            FROM fichas_medicas
        """)
        dados_antigos = cursor.fetchall()

        data_migracao = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        for row in dados_antigos:
            paciente_id = row[0]
            condicao_atual = row[1]
            alergias = row[2]
            historico_familiar = row[3]
            medicamentos_uso = row[4]
            cursor.execute("""
                INSERT OR IGNORE INTO ficha_medica_unificada (
                    paciente_id, historico_clinico_familiar, observacoes_comorbidades, 
                    medicacoes_atuais, alergias, data_registro, 
                    tipo_diabetes, data_diagnostico, insulina_basal, insulina_bolus
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                paciente_id,
                historico_familiar,
                condicao_atual,
                medicamentos_uso,
                alergias,
                data_migracao,
                'Migrado',
                None,
                None,
                None
            ))
        conn.commit()
        print(f"Migração de {len(dados_antigos)} fichas médicas concluída para 'ficha_medica_unificada'.")
    except Exception as e:
        print(f"Erro na migração de fichas: {e}")
    finally:
        conn.close()


def finalizar_refatoramento_fichas_original(get_db_connection):
    """Cópia da função finalizar_refatoramento_fichas original."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DROP TABLE IF EXISTS fichas_medicas")
        cursor.execute("ALTER TABLE ficha_medica_unificada RENAME TO ficha_medica")
        conn.commit()
        print("finalizar_refatoramento_fichas: concluído")
    except Exception as e:
        print(f"Erro ao finalizar refatoramento de fichas: {e}")
    finally:
        conn.close()


def _migrate_json_to_sqlite_original(get_db_connection, db_path):
    """Cópia resumida da lógica de _migrate_json_to_sqlite para referência."""
    json_data = _load_json_data_original(db_path)
    if not json_data:
        return
    conn = get_db_connection()
    cursor = conn.cursor()
    users_migrated_count = 0
    registros_migrated_count = 0
    for user in json_data.get('users', []):
        try:
            cursor.execute("SELECT id FROM users WHERE username = ?", (user['username'],))
            if cursor.fetchone():
                continue
            cursor.execute("INSERT INTO users (id, username, password_hash) VALUES (?, ?, ?)", (user['id'], user['username'], user.get('password_hash')))
            users_migrated_count += 1
        except Exception as e:
            print(f"Erro ao migrar usuário {user.get('username')}: {e}")
    # registros
    for registro in json_data.get('registros_glicemia_refeicao', []):
        try:
            cursor.execute("SELECT id FROM registros WHERE id = ?", (registro.get('id', -1),))
            if cursor.fetchone():
                continue
            data_hora = registro.get('data_hora') or datetime.now().isoformat()
            tipo = registro.get('tipo') or 'Desconhecido'
            alimentos_json_str = json.dumps(registro.get('alimentos')) if registro.get('alimentos') else None
            cursor.execute("INSERT INTO registros (id, user_id, data_hora, tipo, valor, observacoes, alimentos_refeicao) VALUES (?, ?, ?, ?, ?, ?, ?)", (registro.get('id'), registro['user_id'], data_hora, tipo, registro.get('valor'), registro.get('observacoes'), alimentos_json_str))
            registros_migrated_count += 1
        except Exception as e:
            print(f"Erro ao migrar registro {registro.get('id')}: {e}")
    conn.commit()
    print(f"Migração concluída! {users_migrated_count} usuários e {registros_migrated_count} registros migrados.")
    conn.close()


# ===== Copias de utilitários de logica.py (batch 2) =====
def get_cor_glicemia_original(valor):
    """Retorna uma classe CSS com base no valor da glicemia."""
    if valor < 70:
        return 'bg-warning text-dark'
    elif valor >= 70 and valor <= 140:
        return 'bg-success text-white'
    elif valor > 140 and valor <= 200:
        return 'bg-primary text-white'
    else:
        return 'bg-danger text-white'

def get_cor_classificacao_original(valor):
    """Retorna a cor para a classificação do valor de glicemia."""
    if valor < 70:
        return 'text-danger'
    elif valor >= 70 and valor <= 140:
        return 'text-success'
    elif valor > 140 and valor <= 200:
        return 'text-warning'
    else:
        return 'text-danger'

def get_status_class_original(valor):
    """Retorna a classe CSS para o status de glicemia."""
    if valor < 70:
        return 'status-baixa'
    elif valor >= 70 and valor <= 140:
        return 'status-normal'
    else:
        return 'status-alta'

def calcular_fator_sensibilidade_original(dtdi, tipo_insulina):
    """Calcula o fator de sensibilidade à insulina (FS) pela regra de 500/1800."""
    if tipo_insulina == 'rapida' and dtdi:
        return 500 / dtdi
    elif tipo_insulina == 'ultrarapida' and dtdi:
        return 1800 / dtdi
    return None

def calcular_bolus_detalhado_original(carboidratos, glicemia_atual, meta_glicemia, razao_ic, fator_sensibilidade):
    """Calcula a dose de insulina (bolus) com correção."""
    if not all([carboidratos, glicemia_atual, meta_glicemia, razao_ic, fator_sensibilidade]):
        return None
    bolus_carbs = carboidratos / razao_ic
    fator_correcao = (glicemia_atual - meta_glicemia) / fator_sensibilidade
    bolus_total = bolus_carbs + fator_correcao
    return {
        'bolus_carbs': round(bolus_carbs, 2),
        'fator_correcao': round(fator_correcao, 2),
        'bolus_total': max(0, round(bolus_total, 2))
    }

def processar_dados_registro_original(form_data):
    """Processa dados de formulário para registros de glicemia e refeição."""
    from datetime import datetime
    valor = float(form_data.get('valor_glicemia', 0))
    data_hora_str = form_data.get('data_hora')
    observacoes = form_data.get('observacoes', '')
    alimentos_refeicao = form_data.get('alimentos_refeicao', [])
    try:
        data_hora = datetime.fromisoformat(data_hora_str)
    except (ValueError, TypeError):
        data_hora = datetime.now()
    total_carbs = 0
    for item in alimentos_refeicao:
        carbs = float(item.get('carbs', 0))
        quantidade = float(item.get('quantidade', 0))
        total_carbs += carbs * quantidade
    return {
        "valor": valor,
        "total_carbs": total_carbs,
        "observacoes": observacoes,
        "data_hora": data_hora,
        "alimentos_refeicao": alimentos_refeicao
    }


# ===== Copias adicionais para o próximo lote =====
def _call_original(db_obj, candidates, *args, **kwargs):
    """Cópia do _call do db_adapter para referência."""
    for name in candidates:
        if hasattr(db_obj, name):
            func = getattr(db_obj, name)
            if callable(func):
                return func(*args, **kwargs)
    raise NotImplementedError(f"Nenhum dos métodos {candidates} implementado no db_manager")


def adicionar_alimento_original(request, db_manager, flash, url_for, redirect, render_template):
    """Cópia simplificada da rota adicionar_alimento do app.py."""
    if request.method == 'POST':
        try:
            nome = request.form['nome']
            medida_caseira = request.form['medida_caseira']
            peso_g = float(request.form['peso_g'].replace(',', '.'))
            kcal = float(request.form['kcal'].replace(',', '.'))
            carbs_100g = float(request.form['carbs_100g'].replace(',', '.'))
            novo_alimento = {
                'alimento': nome,
                'medida_caseira': medida_caseira,
                'peso': peso_g,
                'kcal': kcal,
                'carbs': carbs_100g
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


def carregar_todos_alimentos_original():
    """Cópia de carregar_todos_alimentos de logica.py"""
    file_path = 'data/alimentos.json'
    if not os.path.exists(file_path):
        return []
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        return data.get('alimentos', [])


def listar_alimentos_simples_original():
    """Cópia de listar_alimentos_simples de logica.py"""
    try:
        alimentos_completos = carregar_todos_alimentos_original()
        lista_simples = [alimento['ALIMENTO'] for alimento in alimentos_completos]
        return lista_simples
    except Exception:
        return []


def carregar_registros_por_usuario_original(db_path, username):
    """Cópia de carregar_registros_por_usuario de logica.py"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT r.*, u.username 
        FROM registros r
        JOIN users u ON r.user_id = u.id
        WHERE u.username = ?
        ORDER BY r.data_hora DESC;
    """, (username,))
    registros = cursor.fetchall()
    return [{**dict(reg), 'alimentos_refeicao': json.loads(reg['alimentos_refeicao']) if reg['alimentos_refeicao'] else []} for reg in registros]


def carregar_todos_usuarios_original(db_path):
    """Cópia de carregar_todos_usuarios de logica.py"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, email, role, is_active FROM users")
    usuarios = cursor.fetchall()
    return [dict(usuario) for usuario in usuarios]


def carregar_pacientes_original(db_path):
    """Cópia de carregar_pacientes de logica.py"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT id, username FROM users WHERE role = 'paciente'")
    return cursor.fetchall()


# ===== Batch 3: cópias de app.py / utilitários =====
from datetime import datetime as _dt

def format_datetime_original(value, format_string='%d/%m/%Y às %H:%M'):
    """Filtro Jinja original de format_datetime (arquivo app.py)."""
    if isinstance(value, _dt):
        return value.strftime(format_string)
    if isinstance(value, str):
        DB_FORMAT = '%Y-%m-%d %H:%M:%S'
        try:
            dt_obj = _dt.strptime(value, DB_FORMAT)
            return dt_obj.strftime(format_string)
        except (ValueError, TypeError):
            return value
    return value


def excluir_alimento_original(id, current_user, db_manager, flash, url_for, redirect):
    """Simplified copy of excluir_alimento route from app.py."""
    if not (current_user.is_admin or current_user.role == 'secretario'):
        flash('Acesso não autorizado.', 'danger')
        return redirect(url_for('alimentos'))

    sucesso = db_manager.excluir_alimento(id)
    if sucesso:
        flash('Alimento excluído com sucesso!', 'success')
    else:
        flash('Erro ao excluir o alimento.', 'danger')
    return redirect(url_for('alimentos'))


def editar_alimento_original(id, db_manager, AlimentoForm, flash, url_for, redirect, render_template, current_user):
    """Simplified copy of editar_alimento route from app.py."""
    alimento = db_manager.carregar_alimento_por_id(id)
    if not alimento:
        flash('Alimento não encontrado.', 'danger')
        return redirect(url_for('alimentos'))
    form = AlimentoForm()
    if form.validate_on_submit():
        try:
            dados_atualizados = {
                'id': id,
                'alimento': getattr(form, 'alimento', getattr(form, 'nome', None)).data if (hasattr(form, 'alimento') or hasattr(form, 'nome')) else None,
                'medida_caseira': form.medida_caseira.data,
                'peso': getattr(form, 'peso', getattr(form, 'peso_g', None)).data if (hasattr(form, 'peso') or hasattr(form, 'peso_g')) else None,
                'carbs': getattr(form, 'carbs', getattr(form, 'carbs_100g', None)).data if (hasattr(form, 'carbs') or hasattr(form, 'carbs_100g')) else None,
                'kcal': getattr(form, 'kcal', None).data if hasattr(form, 'kcal') else None,
            }
            if db_manager.atualizar_alimento(dados_atualizados):
                flash('Alimento atualizado com sucesso!', 'success')
                return redirect(url_for('alimentos'))
            else:
                flash('Erro: Nenhuma alteração salva ou erro no banco de dados.', 'danger')
        except Exception:
            flash('Erro interno ao processar formulário.', 'danger')
    return render_template('editar_alimento.html', alimento=alimento, form=form)


def get_float_or_none_original(request, key):
    value = request.form.get(key)
    if not value:
        return None
    try:
        return float(value.replace(',', '.'))
    except ValueError:
        return None


def get_int_or_none_original(request, key):
    value = request.form.get(key)
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def buscar_alimentos_por_nome_original(db, nome):
    """Fallback copy to search foods by name using existing db methods."""
    # If db has buscar_alimentos, prefer it; otherwise try carregar_alimentos and filter
    if hasattr(db, 'buscar_alimentos'):
        return db.buscar_alimentos(nome)
    alimentos = db.carregar_alimentos() if hasattr(db, 'carregar_alimentos') else []
    nome = nome.lower()
    return [a for a in alimentos if nome in a.get('ALIMENTO', '').lower()]
