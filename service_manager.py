# service_manager.py

from datetime import datetime

def formatar_registros_para_exibicao(registros_brutos):
    """
    Formata e enriquece a lista de registros do banco para simplificar 
    a lógica de exibição no template, incluindo a conversão de data/hora 
    e o tratamento de inconsistências de Glicemia/Refeição.
    """
    registros_formatados = []
    
    if not registros_brutos:
        return []

    for registro_row in registros_brutos:
        # Garante que estamos trabalhando com um dicionário mutável
        reg = dict(registro_row) 
        
        # --- 1. CONVERSÃO DE DATA E HORA (ADICIONADA AQUI) ---
        data_hora_str = reg.get('data_hora')
        if data_hora_str and isinstance(data_hora_str, str):
            try:
                # Converte a string (formato ISO) em objeto datetime
                reg['data_hora'] = datetime.fromisoformat(data_hora_str)
            except ValueError:
                # Se a conversão falhar (formato inválido), mantém a string original.
                pass 
        
        # --- 2. TRATAMENTO E UNIFICAÇÃO DE TIPOS ---
        
        tipo_bruto = reg.get('tipo', 'Outro')
        reg['is_glicemia'] = False
        reg['is_refeicao'] = False
        reg['tipo_exibicao'] = tipo_bruto # Padrão
        
        # A) É Glicemia? (Verifica valor e exclui Refeição)
        if reg.get('valor') is not None and tipo_bruto != 'Refeição':
            reg['is_glicemia'] = True
            
            # Define o texto que aparecerá na Coluna TIPO (Jejum, Pos-Prandial, etc.)
            tipo_medicao = reg.get('tipo_medicao')

            # Lógica de prioridade para o nome de exibição
            if tipo_medicao:
                reg['tipo_exibicao'] = tipo_medicao
            elif tipo_bruto != 'Glicemia':
                reg['tipo_exibicao'] = tipo_bruto
            else:
                reg['tipo_exibicao'] = 'Glicemia'

        # B) É Refeição?
        elif tipo_bruto == 'Refeição':
            reg['is_refeicao'] = True
            reg['tipo_exibicao'] = reg.get('tipo_refeicao') or 'Refeição'
            
        # C) Outro (Mantém o padrão)

        registros_formatados.append(reg)
        
    return registros_formatados