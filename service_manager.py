# service_manager.py

from datetime import datetime
import math 

from datetime import datetime, timedelta 
# Garanta que o 'datetime' e 'timedelta' estão importados, se você os usa.

def formatar_registros_para_exibicao(registros_brutos):
    """
    Formata e enriquece a lista de registros, classificando Glicemia e Refeição
    de forma INDEPENDENTE para permitir a exibição de detalhes combinados ou únicos.
    """
    registros_formatados = []
    
    if not registros_brutos:
        return []

    for registro_row in registros_brutos:
        reg = dict(registro_row) 
        
        # --- 1. CONVERSÃO DE DATA E HORA ---
        data_hora_str = reg.get('data_hora')
        if data_hora_str and isinstance(data_hora_str, str):
            try:
                # Tentativa de converter formatos comuns ('T' ou ' ')
                if 'T' in data_hora_str:
                    reg['data_hora'] = datetime.fromisoformat(data_hora_str)
                elif len(data_hora_str) >= 19:
                    reg['data_hora'] = datetime.strptime(data_hora_str, '%Y-%m-%d %H:%M:%S')
                else: # Trata o formato sem segundos
                    reg['data_hora'] = datetime.strptime(data_hora_str, '%Y-%m-%d %H:%M')
            except ValueError:
                pass 
        
        # --- 2. CLASSIFICAÇÃO DE TIPO (FINAL E INDEPENDENTE) ---
        tipo_bruto = reg.get('tipo', 'Outro')
        reg['is_glicemia'] = False
        reg['is_refeicao'] = False
        reg['tipo_exibicao'] = tipo_bruto
        
        # A) CLASSIFICAÇÃO DE REFEIÇÃO: 
        # É refeição se o tipo bruto for 'Refeição' OU se houver carboidratos OU o JSON de alimentos.
        if tipo_bruto == 'Refeição' or reg.get('total_carbs') is not None or reg.get('alimentos_json') is not None:
            reg['is_refeicao'] = True
            reg['tipo_exibicao'] = reg.get('tipo_refeicao') or 'Refeição'
            
        # B) CLASSIFICAÇÃO DE GLICEMIA: 
        # É glicemia se houver um valor numérico de glicemia ('valor').
        if reg.get('valor') is not None: 
            try:
                reg['valor'] = float(reg['valor'])
            except (TypeError, ValueError):
                 reg['valor'] = None 
            
            if reg.get('valor') is not None:
                reg['is_glicemia'] = True
                
                # Se for SÓ glicemia (sem refeição), ajusta o tipo de exibição.
                if not reg['is_refeicao']:
                    tipo_medicao = reg.get('tipo_medicao')
                    reg['tipo_exibicao'] = tipo_medicao or 'Glicemia'

        registros_formatados.append(reg)
            
    return registros_formatados

