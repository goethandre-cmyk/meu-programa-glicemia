# service_manager.py

from datetime import datetime, timedelta
import math 

def parse_data_hora(data_hora_str):
    """Centraliza a conversão de strings de data/hora para objetos datetime."""
    if not data_hora_str or not isinstance(data_hora_str, str):
        return None
    
    try:
        if 'T' in data_hora_str:
            # Suporta ISO format e Zulu
            return datetime.fromisoformat(data_hora_str.replace('Z', '+00:00'))
        elif len(data_hora_str) >= 19:
            return datetime.strptime(data_hora_str, '%Y-%m-%d %H:%M:%S')
        else:
            # Formato sem segundos
            return datetime.strptime(data_hora_str, '%Y-%m-%d %H:%M')
    except ValueError:
        return None

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
        dt_convertido = parse_data_hora(reg.get('data_hora'))
        if dt_convertido:
            reg['data_hora'] = dt_convertido
        
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
# --- NOVAS FUNÇÕES DE CLASSIFICAÇÃO VISUAL DE RISCO ---

def get_hba1c_class(hba1c_value):
    """
    Retorna as classes CSS e o status para o valor de HbA1c, 
    baseado nas referências clínicas.
    """
    try:
        # Tenta converter o valor para float, se não for None
        valor = float(hba1c_value) if hba1c_value is not None else None
    except (ValueError, TypeError):
        valor = None # Força None em caso de erro de conversão

    if valor is None:
        return 'bg-secondary text-white', 'N/A' # Valor ausente/inválido

    if valor >= 6.5:
        # HbA1c >= 6.5: Risco/Diabetes, controle ruim.
        return 'bg-danger text-white', 'Risco/Diabetes'
    elif 5.7 <= valor < 6.5:
        # 5.7 <= HbA1c < 6.5: Pré-diabetes/Atenção.
        return 'bg-warning text-dark', 'Atenção/Pré-diabetes'
    else: # valor < 5.7
        # HbA1c < 5.7: Meta atingida/Normal.
        return 'bg-success text-white', 'Meta Atingida'

def get_jejum_class(jejum_value):
    """
    Retorna as classes CSS e o status para o valor de Glicose Jejum,
    baseado nas referências clínicas.
    """
    try:
        # Tenta converter o valor para int/float, se não for None
        valor = float(jejum_value) if jejum_value is not None else None
    except (ValueError, TypeError):
        valor = None # Força None em caso de erro de conversão

    if valor is None:
        return 'bg-secondary text-white', 'N/A' # Valor ausente/inválido

    if valor > 99:
        # Glicose Jejum > 99: Risco.
        return 'bg-danger text-white', 'Risco'
    elif 70 <= valor <= 99:
        # 70 <= Glicose Jejum <= 99: Meta atingida/Normal.
        return 'bg-success text-white', 'Meta Atingida'
    else: # valor < 70 (Hipoglicemia ou muito baixo)
        # Glicose Jejum < 70: Atenção/Hipoglicemia
        return 'bg-warning text-dark', 'Atenção/Baixo'

class BolusService:
    # Duração de Ação Máxima da insulina (4h para ultrarrápida é um bom padrão)
    DOA_MAX_HORAS = 4.0 
    
    # Definição de faixas horárias
    HORA_MANHA = 6
    HORA_ALMOCO = 12
    HORA_JANTAR = 18

    def __init__(self, db_manager):
        self.db = db_manager 
        # now_fn é uma função que retorna o datetime atual. Permite injeção de tempo para testes.
        # Por compatibilidade com código existente, aceitamos que a instância possa fornecer
        # um atributo `_now_fn` antes da criação, mas o mais simples é passar uma função
        # via setter externo se desejado. Aqui apenas definimos o default.
        self._now_fn = None

    def set_now_fn(self, now_fn):
        """Define uma função now_fn que retorna o datetime atual (usado em testes)."""
        self._now_fn = now_fn

    def _now(self):
        """Retorna o datetime atual usando a função injetada ou datetime.now() por padrão."""
        if callable(self._now_fn):
            return self._now_fn()
        return datetime.now()

    def _obter_parametro_por_horario(self, parametros, prefixo):
        """Método auxiliar para evitar repetição de lógica de fsi/ric por horário."""
        hora_atual = self._now().hour
        
        if self.HORA_MANHA <= hora_atual < self.HORA_ALMOCO:
            return parametros.get(f'{prefixo}_manha')
        elif self.HORA_ALMOCO <= hora_atual < self.HORA_JANTAR:
            return parametros.get(f'{prefixo}_almoco')
        else:
            return parametros.get(f'{prefixo}_jantar')

    # --- RIC POR HORÁRIO ---
    def obter_ric_por_horario(self, parametros):
        return self._obter_parametro_por_horario(parametros, 'ric')

    # --- FSI POR HORÁRIO ---
    def obter_fsi_por_horario(self, parametros):
        return self._obter_parametro_por_horario(parametros, 'fsi')

    # --- MÉTODO PRINCIPAL ---
    def calcular_bolus_total(self, gc_atual, carboidratos, paciente_id): 
        parametros = self.db.obter_parametros_clinicos(paciente_id)

        if not parametros or not parametros.get('glicemia_alvo'):
            return None, "Parâmetros clínicos incompletos ou ausentes."

        glicemia_alvo = parametros['glicemia_alvo']

        # Obtém FSI/RIC explicitamente; só usa valor padrão quando o retorno for None
        fsi = self.obter_fsi_por_horario(parametros)
        if fsi is None:
            fsi = 50.0  # Valor padrão
        ric = self.obter_ric_por_horario(parametros)
        if ric is None:
            ric = 10.0  # Valor padrão

        if fsi <= 0:
            return None, "FSI inválido (zero ou negativo)."
        if ric <= 0:
            return None, "RIC inválido (zero ou negativo)."

        # Bolus Nutricional (BN)
        bolus_nutricional = carboidratos / ric

        # Bolus de Correção (BC)
        diferenca_glicemia = gc_atual - glicemia_alvo
        bolus_correcao_bruto = max(0, diferenca_glicemia / fsi)  # Garante que a correção não é negativa

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
            # Aceita múltiplos nomes históricos para a chave da dose
            dose_ui = dose.get('dose_aplicada') or dose.get('dose_insulina') or dose.get('dose') or 0.0
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

                tempo_decorrido: timedelta = self._now() - data_aplicacao
                
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