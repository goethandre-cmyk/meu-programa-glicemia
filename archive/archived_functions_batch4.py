import sqlite3
from sqlite3 import Row

def carregar_usuario_original(get_db_connection, username):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    user_data = cursor.fetchone()
    try:
        conn.close()
    except Exception:
        pass
    return dict(user_data) if user_data else None


def carregar_usuario_por_username_original(get_db_connection, username):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, password_hash, role FROM users WHERE username = ?", (username,))
    user_data = cursor.fetchone()
    try:
        conn.close()
    except Exception:
        pass
    if user_data:
        id_, username_, password_hash, role = user_data
        from models import User
        return User(id=id_, username=username_, password_hash=password_hash, role=role)
    return None


def carregar_usuario_por_id_original(get_db_connection, user_id):
    conn = get_db_connection()
    user_data = conn.execute(
        "SELECT id, username, role, email, nome_completo, razao_ic, fator_sensibilidade, data_nascimento, sexo, telefone, medico_id FROM users WHERE id = ?", 
        (user_id,)
    ).fetchone()
    try:
        conn.close()
    except Exception:
        pass
    return dict(user_data) if user_data else None


def carregar_todos_os_usuarios_original(get_db_connection, perfil=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    query = "SELECT id, username, role FROM users"
    params = ()
    if perfil:
        query += " WHERE role = ?"
        params = (perfil,)
    cursor.execute(query, params)
    usuarios = cursor.fetchall()
    try:
        conn.close()
    except Exception:
        pass
    return [{'id': row[0], 'username': row[1], 'role': row[2]} for row in usuarios]


def contar_usuarios_original(get_db_connection, role=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if role:
            query = "SELECT COUNT(*) FROM users WHERE role = ?"
            cursor.execute(query, (role,))
        else:
            query = "SELECT COUNT(*) FROM users"
            cursor.execute(query)
        count = cursor.fetchone()[0]
        return count
    except Exception:
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def contar_pacientes_sem_parametros_original(get_db_connection):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        query = """
            SELECT COUNT(id) FROM users 
            WHERE role = 'paciente' 
            AND (ric_manha IS NULL OR ric_manha = 0 
                OR meta_glicemia IS NULL OR meta_glicemia = 0);
        """
        cursor.execute(query)
        count = cursor.fetchone()[0]
        return count
    except Exception:
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass
