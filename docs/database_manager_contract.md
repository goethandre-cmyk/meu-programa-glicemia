# Contrato canônico para DatabaseManager

Objetivo: definir a API mínima e os contratos (entradas/saídas/erros) que o serviço de banco de dados deve expor para o resto da aplicação e para os testes.

Requisitos gerais
- Linguagem: Python (objetos/dicionários retornados preferencialmente como dict)
- Erros: o DB deve lançar exceções somente em casos graves; preferir retornar None/False e logs quando aplicável. O adaptador levantará NotImplementedError se um método essencial não existir.

Métodos canônicos (contrato)

1) obter_parametros_clinicos(user_id: int) -> dict | None
   - Retorna dicionário com chaves (mínimas):
     - glicemia_alvo (float)
     - ric_manha, ric_almoco, ric_jantar (float | None)
     - fsi_manha, fsi_almoco, fsi_jantar (float | None)
   - Comportamento: se nenhum registro, retorna None. Valores numéricos podem ser None.

2) buscar_doses_insulina_recentes(user_id: int, horas_limite: int) -> list[dict]
   - Cada dict: {'dose_insulina'| 'dose': float, 'data_hora': str}
   - Retorna lista vazia se nenhuma dose encontrada.

3) buscar_ultima_glicemia(user_id: int) -> float | None
   - Retorna valor numérico (float) ou None.

4) salvar_refeicao(user_id:int, data_hora_str:str, tipo_refeicao:str, total_carbs:float, total_kcal:float, alimentos_json:str, observacoes: str=None, dose_aplicada: float=None) -> bool
   - Retorna True se sucesso, False se falhar.

5) salvar_registro_insulina(user_id:int, dose_insulina:float, data_hora:str) -> bool
   - Salva um registro de insulina aplicada. Retorna True/False.

6) carregar_usuario_por_id(user_id:int) -> dict | None
   - Retorna dicionário com ao menos 'id','username','role' ou None.

7) carregar_alimentos() -> list[dict]
   - Retorna lista de alimentos (cada dict com chaves 'alimento','peso','carbs','kcal','medida_caseira').

8) salvar_glicemia(user_id:int, valor_glicemia:float, data_hora_str:str, tipo_medicao:str, observacoes:str=None, dose_aplicada: float=None) -> bool
   - Retorna True/False.

9) buscar_doses_insulina_recentes(user_id:int, horas_limite:int) -> list[dict]
   - Já listado acima, duplicado propositalmente para reforço.

Erros e modos de falha
- Métodos que retornam None: usado para indicar ausência de dados sem lançar exceção.
- Métodos que retornam False: usado para indicar falha ao persistir.
- Exceções: só para erros inesperados (ex: corrupção DB). Adaptador pode transformar AttributeError em NotImplementedError com mensagem clara.

Formato de data/hora
- Usar ISO 8601 quando possível (ex: 'YYYY-MM-DDTHH:MM:SS' ou sem T). O serviço deve aceitar ambas e o adapter/unificador pode normalizar.

Observações de implementação
- Permitir parâmetros por horário (fsi_manha, fsi_almoco...) e valores gerais (fator_sensibilidade). O serviço que consome deve escolher explicitamente quando usar fallback.
- Valores 0 devem ser tratados explicitamente (não usar `or` para fallback).

Contrato de testes
- Os testes unitários do adaptador assumirão comportamentos conforme acima e usarão mocks para verificar delegação.

-- fim
