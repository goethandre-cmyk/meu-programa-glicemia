# Importa a classe principal do Flask e outros módulos
from flask import Flask
# Importa as classes que você criou em outros arquivos
from .appgemini import DatabaseManager
from .logica import AppCore, AuthManager
# Importa a blueprint que contém as rotas da aplicação
from .appgemini import routes_bp

def create_app():
    """
    Cria e configura a instância da aplicação Flask.
    """
    # Inicializa a aplicação Flask
    app = Flask(__name__)
    # Define uma chave secreta para as sessões
    app.secret_key = 'sua_chave_secreta_aqui'

    # --- Inicialização das Camadas de Lógica e Banco de Dados ---
    # Instancia a classe que gerencia o banco de dados
    db_manager = DatabaseManager()
    
    # Instancia a classe de lógica de autenticação, passando o gerenciador do banco
    auth_manager = AuthManager(db_manager)
    
    # Instancia a classe de lógica principal, passando o gerenciador do banco e de autenticação
    app_core = AppCore(db_manager, auth_manager)

    # Armazena as instâncias nas configurações da aplicação
    # Isso permite que elas sejam acessadas por todas as rotas
    app.config['DB_MANAGER'] = db_manager
    app.config['AUTH_MANAGER'] = auth_manager
    app.config['APP_CORE'] = app_core

    # --- Registro das Rotas (Blueprints) ---
    # Registra a blueprint 'routes_bp' para que o Flask saiba quais URLs usar
    app.register_blueprint(routes_bp)

    return app

if __name__ == '__main__':
    # Se este arquivo for executado diretamente, inicia o servidor de desenvolvimento
    app = create_app()
    app.run(debug=True)