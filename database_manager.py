import json
import os
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

class DatabaseManager:
    def __init__(self, db_path='glicemia.json'):
        # Pega o diretório do arquivo atual (database_manager.py)
        base_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Cria o caminho completo para a pasta 'data' dentro do seu projeto
        db_folder = os.path.join(base_dir, 'data')
        
        # Cria a pasta 'data' se ela não existir
        os.makedirs(db_folder, exist_ok=True)
        
        # Define o caminho completo para o arquivo glicemia.json
        self.db_path = os.path.join(db_folder, db_path)
        
        # Linha para verificar o caminho final, que você pode apagar depois
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
        return [user for user in self.db['users'] if user['role'] == 'user']
        
    def medico_tem_acesso_a_paciente(self, medico_id, paciente_id):
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