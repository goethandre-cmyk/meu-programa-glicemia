## Objetivo

Fornecer orientação prática para agentes de código que trabalharão neste repositório — onde olhar primeiro, padrões locais e comandos que permitem executar e testar mudanças rapidamente.

## Visão geral da arquitetura (rápido)
- Dois modos principais de execução: GUI desktop (arquivo `main.py` -> `interface.criar_gui`) e aplicação web baseada em Flask (`app.py`, blueprints como `relatorios.py` e templates em `templates/`).
- Banco de dados SQLite gerenciado por `database_manager.py`. Uma instância singleton é criada em `db_instance.py` como `db_manager` e amplamente usada por serviços e views.
- Lógica de domínio e utilitários: `logica.py` (classes DatabaseManager/ AuthManager antigas/auxiliares), `service_manager.py` (formatadores e `BolusService` — cálculo de bolus).
- Modelos simples: `models.py` contém `User` usado pelo Flask-Login; templates em `templates/` e assets em `static/`.

## Onde o trabalho normalmente começa
- Para inspecionar persistência e migrações: `database_manager.py` — contém `inicializar_db`, `add_new_columns`, e `_migrate_json_to_sqlite`.
- Para entender exibição/formatação de registros: `service_manager.py` e a função `formatar_registros_para_exibicao`.
- Para integrar lógica com a UI (web/desktop): `db_instance.py` (singleton `db_manager`) e `models.py` (contrato do `User`).

## Convenções e padrões do projeto
- A role do usuário é armazenada como string minúscula (ex.: `'paciente'`, `'medico'`, `'admin'`). Verifique `models.User` para propriedades de comodidade (`is_medico`, `is_admin`, etc.).
- Vários arquivos incluem implementações ou variantes históricas de `DatabaseManager` (ex.: `logica.py` contém uma versão; a versão ativa e usada é `database_manager.py` + `db_instance.py`). Prefira `database_manager.py` para mudanças no schema.
- Dados compostos (lista de alimentos em um registro) são salvos como JSON em colunas TEXT (veja `registros.alimentos_refeicao` e o uso de `json.loads`/`json.dumps`).
- Funções de formato/visual (CSS classes) são centralizadas em `service_manager.py` (por exemplo `get_hba1c_class`, `get_jejum_class`).

## Pontos de integração importantes
- Singleton DB: importe `from db_instance import db_manager` em módulos que precisam do DB (ex.: `app.py`, `service_manager.py`).
- Serviços dependentes do DB: `BolusService(db_manager)` — qualquer modificação no cálculo deve preservar a API que retorna dict com chaves `bolus_refeicao`, `bolus_correcao`, `insulina_ativa`, `bolus_total`.
- Templates esperam objetos/flags específicos (ex.: `reg['is_glicemia']`, `reg['is_refeicao']`) produzidos por `formatar_registros_para_exibicao`.

## Como executar (modo rápido)
- GUI desktop (modo mais simples para testar interatividade):
  - Executar: `python main.py` (invoca `interface.criar_gui`).
- Aplicação web (dev):
  - O projeto contém código Flask em `app.py` (versão marcada como "ANTIGO") e blueprints em `relatorios.py`.
  - Recomenda-se garantir que `db_instance.py` seja importado para inicializar o DB antes de executar rotas.
  - Tentativa comum: `set FLASK_APP=app.py; flask run` (PowerShell) ou executar explicitamente o módulo que expõe `app`/`create_app` se houver outro arquivo com `if __name__ == '__main__': app.run(debug=True)`.

## Banco de dados e dados locais
- Arquivo do DB em tempo de execução: `data/glicemia.db` (criado por `DatabaseManager`). Fazer backup antes de alterações destrutivas.
- Existem CSVs e arquivos auxiliares em `data/` (ex.: `alimentos.csv`, `registros.csv`) e um arquivo de projeto `glicemia.sqbpro` — use `database_manager.py` para migrações.

## Riscos e armadilhas conhecidas
- Código legado e duplicação: há implementações antigas/duplicadas de funcionalidades (marcadas como "ANTIGO" em `app.py` e outra `DatabaseManager` em `logica.py`). Confirme qual módulo está sendo importado pelo fluxo que você altera.
- Inicialização do DB: muitas funções assumem que `db_manager` já existe. Use `from db_instance import db_manager` ou crie instância manualmente em scripts de teste.
- Formatos de data/hora: o projeto usa strings ISO em várias partes; funções de parsing tolerantes estão em `service_manager.py` e em métodos de `DatabaseManager`.

## Exemplos rápidos para um agente
- Para criar uma migração de coluna segura: use `DatabaseManager.get_db_connection()` e `ALTER TABLE ...` com captura de `sqlite3.OperationalError` (veja `add_new_columns`).
- Para adicionar um utilitário que retorna registros prontos para template:
  - Use `db_manager.carregar_registros_por_usuario(username)` → passe o resultado para `formatar_registros_para_exibicao(...)` antes de enviar ao template.

## Onde olhar para testes e melhorias de baixo risco
- Não há testes automatizados no repositório; comece com testes unitários para `service_manager.BolusService` e para as funções de formatação de `service_manager.py`.

---
Se algo estiver ambíguo (qual modo é “principal” neste repositório, qual DatabaseManager usar por padrão etc.), diga qual parte você quer que eu esclareça e eu atualizo estas instruções.
