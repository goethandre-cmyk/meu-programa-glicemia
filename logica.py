# logica.py

import os
import json
import csv
from datetime import datetime
import bcrypt

# --- Configuração de Arquivos ---
USUARIOS_FILE = os.path.join('data', 'usuarios.json')
REGISTROS_FILE = os.path.join('data', 'registros.json')
ALIMENTOS_FILE = os.path.join('data', 'alimentos.csv')
LOG_FILE = os.path.join('data', 'log_app.log')
# Garante que a pasta 'data' exista
os.makedirs('data', exist_ok=True)

# --- Funções Utilitárias (Independentes de classes) ---
def get_cor_glicemia(valor):
    """Retorna uma classe CSS baseada no valor da glicemia."""
    if valor < 70:
        return 'hipoglicemia'
    elif 70 <= valor <= 120:
        return 'glicemia-normal'
    elif 120 < valor <= 180:
        return 'glicemia-elevada'
    else:
        return 'hiperglicemia'

def get_cor_classificacao(valor):
    """Retorna a classificação de glicemia baseada no valor."""
    if valor < 70:
        return 'Baixa'
    elif 70 <= valor <= 120:
        return 'Normal'
    elif 120 < valor <= 180:
        return 'Elevada'
    else:
        return 'Muito Alta'

def calcular_bolus_detalhado(carboidratos, glicemia, meta_glicemia, razao_ic, fator_sensibilidade):
    """Calcula a dose de bolus de insulina com base em carboidratos e correção de glicemia."""
    bolus_refeicao = carboidratos / razao_ic if razao_ic else 0
    bolus_correcao = (glicemia - meta_glicemia) / fator_sensibilidade if fator_sensibilidade else 0
    bolus_total = bolus_refeicao + bolus_correcao
    return {
        "bolus_refeicao": round(bolus_refeicao, 2),
        "bolus_correcao": round(bolus_correcao, 2),
        "bolus_total": round(bolus_total, 2)
    }

def calcular_fator_sensibilidade(dtdi, tipo_insulina):
    """
    Calcula o Fator de Sensibilidade à Insulina (FS).
    dtdi: Dose Total Diária de Insulina.
    tipo_insulina: 'rápida' ou 'ultrarrápida'.
    """
    if tipo_insulina == 'ultrarrápida':
        return round(500 / dtdi, 2)
    elif tipo_insulina == 'rápida':
        return round(450 / dtdi, 2)
    else:
        return None

def _limpar_string_para_busca(texto):
    """Função interna para remover espaços, pontuações e converter para minúsculas."""
    if not isinstance(texto, str):
        return ''
    return texto.strip().lower().replace(' ', '').replace('-', '')

# --- Classes de Lógica de Negócio ---

