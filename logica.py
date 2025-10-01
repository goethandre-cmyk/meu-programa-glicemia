# Mantenha o restante do seu código intacto
import sqlite3
from datetime import datetime, timedelta
import bcrypt
import json
import os

class DatabaseManager:
    # ... (o restante da sua classe DatabaseManager) ...
    def __init__(self, db_path='app.db'):
        self.db_path = db_path
        self.inicializar_db()

    
    
    def salvar_usuario(self, username, password_hash, role='simples', email=None, data_nascimento=None, sexo=None, razao_ic=None, fator_sensibilidade=None, meta_glicemia=None):
        """Salva um novo usuário no banco de dados."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO usuarios (username, password_hash, email, role, data_nascimento, sexo, razao_ic, fator_sensibilidade, meta_glicemia)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (username, password_hash, email, role, data_nascimento, sexo, razao_ic, fator_sensibilidade, meta_glicemia))
                conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def carregar_usuario(self, username):
        """Carrega um usuário pelo nome de usuário."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM usuarios WHERE username = ?", (username,))
            usuario = cursor.fetchone()
            return dict(usuario) if usuario else None

    def carregar_usuario_por_id(self, user_id):
        """Carrega um usuário pelo ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM usuarios WHERE id = ?", (user_id,))
            usuario = cursor.fetchone()
            return dict(usuario) if usuario else None

    def atualizar_perfil_usuario(self, username, dados_perfil):
        """Atualiza o perfil de um usuário com novos dados."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            updates = []
            values = []
            for key, value in dados_perfil.items():
                if value is not None:
                    updates.append(f"{key} = ?")
                    values.append(value)

            if updates:
                sql = f"UPDATE usuarios SET {', '.join(updates)} WHERE username = ?"
                values.append(username)
                cursor.execute(sql, values)
                conn.commit()
                return True
            return False

    def salvar_log_acao(self, username, acao):
        """Salva uma ação do usuário na tabela de logs."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO log_acoes (username, acao) VALUES (?, ?)", (username, acao))
                conn.commit()
        except sqlite3.Error as e:
            print(f"Erro ao salvar log de ação: {e}")

    def carregar_todos_usuarios(self):
        """Carrega todos os usuários do banco de dados, excluindo a senha."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT id, username, email, role, is_active FROM usuarios")
            usuarios = cursor.fetchall()
            return [dict(usuario) for usuario in usuarios]

    def excluir_usuario(self, username):
        """Exclui um usuário e todos os seus dados relacionados."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Obtém o ID do usuário para exclusão em cascata
                cursor.execute("SELECT id FROM usuarios WHERE username = ?", (username,))
                user_id = cursor.fetchone()
                
                if user_id:
                    user_id = user_id[0]
                    
                    # Exclui registros relacionados (em cascata manual)
                    cursor.execute("DELETE FROM registros WHERE user_id = ?", (user_id,))
                    cursor.execute("DELETE FROM fichas_medicas WHERE paciente_id = ?", (user_id,))
                    cursor.execute("DELETE FROM agendamentos WHERE paciente_id = ?", (user_id,))
                    
                    # Exclui o usuário principal
                    cursor.execute("DELETE FROM usuarios WHERE username = ?", (username,))
                    conn.commit()
                    return True
            return False
        except sqlite3.Error as e:
            print(f"Erro ao excluir o usuário: {e}")
            return False

    def buscar_alimentos_por_nome(self, nome):
        return self.db_manager.buscar_alimentos(nome)

    def salvar_registro(self, user_id, tipo, valor, carboidratos, observacoes, alimentos_refeicao, data_hora):
        """Salva um novo registro no banco de dados, incluindo a lista de alimentos."""
        # Converte a lista de alimentos para uma string JSON antes de salvar
        alimentos_json = json.dumps(alimentos_refeicao, ensure_ascii=False)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO registros (user_id, tipo, valor, carboidratos, observacoes, alimentos_refeicao, data_hora)
                VALUES (?, ?, ?, ?, ?, ?, ?);
            """, (user_id, tipo, valor, carboidratos, observacoes, alimentos_json, data_hora))
            conn.commit()
            return cursor.lastrowid
    
    def atualizar_registro(self, id, tipo, valor, carboidratos, observacoes, alimentos_refeicao, data_hora):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Converte a lista de alimentos para uma string JSON antes de salvar
                alimentos_json = json.dumps(alimentos_refeicao, ensure_ascii=False)
                
                cursor.execute(
                    "UPDATE registros SET tipo = ?, valor = ?, carboidratos = ?, observacoes = ?, alimentos_refeicao = ?, data_hora = ? WHERE id = ?",
                    (tipo, valor, carboidratos, observacoes, alimentos_json, data_hora, id)
                )
                conn.commit()
            return True
        except sqlite3.OperationalError as e:
            print(f"Erro no banco de dados: {e}")
            return False

    def carregar_registros_por_usuario(self, username):
        """Carrega todos os registros de um usuário específico."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    r.*, 
                    u.username 
                FROM registros r
                JOIN usuarios u ON r.user_id = u.id
                WHERE u.username = ?
                ORDER BY r.data_hora DESC;
            """, (username,))
            registros = cursor.fetchall()
            # Converte a string JSON de alimentos para uma lista Python
            return [
                {**dict(reg), 'alimentos_refeicao': json.loads(reg['alimentos_refeicao']) if reg['alimentos_refeicao'] else []}
                for reg in registros
            ]

    def excluir_registro(self, id):
        """Exclui um registro pelo ID."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM registros WHERE id = ?", (id,))
            conn.commit()
            return cursor.rowcount > 0

    def encontrar_registro_por_id(self, id):
        """Encontra um registro pelo ID, incluindo o nome de usuário e convertendo a data."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = """
            SELECT r.*, u.username
            FROM registros r
            JOIN usuarios u ON r.user_id = u.id
            WHERE r.id = ?
            """
            
            cursor.execute(query, (id,))
            registro = cursor.fetchone()
            
            if registro:
                registro_dict = dict(registro)
                
                # Converte a string de data para um objeto datetime
                if isinstance(registro_dict.get('data_hora'), str):
                    try:
                        registro_dict['data_hora'] = datetime.fromisoformat(registro_dict['data_hora'])
                    except (ValueError, TypeError):
                        pass # Se a conversão falhar, mantém a string
                
                # Converte a string JSON de alimentos para uma lista de Python
                if isinstance(registro_dict.get('alimentos_refeicao'), str):
                    try:
                        registro_dict['alimentos_refeicao'] = json.loads(registro_dict['alimentos_refeicao'])
                    except (json.JSONDecodeError, TypeError):
                        registro_dict['alimentos_refeicao'] = []
                
                return registro_dict
            
            return None

    def carregar_pacientes_do_medico(self, medico_id):
        """Carrega todos os usuários com o papel 'paciente' associados a um médico."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # TODO: Implementar a lógica de associação de pacientes a médicos, 
            # por enquanto, retorna todos os pacientes
            cursor.execute("SELECT id, username, email FROM usuarios WHERE role = 'paciente'")
            pacientes = cursor.fetchall()
            return [dict(pac) for pac in pacientes]

    def carregar_pacientes(self):
        """Carrega todos os usuários com o papel 'paciente'."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT id, username FROM usuarios WHERE role = 'paciente'")
            return cursor.fetchall()

    def carregar_medicos(self):
        """Carrega todos os usuários com o papel 'medico'."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT id, username FROM usuarios WHERE role = 'medico'")
            return cursor.fetchall()

    def carregar_ficha_medica(self, paciente_id):
        """Carrega a ficha médica de um paciente."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM fichas_medicas WHERE paciente_id = ?", (paciente_id,))
            ficha = cursor.fetchone()
            return dict(ficha) if ficha else None

    def salvar_ficha_medica(self, dados):
        """Salva ou atualiza a ficha médica de um paciente."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM fichas_medicas WHERE paciente_id = ?", (dados['paciente_id'],))
            exists = cursor.fetchone()

            if exists:
                cursor.execute("""
                    UPDATE fichas_medicas
                    SET condicao_atual = ?, alergias = ?, historico_familiar = ?, medicamentos_uso = ?
                    WHERE paciente_id = ?
                """, (dados['condicao_atual'], dados['alergias'], dados['historico_familiar'], dados['medicamentos_uso'], dados['paciente_id']))
            else:
                cursor.execute("""
                    INSERT INTO fichas_medicas (paciente_id, condicao_atual, alergias, historico_familiar, medicamentos_uso)
                    VALUES (?, ?, ?, ?, ?)
                """, (dados['paciente_id'], dados['condicao_atual'], dados['alergias'], dados['historico_familiar'], dados['medicamentos_uso']))
            conn.commit()

    
    def criar_agendamento(self, paciente_id, medico_id, data_hora, observacoes):
        """Cria um novo agendamento."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO agendamentos (paciente_id, medico_id, data_hora, observacoes)
                    VALUES (?, ?, ?, ?);
                """, (paciente_id, medico_id, data_hora, observacoes))
                conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Erro ao criar agendamento: {e}")
            return False

    def carregar_agendamentos(self, medico_id=None, role=None):
        """Carrega agendamentos, filtrando por médico se aplicável."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            query = """
                SELECT 
                    a.id, a.data_hora, a.observacoes, a.status,
                    p.username as paciente_username,
                    m.username as medico_username
                FROM agendamentos a
                JOIN usuarios p ON a.paciente_id = p.id
                JOIN usuarios m ON a.medico_id = m.id
            """
            
            if role == 'medico' and medico_id:
                query += " WHERE a.medico_id = ? ORDER BY a.data_hora DESC"
                cursor.execute(query, (medico_id,))
            else:
                query += " ORDER BY a.data_hora DESC"
                cursor.execute(query)

            return cursor.fetchall()

    def carregar_agendamentos_paciente(self, paciente_username):
        """Carrega os agendamentos de um paciente específico."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    a.id, a.data_hora, a.observacoes, a.status,
                    m.username as medico_username
                FROM agendamentos a
                JOIN usuarios p ON a.paciente_id = p.id
                JOIN usuarios m ON a.medico_id = m.id
                WHERE p.username = ?
                ORDER BY a.data_hora DESC;
            """, (paciente_username,))
            return cursor.fetchall()

    def atualizar_status_agendamento(self, agendamento_id, novo_status):
        """Atualiza o status de um agendamento."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE agendamentos SET status = ? WHERE id = ?", (novo_status, agendamento_id))
            conn.commit()
            return cursor.rowcount > 0

    def obter_agendamento_por_id(self, agendamento_id):
        """Obtém um agendamento específico pelo ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM agendamentos WHERE id = ?", (agendamento_id,))
            agendamento = cursor.fetchone()
            return dict(agendamento) if agendamento else None
    
    def criar_ficha_medica_inicial(self, paciente_id):
        """Cria uma ficha médica inicial vazia para um novo paciente."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR IGNORE INTO fichas_medicas (paciente_id) VALUES (?)", (paciente_id,))
            conn.commit()

