# models.py

from flask_login import UserMixin
from datetime import datetime

class User(UserMixin):
    """
    Modelo de Usuário para integração com Flask-Login e armazenamento de dados.
    Contém os dados básicos e as propriedades de checagem de papel (role).
    """
    def __init__(self, id, username, password_hash, role='user', email=None, 
                 razao_ic=1.0, fator_sensibilidade=1.0, data_nascimento=None, 
                 sexo=None, meta_glicemia=None): # <-- Adicionado 'meta_glicemia' aqui
        
        self.id = id
        self.username = username
        self.password_hash = password_hash
        # Armazena a role em minúsculas para consistência em toda a aplicação
        self.role = role.lower() 
        self.email = email
        self.razao_ic = razao_ic
        self.fator_sensibilidade = fator_sensibilidade
        self.data_nascimento = data_nascimento
        self.sexo = sexo
        self.meta_glicemia = meta_glicemia  # <-- Atribuição do atributo
        
    def get_id(self):
        # Implementação obrigatória para Flask-Login
        return str(self.id)
        
    @property
    def is_medico(self):
        return self.role == 'medico'

    @property
    def is_admin(self):
        return self.role == 'admin'

    @property
    def is_secretario(self):
        # Propriedade adicionada explicitamente
        return self.role == 'secretario'

    @property
    def is_paciente(self):
        # Mantendo 'user' por compatibilidade
        return self.role == 'paciente' or self.role == 'user' 

    @property
    def is_cuidador(self):
        return self.role == 'cuidador'

# Fim de models.py