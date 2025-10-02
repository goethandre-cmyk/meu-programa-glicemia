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
                 sexo=None, meta_glicemia=None, 
                 # NOVOS CAMPOS ADICIONADOS AQUI:
                 nome_completo=None, telefone=None, documento=None, 
                 crm=None, cns=None, especialidade=None):
        
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
        self.meta_glicemia = meta_glicemia 
        
        # NOVAS ATRIBUIÇÕES:
        self.nome_completo = nome_completo
        self.telefone = telefone
        self.documento = documento
        self.crm = crm
        self.cns = cns
        self.especialidade = especialidade
        
    def get_id(self):
        # Implementação obrigatória para Flask-Login
        return str(self.id)
        
    @property
    def is_medico(self):
        # CORREÇÃO AQUI: Inclui o 'admin' para que ele tenha todas as permissões de médico.
        return self.role in ['medico', 'admin']

    @property
    def is_admin(self):
        return self.role == 'admin'

    @property
    def is_secretario(self):
        return self.role == 'secretario'

    @property
    def is_paciente(self):
        # Mantendo 'user' por compatibilidade
        return self.role == 'paciente' or self.role == 'user' 

    @property
    def is_cuidador(self):
        return self.role == 'cuidador'

# Fim de models.py