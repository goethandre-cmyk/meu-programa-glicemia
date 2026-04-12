import sqlite3
import json
from datetime import datetime


def salvar_registro_original(db_path, user_id, tipo, valor, carboidratos, observacoes, alimentos_refeicao, data_hora):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    alimentos_json = json.dumps(alimentos_refeicao, ensure_ascii=False)
    cursor.execute("""
        INSERT INTO registros (user_id, tipo, valor, carboidratos, observacoes, alimentos_refeicao, data_hora)
        VALUES (?, ?, ?, ?, ?, ?, ?);
    """, (user_id, tipo, valor, carboidratos, observacoes, alimentos_json, data_hora))
    conn.commit()
    last = cursor.lastrowid
    conn.close()
    return last


def atualizar_registro_original(db_path, id, tipo, valor, carboidratos, observacoes, alimentos_refeicao, data_hora):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        alimentos_json = json.dumps(alimentos_refeicao, ensure_ascii=False)
        cursor.execute(
            "UPDATE registros SET tipo = ?, valor = ?, carboidratos = ?, observacoes = ?, alimentos_refeicao = ?, data_hora = ? WHERE id = ?",
            (tipo, valor, carboidratos, observacoes, alimentos_json, data_hora, id)
        )
        conn.commit()
        updated = cursor.rowcount
        conn.close()
        return updated > 0
    except sqlite3.OperationalError:
        try:
            conn.close()
        except Exception:
            pass
        return False


def encontrar_registro_por_id_original(db_path, id):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT r.*, u.username
        FROM registros r
        JOIN users u ON r.user_id = u.id
        WHERE r.id = ?
    """, (id,))
    registro = cursor.fetchone()
    conn.close()
    if not registro:
        return None
    registro_dict = dict(registro)
    if isinstance(registro_dict.get('alimentos_refeicao'), str):
        try:
            registro_dict['alimentos_refeicao'] = json.loads(registro_dict['alimentos_refeicao'])
        except Exception:
            registro_dict['alimentos_refeicao'] = []
    return registro_dict


def carregar_pacientes_original(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT id, username FROM users WHERE role = 'paciente'")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def carregar_medicos_original(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT id, username FROM users WHERE role = 'medico'")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def criar_agendamento_original(db_path, paciente_id, medico_id, data_hora, observacoes):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO agendamentos (paciente_id, medico_id, data_hora, observacoes)
            VALUES (?, ?, ?, ?);
        """, (paciente_id, medico_id, data_hora, observacoes))
        conn.commit()
        conn.close()
        return True
    except sqlite3.Error:
        try:
            conn.close()
        except Exception:
            pass
        return False


def carregar_agendamentos_original(db_path, medico_id=None, role=None):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    query = '''
        SELECT 
            a.id, a.data_hora, a.observacoes, a.status,
            p.username as paciente_username,
            m.username as medico_username
        FROM agendamentos a
        JOIN users p ON a.paciente_id = p.id
        JOIN users m ON a.medico_id = m.id
    '''
    if role == 'medico' and medico_id:
        query += " WHERE a.medico_id = ? ORDER BY a.data_hora DESC"
        cursor.execute(query, (medico_id,))
    else:
        query += " ORDER BY a.data_hora DESC"
        cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()
    return rows


def carregar_agendamentos_paciente_original(db_path, paciente_username):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('''
        SELECT
            a.id, a.data_hora, a.observacoes, a.status,
            m.username as medico_username
        FROM agendamentos a
        JOIN users p ON a.paciente_id = p.id
        JOIN users m ON a.medico_id = m.id
        WHERE p.username = ?
        ORDER BY a.data_hora DESC;
    ''', (paciente_username,))
    rows = cursor.fetchall()
    conn.close()
    return rows