class AuthManager:
    # ... (o restante da sua classe AuthManager) ...
    def __init__(self, db_manager):
        self.db_manager = db_manager

    def salvar_usuario(self, username, password, **kwargs):
        """
        Salva um novo usuário com senha criptografada.
        Recebe a role e outros dados via kwargs.
        """
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        # Extrai a role do dicionário kwargs para evitar o erro de argumento duplicado
        role = kwargs.pop('role', 'simples')

        # Chama a função do DatabaseManager com os argumentos corretos
        sucesso = self.db_manager.salvar_usuario(
            username=username,
            password_hash=password_hash,
            role=role,
            **kwargs
        )

        if sucesso:
            # Se for um paciente, cria a ficha médica vazia
            if role == 'paciente':
                usuario = self.db_manager.carregar_usuario(username)
                if usuario:
                    self.db_manager.criar_ficha_medica_inicial(usuario['id'])
            return True, "Usuário cadastrado com sucesso."
        else:
            return False, "Nome de usuário já existe. Por favor, escolha outro."

    def verificar_login(self, username, password):
        """Verifica as credenciais do usuário."""
        usuario = self.db_manager.carregar_usuario(username)
        if usuario:
            # Verifica se a senha fornecida corresponde ao hash armazenado
            if bcrypt.checkpw(password.encode('utf-8'), usuario['password_hash'].encode('utf-8')):
                return usuario, "Login bem-sucedido!"
        return None, "Nome de usuário ou senha incorretos."

    def atualizar_perfil_usuario(self, username, dados_perfil, nova_senha=None):
        """Atualiza o perfil de um usuário, incluindo a senha se for fornecida."""
        if nova_senha:
            # Criptografa a nova senha antes de atualizar
            password_hash = bcrypt.hashpw(nova_senha.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            dados_perfil['password_hash'] = password_hash
        
        return self.db_manager.atualizar_perfil_usuario(username, dados_perfil)
        
    def carregar_todos_usuarios(self):
        """Carrega todos os usuários do banco de dados (função delegada)."""
        return self.db_manager.carregar_todos_usuarios()

# Mantenha o restante do seu código intacto
# Exemplo de como a classe AppCore deve ficar

class AppCore:
    def __init__(self, db_manager):
        self.db_manager = db_manager
        # AQUI, o método é chamado, mas o retorno precisa ser ajustado
        self.alimentos_db = self._carregar_alimentos_json()

    def _carregar_alimentos_json(self):
        """Carrega os dados de alimentos de um arquivo JSON."""
        filepath = 'data/alimentos.json'

        print(f"DEBUG: Procurando o arquivo em: {os.path.abspath(filepath)}")

        if not os.path.exists(filepath):
            print(f"AVISO: O arquivo '{filepath}' NÃO foi encontrado. A busca por alimentos não funcionará.")
            return {"alimentos": []}

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                dados = json.load(f)
                
                # Se o arquivo JSON for uma lista, o envolvemos em um dicionário
                if isinstance(dados, list):
                    print(f"INFO: O arquivo '{filepath}' foi carregado com sucesso. Total de registros: {len(dados)}")
                    return {"alimentos": dados}
                # Se já for um dicionário com a chave 'alimentos', retorna-o
                elif isinstance(dados, dict) and "alimentos" in dados:
                    print(f"INFO: O arquivo '{filepath}' foi carregado com sucesso. Total de registros: {len(dados['alimentos'])}")
                    return dados
                else:
                    # Se não for uma lista ou um dicionário válido, o formato está incorreto.
                    print(f"ERRO: O arquivo '{filepath}' tem um formato inesperado. Esperada uma lista de alimentos ou um dicionário com a chave 'alimentos'.")
                    return {"alimentos": []}
                    
        except (IOError, json.JSONDecodeError) as e:
            print(f"ERRO: Não foi possível ler o arquivo '{filepath}'. Ele pode estar corrompido ou com formato inválido. Erro: {e}")
            return {"alimentos": []}

    def salvar_alimento_json(self, novo_alimento):
        """Salva um novo alimento no arquivo JSON."""
        # Verifica se o alimento já existe
        for alimento in self.alimentos_db["alimentos"]:
            if alimento["ALIMENTO"].lower() == novo_alimento["ALIMENTO"].lower():
                return False  # Alimento já existe, não salva
        
        self.alimentos_db["alimentos"].append(novo_alimento)
        try:
            # Salva no arquivo original
            with open('data/alimentos.json', 'w', encoding='utf-8') as f:
                json.dump(self.alimentos_db, f, ensure_ascii=False, indent=4)
            return True
        except IOError:
            return False

    def pesquisar_alimentos(self, termo):
        """Busca alimentos na base de dados que correspondem a um termo."""
        termo = termo.lower()
        resultados = [
            alimento for alimento in self.alimentos_db["alimentos"]
            if termo in alimento["ALIMENTO"].lower() or termo in alimento.get("MEDIDA CASEIRA", "").lower()
        ]
        return resultados
    
    def carregar_todos_alimentos(self):
        """
        Carrega todos os alimentos do arquivo JSON.
        """
        file_path = 'data/alimentos.json'  # Verifique se o caminho do seu arquivo está correto
        if not os.path.exists(file_path):
            return []
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get("alimentos", [])

    def listar_alimentos_simples(self):
        """
        Carrega a lista de alimentos e retorna uma lista simples de nomes.
        Útil para preencher caixas de seleção ou autocompletar no frontend.
        """
        try:
            alimentos_completos = self.carregar_todos_alimentos()
            lista_simples = [alimento['ALIMENTO'] for alimento in alimentos_completos]
            return lista_simples
        except Exception as e:
            print(f"Erro ao listar alimentos simples: {e}")
            return []
        
    def adicionar_registro(self, user_id, dados):
        """
        Adiciona um novo registro de glicemia ou refeição no banco de dados.
        Recebe o ID do usuário e um dicionário de dados.
        """
        try:
            # Extrai os dados do dicionário, usando .get() para evitar erros
            tipo = dados.get('tipo')
            valor = dados.get('valor')
            carboidratos = dados.get('carboidratos')
            observacoes = dados.get('observacoes')
            alimentos_refeicao = dados.get('alimentos_refeicao', [])  # Usa uma lista vazia se não houver
            data_hora = dados.get('data_hora')

            # Chama o método da classe DatabaseManager para salvar o registro
            registro_id = self.db_manager.salvar_registro(
                user_id=user_id,
                tipo=tipo,
                valor=valor,
                carboidratos=carboidratos,
                observacoes=observacoes,
                alimentos_refeicao=alimentos_refeicao,
                data_hora=data_hora
            )

            # Salva um log de ação no banco de dados
            if tipo == 'Glicemia':
                self.salvar_log_acao(f"Registro de glicemia (ID: {registro_id}) adicionado por {user_id}", user_id)
            elif tipo == 'Refeição':
                self.salvar_log_acao(f"Registro de refeição (ID: {registro_id}) adicionado por {user_id}", user_id)

            return True, "Registro adicionado com sucesso!"
        except Exception as e:
            print(f"Erro ao adicionar registro: {e}")
            return False, "Erro ao adicionar o registro. Por favor, tente novamente."
    
    def atualizar_registro(self, registro_id, tipo, dados_registro):
        """
        Atualiza um registro existente no banco de dados.
        Recebe um dicionário com os dados a serem atualizados.
        """
        alimentos_refeicao = dados_registro.get('alimentos_refeicao', [])
        
        return self.db_manager.atualizar_registro(
            id=registro_id, 
            tipo=tipo,
            valor=dados_registro.get('valor'), 
            carboidratos=dados_registro.get('total_carbs'), 
            observacoes=dados_registro.get('observacoes'), 
            alimentos_refeicao=alimentos_refeicao,
            data_hora=dados_registro.get('data_hora')
        )
    
    def mostrar_registros(self, usuario_filtro=None):
        """Carrega e formata os registros de glicemia e refeição."""
        registros = self.db_manager.carregar_registros_por_usuario(usuario_filtro)
        for reg in registros:
            reg['data_hora'] = datetime.fromisoformat(reg['data_hora'])
        return registros

    def encontrar_registro(self, id):
        """Encontra e retorna um registro pelo ID."""
        return self.db_manager.encontrar_registro_por_id(id)

    def excluir_registro(self, id):
        """Exclui um registro específico do banco de dados."""
        return self.db_manager.excluir_registro(id)
    
    def get_resumo_dashboard(self, username):
        """Retorna dados de resumo para o dashboard do usuário paciente/simples."""
        registros = self.db_manager.carregar_registros_por_usuario(username)
        # TODO: Implementar a lógica de resumo
        return {}

    def get_resumo_dashboard_medico(self):
        """Retorna dados de resumo para o dashboard do médico."""
        todos_usuarios = self.db_manager.carregar_todos_usuarios()
        total_pacientes = sum(1 for u in todos_usuarios if u['role'] == 'paciente')
        # TODO: Implementar lógica de pacientes ativos
        return {
            'total_pacientes': total_pacientes,
            'pacientes_ativos': 0  # Placeholder
        }

    def salvar_log_acao(self, acao, username=None):
        """Salva uma ação no log, usando o username da sessão se não for fornecido."""
        self.db_manager.salvar_log_acao(username, acao)

    def atualizar_status_agendamento(self, agendamento_id, novo_status):
        """Atualiza o status de um agendamento."""
        return self.db_manager.atualizar_status_agendamento(agendamento_id, novo_status)

# A sua função processar_dados_registro do app.py
def processar_dados_registro(form_data):
    """Processa os dados do formulário de registro."""
    
    # 1. Pegar os valores de forma segura, tratando a ausência de campos
    valor_glicemia = form_data.get('valor_glicemia')
    data_hora = form_data.get('data_hora')
    refeicao = form_data.get('refeicao')
    observacoes = form_data.get('observacoes')
    
    # Este é o campo oculto que o JavaScript atualiza no HTML
    total_carbs_str = form_data.get('total_carbs_refeicao') # Nome corrigido para 'total_carbs_refeicao'
    alimentos_refeicao_str = form_data.get('alimentos_refeicao')

    # 2. Validar e converter os valores
    if not valor_glicemia:
        raise ValueError("O campo de valor da glicemia é obrigatório.")

    # Converte o valor da glicemia para float
    valor_glicemia_float = float(valor_glicemia.replace(',', '.'))
    
    # Converte o total de carboidratos para float, tratando possíveis erros
    total_carbs = 0.0
    if total_carbs_str:
        total_carbs = float(total_carbs_str.replace(',', '.'))
    
    # Tenta carregar a string JSON. Se falhar, assume uma lista vazia.
    try:
        alimentos_refeicao = json.loads(alimentos_refeicao_str)
    except (json.JSONDecodeError, TypeError):
        alimentos_refeicao = []

    # 3. Retornar um dicionário de dados processados
    dados_processados = {
        'valor': valor_glicemia_float,
        'data_hora': data_hora,
        'carboidratos': total_carbs,
        'observacoes': observacoes,
        'refeicao': refeicao,
        'alimentos_refeicao': alimentos_refeicao
    }
    
    return dados_processados

# --- Funções de Ajuda (utilitárias) ---
def get_cor_glicemia(valor):
    """Retorna uma classe CSS com base no valor da glicemia."""
    if valor < 70:
        return 'bg-warning text-dark'
    elif valor >= 70 and valor <= 140:
        return 'bg-success text-white'
    elif valor > 140 and valor <= 200:
        return 'bg-primary text-white'
    else:
        return 'bg-danger text-white'

def get_cor_classificacao(valor):
    """Retorna a cor para a classificação do valor de glicemia."""
    if valor < 70:
        return 'text-danger'
    elif valor >= 70 and valor <= 140:
        return 'text-success'
    elif valor > 140 and valor <= 200:
        return 'text-warning'
    else:
        return 'text-danger'

def get_status_class(valor):
    """Retorna a classe CSS para o status de glicemia."""
    if valor < 70:
        return 'status-baixa'
    elif valor >= 70 and valor <= 140:
        return 'status-normal'
    else:
        return 'status-alta'

def calcular_fator_sensibilidade(dtdi, tipo_insulina):
    """Calcula o fator de sensibilidade à insulina (FS) pela regra de 500/1800."""
    if tipo_insulina == 'rapida' and dtdi:
        return 500 / dtdi
    elif tipo_insulina == 'ultrarapida' and dtdi:
        return 1800 / dtdi
    return None

def calcular_bolus_detalhado(carboidratos, glicemia_atual, meta_glicemia, razao_ic, fator_sensibilidade):
    """Calcula a dose de insulina (bolus) com correção."""
    if not all([carboidratos, glicemia_atual, meta_glicemia, razao_ic, fator_sensibilidade]):
        return None
    
    # Bolus para carboidratos
    bolus_carbs = carboidratos / razao_ic

    # Fator de correção
    fator_correcao = (glicemia_atual - meta_glicemia) / fator_sensibilidade

    # Bolus total
    bolus_total = bolus_carbs + fator_correcao
    
    return {
        'bolus_carbs': round(bolus_carbs, 2),
        'fator_correcao': round(fator_correcao, 2),
        'bolus_total': max(0, round(bolus_total, 2))  # Evita bolus negativo
    }

def processar_dados_registro(form_data):
    """
    Processa dados de formulário para registros de glicemia e refeição,
    agora compatível com as chaves do formulário HTML.
    """
    valor = float(form_data.get('valor_glicemia', 0))
    data_hora_str = form_data.get('data_hora')
    observacoes = form_data.get('observacoes', '')
    
    # A lista de alimentos já foi convertida em app.py
    alimentos_refeicao = form_data.get('alimentos_refeicao', [])
    
    try:
        data_hora = datetime.fromisoformat(data_hora_str)
    except (ValueError, TypeError):
        data_hora = datetime.now()

    total_carbs = 0
    
    # Percorre a lista de alimentos (que já é uma lista de Python)
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