class BolusService:
     # Duração de Ação Máxima da insulina (4h para ultrarrápida)
    DOA_MAX_HORAS = 4.0 
    def __init__(self, db_manager):
        # A injeção do db_manager permite que o serviço acesse dados, se necessário
        self.db = db_manager 

    # --- NOVO MÉTODO: OBTEM RIC POR HORÁRIO ---
    def obter_ric_por_horario(self, parametros):
        """
        Determina e retorna a RIC (Razão Insulina/Carboidrato) 
        com base nos parâmetros do paciente e na hora atual.
        """
        # Define os horários de corte (iguais aos usados para o FSI)
        HORARIO_MANHA = 6
        HORARIO_ALMOCO = 12
        HORARIO_JANTAR = 18

        hora_atual = datetime.now().hour
        
        # 1. Manhã: [06:00 - 11:59]
        if HORARIO_MANHA <= hora_atual < HORARIO_ALMOCO:
            return parametros.get('ric_manha')
            
        # 2. Almoço: [12:00 - 17:59]
        elif HORARIO_ALMOCO <= hora_atual < HORARIO_JANTAR:
            return parametros.get('ric_almoco')
            
        # 3. Jantar/Noite: [18:00 - 05:59]
        else:
            return parametros.get('ric_jantar')

    # --- MÉTODO JÁ EXISTENTE (FSI) ---
    def obter_fsi_por_horario(self, parametros):
        """
        Determina e retorna o FSI (Fator de Sensibilidade à Insulina) 
        com base nos parâmetros do paciente e na hora atual.
        """
        # Horários de corte mantidos, como no original...
        HORARIO_MANHA = 6
        HORARIO_ALMOCO = 12
        HORARIO_JANTAR = 18

        hora_atual = datetime.now().hour
        
        # 1. Manhã: [06:00 - 11:59]
        if HORARIO_MANHA <= hora_atual < HORARIO_ALMOCO:
            return parametros.get('fsi_manha')
            
        # 2. Almoço: [12:00 - 17:59]
        elif HORARIO_ALMOCO <= hora_atual < HORARIO_JANTAR:
            return parametros.get('fsi_almoco')
            
        # 3. Jantar/Noite: [18:00 - 05:59]
        else:
            return parametros.get('fsi_jantar')


    # --- MÉTODO PRINCIPAL (CORREÇÃO) ---
 
    def calcular_bolus_total(self, gc_atual, carboidratos, paciente_id): 
        """
        Calcula a dose total de Bolus (Correção + Nutricional) para o paciente,
        incluindo o cálculo interno da Insulina Ativa (IA).
        """
        # 1. Obter Parâmetros Clínicos
        parametros = self.db.obter_parametros_clinicos(paciente_id)
        
        # 2. Validação Inicial
        if not parametros or not parametros.get('glicemia_alvo'):
            return None, "Parâmetros clínicos incompletos ou ausentes."

        glicemia_alvo = parametros['glicemia_alvo']
        
        # 3. Determinar o FSI e o RIC do momento
        fsi = self.obter_fsi_por_horario(parametros)
        ric = self.obter_ric_por_horario(parametros)
        
        # 4. Validação de FSI e RIC
        if not fsi or fsi == 0:
            return None, "Fator de Sensibilidade à Insulina (FSI) para o horário atual não configurado ou é zero."
        
        if not ric or ric == 0:
            return None, "Razão Insulina/Carboidrato (RIC) para o horário atual não configurada ou é zero."
        
        
        # --- Lógica de Cálculo (DEFINE bolus_bruto) ---
        
        # Bolus Nutricional (BN): Carboidratos / RIC
        bolus_nutricional = carboidratos / ric
        
        # Bolus de Correção (BC): (GC - GA) / FSI
        diferenca_glicemia = gc_atual - glicemia_alvo
        bolus_correcao = diferenca_glicemia / fsi
        
        # Bolus Bruto (soma antes da IA)
        bolus_bruto = bolus_nutricional + bolus_correcao  # <--- DEFINIÇÃO CRÍTICA AQUI
        
        # --- CÁLCULO DA INSULINA ATIVA (IA) ---
        ia_ativa = self.calcular_insulina_ativa(paciente_id)

        # Bolus Final (aplicando IA)
        bolus_final = bolus_bruto - ia_ativa
        
        # Arredondamento (para o 0.5 UI mais próximo)
        dose_arredondada = round(bolus_final * 2) / 2
        
        # Garantir dose mínima é 0
        bolus_total = max(0, dose_arredondada)
        
        # Retorna todos os componentes
        return {
            'bolus_refeicao': round(bolus_nutricional, 1),
            'bolus_correcao': round(bolus_correcao, 1),
            'insulina_ativa': round(ia_ativa, 1),
            'bolus_total': bolus_total,
            'fsi_usado': fsi,
            'ric_usado': ric
        }, None

    def calcular_insulina_ativa(self, user_id):
        """
        Calcula a Insulina Ativa (IA) total baseada em doses recentes.
        Usa um modelo linear simplificado para a curva de ação da insulina.
        """
        
        # 1. Obter as doses do DB
        doses_recentes = self.db.buscar_doses_insulina_recentes(user_id, horas_limite=math.ceil(self.DOA_MAX_HORAS))
        
        ia_total = 0.0
        
        if not doses_recentes:
            return 0.0
        
        for dose in doses_recentes:
            dose_ui = dose.get('dose_insulina', 0.0)
            data_aplicacao_str = dose.get('data_hora')
            
            if dose_ui <= 0.0 or not data_aplicacao_str:
                continue
                
            try:
                # 2. Conversão da Data
                data_aplicacao = datetime.fromisoformat(data_aplicacao_str)
                tempo_decorrido: timedelta = datetime.now() - data_aplicacao
                
                # Tempo decorrido em horas
                tempo_decorrido_horas = tempo_decorrido.total_seconds() / 3600
                
                # 3. Cálculo da Insulina Ativa (Modelo Linear Simples)
                
                # Porcentagem de insulina remanescente (linear)
                # Exemplo: Se DOA=4h e passou 1h, sobram 3/4 = 75%
                porcentagem_restante = (self.DOA_MAX_HORAS - tempo_decorrido_horas) / self.DOA_MAX_HORAS
                
                # Garante que a porcentagem está entre 0 e 1 (0% a 100%)
                porcentagem_restante = max(0.0, min(1.0, porcentagem_restante))
                
                insulina_remanescente = dose_ui * porcentagem_restante
                ia_total += insulina_remanescente
                
            except ValueError:
                # Ignora doses com data/hora inválida
                continue

        # Retorna o total de IA arredondado (ex: 0.5 UI)
        return round(ia_total * 2) / 2 
