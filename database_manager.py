import json
import os
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

class DatabaseManager:
    def __init__(self, db_path='glicemia.json'):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        db_folder = os.path.join(base_dir, 'data')
        os.makedirs(db_folder, exist_ok=True)
        self.db_path = os.path.join(db_folder, db_path)
        print(f"Salvando em: {self.db_path}")
        self.db = self._load_db()

    def _load_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        if not os.path.exists(self.db_path):
            return self._create_initial_db()
        
        try:
            with open(self.db_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"Erro: O arquivo '{self.db_path}' está corrompido ou vazio. Criando um novo.")
            return self._create_initial_db()

    def _create_initial_db(self):
        initial_db = {
            'users': [],
            'registros_glicemia_refeicao': [],
            'alimentos': [],
            'medicos': [],
            'agendamentos': [],
            'logs_acao': [],
            'fichas_medicas': []
        }
        self._save_db(initial_db)
        return initial_db

    def _save_db(self, data=None):
        with open(self.db_path, 'w', encoding='utf-8') as f:
            if data:
                json.dump(data, f, indent=4)
            else:
                json.dump(self.db, f, indent=4)

    def carregar_usuario(self, username):
        for user in self.db['users']:
            if user['username'] == username:
                return user
        return None

    def carregar_usuario_por_id(self, user_id):
        for user in self.db['users']:
            if user['id'] == user_id:
                return user
        return None

    def carregar_todos_os_usuarios(self):
        return self.db['users']

    def salvar_usuario(self, user_data):
        if self.carregar_usuario(user_data['username']):
            return False

        if not self.db['users']:
            last_id = 0
        else:
            last_id = max(u['id'] for u in self.db['users'])
        
        user_data['id'] = last_id + 1
        self.db['users'].append(user_data)
        self._save_db()
        return True

    # -- O MÉTODO ATUALIZAR_USUARIO ESTAVA AQUI E FOI MOVIDO PARA DENTRO DA CLASSE --
    def atualizar_usuario(self, user_data):
        """
        Atualiza os dados de um usuário existente na base de dados.
        Recebe um dicionário com os dados do usuário, incluindo o 'id'.
        """
        user_id = user_data.get('id')
        if not user_id:
            return False

        try:
            for i, user in enumerate(self.db['users']):
                if user.get('id') == user_id:
                    self.db['users'][i].update(user_data)
                    self._save_db()
                    return True
            return False
        except Exception as e:
            print(f"Erro ao atualizar usuário: {e}")
            return False

    def salvar_registro(self, registro_data):
        last_id = max([r['id'] for r in self.db['registros_glicemia_refeicao']] + [0])
        registro_data['id'] = last_id + 1
        self.db['registros_glicemia_refeicao'].append(registro_data)
        self._save_db()
        return True
        
    def carregar_registros(self, user_id):
        return [r for r in self.db['registros_glicemia_refeicao'] if r.get('user_id') == user_id]

    def encontrar_registro(self, registro_id):
        for registro in self.db['registros_glicemia_refeicao']:
            if registro['id'] == registro_id:
                return registro
        return None
        
    def atualizar_registro(self, registro_data):
        for i, registro in enumerate(self.db['registros_glicemia_refeicao']):
            if registro['id'] == registro_data['id']:
                self.db['registros_glicemia_refeicao'][i] = registro_data
                self._save_db()
                return True
        return False

    def excluir_registro(self, registro_id):
        initial_count = len(self.db['registros_glicemia_refeicao'])
        self.db['registros_glicemia_refeicao'] = [r for r in self.db['registros_glicemia_refeicao'] if r['id'] != registro_id]
        if len(self.db['registros_glicemia_refeicao']) < initial_count:
            self._save_db()
            return True
        return False
        
    def salvar_alimento(self, alimento_data):
        last_id = max([a['id'] for a in self.db['alimentos']] + [0])
        alimento_data['id'] = last_id + 1
        self.db['alimentos'].append(alimento_data)
        self._save_db()
        return True

    def carregar_alimentos(self):
        return self.db['alimentos']
        
    def encontrar_alimento(self, alimento_id):
        for alimento in self.db['alimentos']:
            if alimento['id'] == alimento_id:
                return alimento
        return None

    def atualizar_alimento(self, alimento_data):
        for i, alimento in enumerate(self.db['alimentos']):
            if alimento['id'] == alimento_data['id']:
                self.db['alimentos'][i] = alimento_data
                self._save_db()
                return True
        return False

    def excluir_alimento(self, alimento_id):
        initial_count = len(self.db['alimentos'])
        self.db['alimentos'] = [a for a in self.db['alimentos'] if a['id'] != alimento_id]
        if len(self.db['alimentos']) < initial_count:
            self._save_db()
            return True
        return False

    def salvar_log_acao(self, acao, usuario):
        log = {
            'data_hora': str(datetime.now()),
            'acao': acao,
            'usuario': usuario
        }
        self.db['logs_acao'].append(log)
        self._save_db()
        return True
    
    def obter_pacientes_por_medico(self, medico_id):
        medico = self.carregar_usuario_por_id(medico_id)
        if not medico or medico.get('role') != 'medico':
            return []

        pacientes_vinculados_ids = medico.get('pacientes_vinculados', [])

        pacientes = []
        for user_id in pacientes_vinculados_ids:
            paciente = self.carregar_usuario_por_id(user_id)
            if paciente:
                pacientes.append(paciente)

        return pacientes
        
    def medico_tem_acesso_a_paciente(self, medico_id, paciente_id):
        return True

    def salvar_ficha_medica(self, ficha_data):
        paciente_id = ficha_data['paciente_id']
        for i, ficha in enumerate(self.db['fichas_medicas']):
            if ficha.get('paciente_id') == paciente_id:
                self.db['fichas_medicas'][i].update(ficha_data)
                self._save_db()
                return True
        
        self.db['fichas_medicas'].append(ficha_data)
        self._save_db()
        return True

    def carregar_ficha_medica(self, paciente_id):
        for ficha in self.db['fichas_medicas']:
            if ficha.get('paciente_id') == paciente_id:
                return ficha
        return None

    def carregar_agendamentos_medico(self, medico_id):
        return [a for a in self.db['agendamentos'] if a.get('medico_id') == medico_id]

    def carregar_agendamentos_paciente(self, paciente_id):
        return [a for a in self.db['agendamentos'] if a.get('paciente_id') == paciente_id]
        
    def carregar_medicos(self):
        return [user for user in self.db['users'] if user['role'] == 'medico']

    def salvar_agendamento(self, agendamento_data):
        last_id = max([a['id'] for a in self.db['agendamentos']] + [0])
        agendamento_data['id'] = last_id + 1
        self.db['agendamentos'].append(agendamento_data)
        self._save_db()
        return True

    # ---- MÉTODOS DE VINCULAÇÃO E CARREGAMENTO ESPECÍFICO ----

    def carregar_cuidadores(self):
        cuidadores = []
        for usuario in self.db['users']:
            if usuario.get('role') == 'cuidador':
                cuidadores.append(usuario)
        return cuidadores

    def vincular_cuidador_paciente(self, cuidador_username, paciente_username):
        cuidador = next((u for u in self.db['users'] if u['username'] == cuidador_username), None)
        paciente = next((u for u in self.db['users'] if u['username'] == paciente_username), None)
        if not cuidador or not paciente:
            return False
        # Corrigido: 'user' para 'paciente' para manter a consistência
        if cuidador['role'] != 'cuidador' or paciente['role'] != 'paciente':
            return False
        if 'pacientes_vinculados' not in cuidador:
            cuidador['pacientes_vinculados'] = []
        if paciente['id'] not in cuidador['pacientes_vinculados']:
            cuidador['pacientes_vinculados'].append(paciente['id'])
            self._save_db()
            return True
        return False
        
    # Corrigido: Este método foi movido e indentado para DENTRO da classe
    def vincular_paciente_medico(self, paciente_id, medico_id):
        """
        Vincula um paciente a um médico.
        """
        # Encontra o paciente e o médico pelos seus IDs
        paciente = self.carregar_usuario_por_id(paciente_id)
        medico = self.carregar_usuario_por_id(medico_id)

        # Verifica se ambos os usuários existem e se as suas roles estão corretas
        if not paciente or not medico:
            return False  # Paciente ou médico não encontrado

        if paciente.get('role') != 'paciente' or medico.get('role') != 'medico':
            return False  # As roles não correspondem ao esperado
        
        # Se o médico ainda não tiver a lista de pacientes, crie-a
        if 'pacientes_vinculados' not in medico:
            medico['pacientes_vinculados'] = []
        
        # Adiciona o ID do paciente à lista do médico, se ainda não estiver lá
        if paciente['id'] not in medico['pacientes_vinculados']:
            medico['pacientes_vinculados'].append(paciente['id'])
            
            # O método 'atualizar_usuario' já salva o arquivo
            self.atualizar_usuario(medico)
            return True
        
        return False # A vinculação já existe