class DataManager:
    """
    Gerencia a leitura e escrita de todos os arquivos de dados.
    """
    def __init__(self):
        self._inicializar_arquivos()

    def _inicializar_arquivos(self):
        if not os.path.exists(USUARIOS_FILE):
            with open(USUARIOS_FILE, 'w', encoding='utf-8') as f:
                json.dump({}, f)
        
        if not os.path.exists(REGISTROS_FILE):
            with open(REGISTROS_FILE, 'w', encoding='utf-8') as f:
                json.dump([], f)
        
        if not os.path.exists(ALIMENTOS_FILE):
            with open(ALIMENTOS_FILE, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f, delimiter=';')
                writer.writerow(['ID', 'ALIMENTO', 'MEDIDA CASEIRA', 'PESO (g/ml)', 'Kcal', 'CHO (g)'])

    def carregar_usuarios(self):
        """Carrega os dados de usuários do arquivo JSON."""
        try:
            with open(USUARIOS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def salvar_usuarios(self, usuarios):
        """Salva os dados de usuários no arquivo JSON."""
        with open(USUARIOS_FILE, 'w', encoding='utf-8') as f:
            json.dump(usuarios, f, indent=4, ensure_ascii=False)

    def carregar_registros(self):
        """
        Carrega os registros do ficheiro JSON e converte a string de data
        de volta para um objeto datetime para uso no aplicativo.
        """
        try:
            if os.path.exists(REGISTROS_FILE):
                with open(REGISTROS_FILE, 'r', encoding='utf-8') as f:
                    registros_json = json.load(f)
                    for registro in registros_json:
                        data_hora_str = registro.get('data_hora')
                        if data_hora_str and isinstance(data_hora_str, str):
                            try:
                                registro['data_hora'] = datetime.fromisoformat(data_hora_str)
                            except ValueError:
                                registro['data_hora'] = None
                    return registros_json
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        return []

    def salvar_registros(self, registros):
        """
        Salva os registros no ficheiro JSON, convertendo objetos de data
        para strings para serialização.
        """
        registros_salvar = []
        for registro in registros:
            reg_copy = registro.copy()
            if 'data_hora' in reg_copy and isinstance(reg_copy['data_hora'], datetime):
                reg_copy['data_hora'] = reg_copy['data_hora'].isoformat()
            registros_salvar.append(reg_copy)
        
        with open(REGISTROS_FILE, 'w', encoding='utf-8') as f:
            json.dump(registros_salvar, f, indent=4, ensure_ascii=False)

    def carregar_alimentos(self):
        """Carrega a base de dados de alimentos do arquivo CSV."""
        alimentos = []
        try:
            with open(ALIMENTOS_FILE, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f, delimiter=';')
                for row in reader:
                    alimentos.append(row)
        except FileNotFoundError:
            pass
        return alimentos

    def salvar_alimento_csv(self, nome, tipo, carbs, protein, fat, acucares, gord_sat, sodio, medida_caseira, peso_g):
        """Adiciona um novo alimento ao arquivo CSV."""
        try:
            alimentos_atuais = self.carregar_alimentos()
            next_id = 1
            if alimentos_atuais:
                next_id = int(alimentos_atuais[-1]['ID']) + 1

            with open(ALIMENTOS_FILE, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f, delimiter=';')
                writer.writerow([next_id, nome, medida_caseira, peso_g, 0, carbs])
        except Exception as e:
            print(f"Erro ao salvar alimento no CSV: {e}")

class AuthManager:
    """
    Gerencia a autenticação e dados de usuário.
    """
    def __init__(self, data_manager):
        self.data_manager = data_manager

    def salvar_usuario(self, username, password, **kwargs):
        """Cadastra ou atualiza um usuário com senha hasheada."""
        usuarios = self.data_manager.carregar_usuarios()
        if username in usuarios:
            return False, "Nome de usuário já existe."

        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        novo_usuario = {
            "password": hashed_password,
            "role": "user",
            **kwargs
        }
        
        usuarios[username] = novo_usuario
        self.data_manager.salvar_usuarios(usuarios)
        return True, "Cadastro bem-sucedido."

    def verificar_login(self, username, password):
        """Verifica as credenciais do usuário com a senha hasheada."""
        usuarios = self.data_manager.carregar_usuarios()
        usuario = usuarios.get(username)
        if usuario:
            try:
                if bcrypt.checkpw(password.encode('utf-8'), usuario['password'].encode('utf-8')):
                    return usuario, "Login bem-sucedido."
            except (KeyError, ValueError, TypeError):
                pass
        return None, "Credenciais inválidas. Tente novamente."

class AppCore:
    """
    A camada de aplicação que coordena a lógica de negócio.
    """
    def __init__(self, data_manager):
        self.data_manager = data_manager
        self.registros = self.data_manager.carregar_registros()
        self.alimentos = self.data_manager.carregar_alimentos()
        
    def salvar_log_acao(self, acao, usuario):
        """Salva uma ação do usuário em um arquivo de log."""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{timestamp}] - Usuário: {usuario} - Ação: {acao}\n"
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(log_entry)

    def adicionar_registro(self, **kwargs):
        """Adiciona um novo registro e salva."""
        next_id = 1
        if self.registros:
            max_id = max(int(reg.get('id', 0)) for reg in self.registros)
            next_id = max_id + 1
        
        novo_registro = {
            'id': next_id,
            'data_hora': kwargs.get('data_hora', datetime.now()),
            **kwargs
        }
        self.registros.append(novo_registro)
        self.data_manager.salvar_registros(self.registros)
        
    def mostrar_registros(self, usuario_filtro=None):
        """Retorna a lista de registros, opcionalmente filtrada por usuário."""
        if usuario_filtro:
            return [r for r in self.registros if r.get('usuario') == usuario_filtro]
        return self.registros

    def encontrar_registro(self, id_str):
        """Encontra um registro pelo ID, que pode vir como string."""
        try:
            id_int = int(id_str)
            for registro in self.registros:
                if isinstance(registro.get('id'), str):
                    registro['id'] = int(registro['id'])
                if registro.get('id') == id_int:
                    return registro
        except (ValueError, TypeError):
            pass
        return None

    def atualizar_registro(self, id_str, **kwargs):
        """Atualiza um registro existente."""
        registo = self.encontrar_registro(id_str)
        if registo:
            registo.update(kwargs)
            self.data_manager.salvar_registros(self.registros)
            return True
        return False
        
    def excluir_registro(self, id_str):
        """Exclui um registro pelo ID."""
        id_int = int(id_str)
        registros_atuais = [r for r in self.registros if int(r.get('id', 0)) != id_int]
        if len(registros_atuais) < len(self.registros):
            self.registros = registros_atuais
            self.data_manager.salvar_registros(self.registros)
            return True
        return False

    def salvar_alimento_csv(self, nome, tipo, carbs, protein, fat, acucares, gord_sat, sodio, medida_caseira, peso_g):
        """Chama a função para salvar um novo alimento no CSV."""
        self.data_manager.salvar_alimento_csv(nome, tipo, carbs, protein, fat, acucares, gord_sat, sodio, medida_caseira, peso_g)
        
    def pesquisar_alimentos(self, termo_pesquisa):
        """Busca alimentos na base de dados carregada em memória."""
        termo_limpo = _limpar_string_para_busca(termo_pesquisa)
        resultados = []
        for alimento in self.alimentos:
            nome_alimento_limpo = _limpar_string_para_busca(alimento.get('ALIMENTO', ''))
            if termo_limpo in nome_alimento_limpo:
                resultados.append(alimento)
        return resultados