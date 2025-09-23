# Diário de Desenvolvimento - Nome do Projeto

### 19/09/2025 - Início do desenvolvimento

**Objetivo:** Criar um diário para registrar o progresso e as soluções em conjunto com o Gemini.

**Primeiro desafio:** Estabelecer uma rotina para documentar o trabalho.

**Conclusão:** A partir de agora, usarei este arquivo para registrar problemas, soluções e decisões importantes do projeto.
# 19/09/2025 - Refatoração Inicial: Divisão da Lógica de BD
**Problema:**
O arquivo app.py ultrapassou 700 linhas, misturando a lógica de aplicação (rotas, templates) com as operações de banco de dados, o que dificulta a depuração e manutenção do projeto.

**Solução:**
Realizamos uma refatoração para separar a lógica do banco de dados em um módulo dedicado, tornando o projeto mais modular e organizado.

Arquivo criado: funcoes_bd.py

Função principal: buscar_todos_alimentos()

Responsabilidade: Lida com todas as interações diretas com o banco de dados.

app.py:

Foi simplificado. Agora, apenas importa e chama a função buscar_todos_alimentos() do novo módulo.

# Arquivo: funcoes_bd.py

import sqlite3

def conectar_bd():
    """Conecta ao banco de dados e retorna o objeto de conexão."""
    conn = sqlite3.connect('seubanco.db')
    conn.row_factory = sqlite3.Row
    return conn

def buscar_todos_alimentos():
    """Busca e retorna uma lista de todos os alimentos."""
    alimentos = []
    conn = conectar_bd()
    cursor = conn.cursor()
    
    try:
        query = "SELECT * FROM alimentos"
        cursor.execute(query)
        alimentos = cursor.fetchall()
    except sqlite3.Error as e:
        print(f"Erro ao buscar alimentos: {e}")
    finally:
        conn.close()
        
    return alimentos
    
# Arquivo: app.py

from flask import Flask, render_template
from funcoes_bd import buscar_todos_alimentos

app = Flask(__name__)

@app.route('/alimentos')
def lista_alimentos():
    alimentos = buscar_todos_alimentos()
    return render_template('sua_pagina.html', alimentos=alimentos)

