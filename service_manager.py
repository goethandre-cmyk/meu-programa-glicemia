# service_manager.py

from datetime import datetime
import math 

from datetime import datetime, timedelta 
# Garanta que o 'datetime' e 'timedelta' estão importados, se você os usa.

def formatar_registros_para_exibicao(registros_brutos):
    """
    Formata e enriquece a lista de registros.
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
                    reg['data_hora'] = datetime.fromisoformat(data_hora_str.replace('Z', '+00:00')) # Suporta Zulu/ISO
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
        if tipo_bruto == 'Refeição' or reg.get('total_carbs') is not None or reg.get('alimentos_json') is not None:
            reg['is_refeicao'] = True
            reg['tipo_exibicao'] = reg.get('tipo_refeicao') or 'Refeição'
            
        # B) CLASSIFICAÇÃO DE GLICEMIA: 
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
    # Duração de Ação Máxima da insulina (4h para ultrarrápida é um bom padrão)
    DOA_MAX_HORAS = 4.0 
    
    def __init__(self, db_manager):
        self.db = db_manager 

    # --- RIC POR HORÁRIO ---
    def obter_ric_por_horario(self, parametros):
        HORARIO_MANHA = 6
        HORARIO_ALMOCO = 12
        HORARIO_JANTAR = 18
        hora_atual = datetime.now().hour
        
        if HORARIO_MANHA <= hora_atual < HORARIO_ALMOCO:
            return parametros.get('ric_manha')
        elif HORARIO_ALMOCO <= hora_atual < HORARIO_JANTAR:
            return parametros.get('ric_almoco')
        else:
            return parametros.get('ric_jantar')

    # --- FSI POR HORÁRIO ---
    def obter_fsi_por_horario(self, parametros):
        HORARIO_MANHA = 6
        HORARIO_ALMOCO = 12
        HORARIO_JANTAR = 18
        hora_atual = datetime.now().hour
        
        if HORARIO_MANHA <= hora_atual < HORARIO_ALMOCO:
            return parametros.get('fsi_manha')
        elif HORARIO_ALMOCO <= hora_atual < HORARIO_JANTAR:
            return parametros.get('fsi_almoco')
        else:
            return parametros.get('fsi_jantar')

    # --- MÉTODO PRINCIPAL ---
    def calcular_bolus_total(self, gc_atual, carboidratos, paciente_id): 
        parametros = self.db.obter_parametros_clinicos(paciente_id)
        
        if not parametros or not parametros.get('glicemia_alvo'):
            return None, "Parâmetros clínicos incompletos ou ausentes."

        glicemia_alvo = parametros['glicemia_alvo']
        fsi = self.obter_fsi_por_horario(parametros) or 50.0 # Valor padrão se for None
        ric = self.obter_ric_por_horario(parametros) or 10.0 # Valor padrão se for None
        
        if fsi <= 0:
            return None, "FSI inválido (zero ou negativo)."
        if ric <= 0:
            return None, "RIC inválido (zero ou negativo)."
        
        # Bolus Nutricional (BN)
        bolus_nutricional = carboidratos / ric
        
        # Bolus de Correção (BC)
        diferenca_glicemia = gc_atual - glicemia_alvo
        bolus_correcao_bruto = max(0, diferenca_glicemia / fsi) # Garante que a correção não é negativa
        
        bolus_bruto = bolus_nutricional + bolus_correcao_bruto
        
        # CÁLCULO DA INSULINA ATIVA (IA)
        ia_ativa = self.calcular_insulina_ativa(paciente_id)

        # Bolus Final
        bolus_final = bolus_bruto - ia_ativa
        
        # Arredondamento (para o 0.5 UI mais próximo) e Garantir dose mínima é 0
        dose_arredondada = round(bolus_final * 2) / 2
        bolus_total = max(0, dose_arredondada)
        
        # Retorna todos os componentes
        return {
            'bolus_refeicao': round(bolus_nutricional, 1),
            'bolus_correcao': round(bolus_correcao_bruto, 1),
            'insulina_ativa': round(ia_ativa, 1),
            'bolus_total': bolus_total,
            'fsi_usado': fsi,
            'ric_usado': ric
        }, None

    # --- MÉTODO DE CÁLCULO DA INSULINA ATIVA CORRIGIDO ---
    def calcular_insulina_ativa(self, user_id):
        """
        Calcula a Insulina Ativa (IA) total baseada em doses recentes.
        Usa um modelo linear simplificado.
        """
        
        # 1. Obter as doses do DB
        # O db_manager deve buscar a dose_insulina e data_hora
        doses_recentes = self.db.buscar_doses_insulina_recentes(user_id, horas_limite=math.ceil(self.DOA_MAX_HORAS))
        
        ia_total = 0.0
        
        if not doses_recentes:
            return 0.0
        
        for dose in doses_recentes:
            dose_ui = dose.get('dose_insulina', 0.0)
            data_aplicacao_str = dose.get('data_hora')
            
            if dose_ui <= 0.0 or not data_aplicacao_str:
                continue
                
            # 2. Conversão e Cálculo
            try:
                # Lógica de conversão de data/hora (copiada do seu código, mas agora identada)
                data_aplicacao = None
                if 'T' in data_aplicacao_str:
                    data_aplicacao = datetime.fromisoformat(data_aplicacao_str.replace('Z', '+00:00'))
                elif len(data_aplicacao_str) >= 19:
                    data_aplicacao = datetime.strptime(data_aplicacao_str, '%Y-%m-%d %H:%M:%S')
                else:
                    data_aplicacao = datetime.strptime(data_aplicacao_str, '%Y-%m-%d %H:%M')

                if not data_aplicacao:
                    continue 

                tempo_decorrido: timedelta = datetime.now() - data_aplicacao
                
                # Tempo decorrido em horas
                horas_decorridas = tempo_decorrido.total_seconds() / 3600.0
                
                # Se passou do tempo de ação, pule.
                if horas_decorridas >= self.DOA_MAX_HORAS:
                    continue
                    
                # Modelo Linear de Insulina Ativa (Simples):
                # IA = Dose * (DOA_MAX - horas_decorridas) / DOA_MAX
                fator_remanescente = (self.DOA_MAX_HORAS - horas_decorridas) / self.DOA_MAX_HORAS
                
                ia_dose_atual = dose_ui * fator_remanescente
                ia_total += ia_dose_atual
                
            except (ValueError, TypeError):
                # Ignora doses com data/hora inválida
                continue

        # 3. Retorna o total de IA arredondado (fora do loop)
        return round(ia_total, 1) # Arredondar para 1 casa decimal (ex: 0.5 UI)