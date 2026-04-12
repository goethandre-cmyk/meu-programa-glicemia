import sqlite3
from datetime import datetime


def criar_paciente_e_ficha_inicial_original(get_db_connection, paciente_data, medico_id, anamnese_data):
    conn = get_db_connection()
    try:
        cursor = conn.execute(
            """
            INSERT INTO users (
                username, password_hash, role, email, nome_completo, data_nascimento, 
                sexo, medico_id, telefone, razao_ic, fator_sensibilidade
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                paciente_data['username'],
                paciente_data['password_hash'],
                'paciente',
                paciente_data.get('email'),
                paciente_data.get('nome_completo'),
                paciente_data.get('data_nascimento'),
                paciente_data.get('sexo'),
                medico_id,
                paciente_data.get('telefone'),
                paciente_data.get('razao_ic', 1.0),
                paciente_data.get('fator_sensibilidade', 1.0)
            )
        )
        paciente_id = cursor.lastrowid

        conn.execute(
            """
            INSERT INTO ficha_medica (
                user_id, medico_id, data_registro, tipo_diabetes, data_diagnostico,
                historico_familiar, outras_comorbidades
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                paciente_id,
                medico_id,
                datetime.now().isoformat(),
                anamnese_data.get('tipo_diabetes'),
                anamnese_data.get('data_diagnostico'),
                anamnese_data.get('historico_familiar'),
                anamnese_data.get('outras_comorbidades')
            )
        )

        conn.execute(
            "INSERT OR IGNORE INTO vinculos_medico_paciente (medico_id, paciente_id) VALUES (?, ?)",
            (medico_id, paciente_id)
        )

        conn.commit()
        return True

    except sqlite3.IntegrityError as e:
        conn.rollback()
        return False
    except Exception:
        conn.rollback()
        return False
    finally:
        try:
            conn.close()
        except Exception:
            pass


def salvar_parametros_paciente_original(get_db_connection, paciente_id, ric_manha, ric_almoco, ric_jantar, ric_noite, fsi_manha, fsi_almoco, fsi_jantar, fsi_noite, meta_glicemia, alterado_por_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    historico_updates = []

    novos_valores = {
        'ric_manha': ric_manha,
        'ric_almoco': ric_almoco,
        'ric_jantar': ric_jantar,
        'ric_noite': ric_noite,
        'fsi_manha': fsi_manha,
        'fsi_almoco': fsi_almoco,
        'fsi_jantar': fsi_jantar,
        'fsi_noite': fsi_noite,
        'meta_glicemia': meta_glicemia,
    }

    try:
        colunas = list(novos_valores.keys())
        query_select = f"SELECT {', '.join(colunas)} FROM users WHERE id = ? AND role = 'paciente'"
        cursor.execute(query_select, (paciente_id,))
        valores_atuais_db = cursor.fetchone()

        if not valores_atuais_db:
            return False

        valores_atuais = dict(zip(colunas, valores_atuais_db))
        data_registro = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        for campo, novo_valor in novos_valores.items():
            valor_atual = valores_atuais.get(campo)
            valor_atual_num = float(valor_atual) if valor_atual is not None else 0
            novo_valor_num = float(novo_valor) if novo_valor is not None and novo_valor != '' else 0
            if valor_atual_num != novo_valor_num:
                historico_updates.append((
                    paciente_id,
                    alterado_por_id,
                    campo,
                    valor_atual,
                    novo_valor_num,
                    data_registro
                ))

        if historico_updates:
            query_update = """
                UPDATE users
                SET ric_manha = ?, ric_almoco = ?, ric_jantar = ?, ric_noite = ?, 
                    fsi_manha = ?, fsi_almoco = ?, fsi_jantar = ?, fsi_noite = ?, 
                    meta_glicemia = ?
                WHERE id = ? AND role = 'paciente';
            """

            params_update = (
                ric_manha, ric_almoco, ric_jantar, ric_noite,
                fsi_manha, fsi_almoco, fsi_jantar, fsi_noite,
                meta_glicemia,
                paciente_id
            )

            cursor.execute(query_update, params_update)

            sql_historico = """
                INSERT INTO historico_parametros 
                (paciente_id, alterado_por_id, campo, valor_anterior, novo_valor, data_registro)
                VALUES (?, ?, ?, ?, ?, ?)
            """
            cursor.executemany(sql_historico, historico_updates)

        conn.commit()
        return True

    except Exception:
        if conn:
            conn.rollback()
        return False
    finally:
        try:
            conn.close()
        except Exception:
            pass


def verificar_vinculo_medico_paciente_original(get_db_connection, medico_id, paciente_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 1 
            FROM users 
            WHERE id = ? AND medico_id = ?
        """, (paciente_id, medico_id))
        vinculo_existe = cursor.fetchone() is not None
        conn.close()
        return vinculo_existe
    except Exception:
        return False


def obter_todos_pacientes_original(get_db_connection):
    conn = get_db_connection()
    cursor = conn.cursor()
    query = """
    SELECT 
        id, 
        username, 
        nome_completo, 
        razao_ic, 
        fator_sensibilidade,
        meta_glicemia 
    FROM 
        users
    WHERE 
        role = 'paciente';
    """
    cursor.execute(query)
    colunas = [col[0] for col in cursor.description]
    pacientes = [dict(zip(colunas, row)) for row in cursor.fetchall()]
    conn.close()
    return pacientes


def obter_todos_pacientes_com_parametros_original(get_db_connection):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        query = """
            SELECT id, username, nome_completo, medico_id, 
                ric_manha, ric_almoco, ric_jantar,
                fator_sensibilidade, meta_glicemia
            FROM users
            WHERE role = 'paciente'
            ORDER BY nome_completo ASC;
        """
        cursor.execute(query)
        pacientes = [dict(row) for row in cursor.fetchall()]
        return pacientes
    except Exception:
        return []
    finally:
        try:
            conn.close()
        except Exception:
            pass


def salvar_log_acao_original(get_db_connection, acao, usuario):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO logs_acao (data_hora, acao, usuario) VALUES (?, ?, ?)", 
                    (datetime.now().isoformat(), acao, usuario))
    conn.commit()
    try:
        conn.close()
    except Exception:
        pass
    return True


def get_user_id_by_username_original(get_db_connection, username):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
    user_id = cursor.fetchone()
    conn.close()
    return user_id[0] if user_id else None


def contar_pacientes_em_alerta_original(get_db_connection):
    conn = get_db_connection()
    cursor = conn.cursor()
    limite_tempo = datetime.now() - timedelta(hours=48)
    limite_tempo_str = limite_tempo.strftime('%Y-%m-%d %H:%M:%S')
    HIPOGLICEMIA = 70
    HIPERGLICEMIA = 250
    try:
        query = """
            SELECT COUNT(DISTINCT paciente_id) 
            FROM registros
            WHERE timestamp >= ? 
            AND (glicemia < ? OR glicemia > ?);
        """
        cursor.execute(query, (limite_tempo_str, HIPOGLICEMIA, HIPERGLICEMIA))
        count = cursor.fetchone()[0]
        return count
    except Exception:
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def contar_registros_24h_original(get_db_connection):
    conn = get_db_connection()
    cursor = conn.cursor()
    limite_tempo = datetime.now() - timedelta(hours=24)
    limite_tempo_str = limite_tempo.strftime('%Y-%m-%d %H:%M:%S')
    try:
        query = """
            SELECT COUNT(*) 
            FROM registros
            WHERE timestamp >= ?;
        """
        cursor.execute(query, (limite_tempo_str,))
        count = cursor.fetchone()[0]
        return count
    except Exception:
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass
