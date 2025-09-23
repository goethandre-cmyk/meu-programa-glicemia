# models.py
from flask_login import UserMixin

class User(UserMixin):
    def __init__(self, user_id, username, role):
        self.id = user_id
        self.username = username
        self.role = role
    
    # O Flask-Login precisa desta propriedade.
    # Se a sua classe User no AuthManager já tem um id, isso deve funcionar.
    def get_id(self):
        return str(self.id)