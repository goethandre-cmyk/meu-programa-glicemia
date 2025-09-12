# database_manager.py
import sqlite3
from datetime import datetime
import json

class DatabaseManager:
    """
    Gerencia a conexão e as operações do banco de dados SQLite.
    """
    def __init__(self, db_path='glicemia.db'):
        self.db_path = db_path
        self._setup_db()

    def _get_connection(self):
        """Retorna uma conexão com o banco de dados."""
        return sqlite3.connect(self.db_path)

    def _setup_db(self):
        """
        Cria as tabelas `usuarios` e `registros` se não existirem.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Tabela de usuários
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                email TEXT,
                role TEXT DEFAULT 'user',
                data_nascimento TEXT,
                sexo TEXT,
                razao_ic REAL,
                fator_sensibilidade REAL,
                meta_glicemia REAL
            )
        ''')

        # Tabela de registros
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS registros (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                data_hora TEXT,
                tipo TEXT,
                valor REAL,
                descricao TEXT,
                refeicao TEXT,
                alimentos_refeicao TEXT,  -- Armazenado como JSON string
                total_carbs REAL,
                total_calorias REAL,
                observacoes TEXT,
                FOREIGN KEY (user_id) REFERENCES usuarios(id)
            )
        ''')
        
        # Tabela de logs
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY,
                timestamp TEXT,
                acao TEXT,
                usuario TEXT
            )
        ''')

        conn.commit()
        conn.close()

    def salvar_usuario(self, usuario):
        """Salva um novo usuário ou atualiza um existente."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Busca o ID do usuário, se ele já existir
        cursor.execute("SELECT id FROM usuarios WHERE username = ?", (usuario['username'],))
        user_id = cursor.fetchone()

        if user_id:
            # Atualiza o usuário existente
            cursor.execute('''
                UPDATE usuarios SET password_hash=?, email=?, role=?, data_nascimento=?,
                sexo=?, razao_ic=?, fator_sensibilidade=?, meta_glicemia=?
                WHERE username=?
            ''', (
                usuario['password_hash'], usuario.get('email'), usuario.get('role'),
                usuario.get('data_nascimento'), usuario.get('sexo'), usuario.get('razao_ic'),
                usuario.get('fator_sensibilidade'), usuario.get('meta_glicemia'), usuario['username']
            ))
        else:
            # Insere um novo usuário
            cursor.execute('''
                INSERT INTO usuarios (username, password_hash, email, role, data_nascimento, sexo, razao_ic, fator_sensibilidade, meta_glicemia)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                usuario['username'], usuario['password_hash'], usuario.get('email'),
                usuario.get('role', 'user'), usuario.get('data_nascimento'), usuario.get('sexo'),
                usuario.get('razao_ic'), usuario.get('fator_sensibilidade'), usuario.get('meta_glicemia')
            ))
        
        conn.commit()
        conn.close()

    def carregar_usuario(self, username):
        """Carrega um único usuário pelo nome de usuário."""
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM usuarios WHERE username=?", (username,))
        usuario = cursor.fetchone()
        conn.close()
        
        if usuario:
            # Converte o objeto Row em um dicionário
            return dict(usuario)
        return None

    def carregar_usuarios(self):
        """Carrega todos os usuários."""
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM usuarios")
        usuarios = cursor.fetchall()
        conn.close()
        
        # Converte a lista de objetos Row em uma lista de dicionários
        return [dict(row) for row in usuarios]

    def excluir_usuario(self, username):
        """Exclui um usuário do banco de dados."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM usuarios WHERE username=?", (username,))
        conn.commit()
        conn.close()
    
    def salvar_registro(self, registro):
        """Salva um novo registro no banco de dados."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO registros (user_id, data_hora, tipo, valor, descricao, refeicao, alimentos_refeicao, total_carbs, total_calorias, observacoes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            registro['user_id'], registro['data_hora'], registro['tipo'], registro['valor'],
            registro['descricao'], registro.get('refeicao'), json.dumps(registro.get('alimentos_refeicao')),
            registro.get('total_carbs'), registro.get('total_calorias'), registro.get('observacoes')
        ))
        conn.commit()
        conn.close()

    def carregar_registros(self, user_id=None):
        """Carrega registros de um usuário específico ou todos os registros."""
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = "SELECT * FROM registros"
        params = ()
        
        if user_id:
            query += " WHERE user_id = ?"
            params = (user_id,)
        
        query += " ORDER BY data_hora DESC"
        
        cursor.execute(query, params)
        registros = cursor.fetchall()
        conn.close()
        
        lista_registros = []
        for row in registros:
            reg = dict(row)
            # Converte a string JSON de volta para uma lista/dicionário
            if reg.get('alimentos_refeicao'):
                reg['alimentos_refeicao'] = json.loads(reg['alimentos_refeicao'])
            
            # Converte a string de data/hora para um objeto datetime
            if reg.get('data_hora'):
                reg['data_hora'] = datetime.fromisoformat(reg['data_hora'])
            
            lista_registros.append(reg)
            
        return lista_registros

    def excluir_registro(self, registro_id):
        """Exclui um registro pelo seu ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM registros WHERE id=?", (registro_id,))
        conn.commit()
        conn.close()

    def atualizar_registro(self, registro):
        """Atualiza um registro existente."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE registros SET valor=?, tipo=?, descricao=?, refeicao=?,
            alimentos_refeicao=?, total_carbs=?, total_calorias=?, observacoes=?
            WHERE id=?
        ''', (
            registro['valor'], registro['tipo'], registro['descricao'],
            registro.get('refeicao'), json.dumps(registro.get('alimentos_refeicao')),
            registro.get('total_carbs'), registro.get('total_calorias'),
            registro.get('observacoes'), registro['id']
        ))
        conn.commit()
        conn.close()
    
    def salvar_log_acao(self, acao, usuario):
        """Salva um log de ação no banco de dados."""
        conn = self._get_connection()
        cursor = conn.cursor()
        timestamp = datetime.now().isoformat()
        cursor.execute('''
            INSERT INTO logs (timestamp, acao, usuario)
            VALUES (?, ?, ?)
        ''', (timestamp, acao, usuario))
        conn.commit()
        conn.close()
