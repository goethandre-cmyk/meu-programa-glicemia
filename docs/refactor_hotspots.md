# Hotspots e recomendações para refatoração (inspeção rápida)

Resumo: esta lista é um relatório inicial com lugares do código onde há duplicação, inconsistências ou risco de regressão. Recomendações seguem cada hotspot.

1) Duplicação do DatabaseManager
   - Arquivos: `database_manager.py` (completo) e `logica.py` (versão legada com DatabaseManager).
   - Risco: alterações aplicadas em um não se propagam ao outro; dificulta manutenção.
   - Recomendação: escolher `database_manager.py` como fonte canônica, criar adaptador compatível, escrever testes e então migrar/retirar a implementação de `logica.py`.

2) Arquivo `app.py` com blocos 'ANTIGO' e lógica duplicada
   - Muitos endpoints reimplementam validações/transformações que existem em `service_manager.py` ou no DB manager.
   - Recomendação: extrair lógica para serviços (BolusService, AppCore, DB adapter) e deixar `app.py` focado em rotas, validação leve e autorização.

3) Nomes e campos inconsistentes
   - Exemplos: `fator_sensibilidade` vs `fsi_geral` vs `fsi`; `razao_ic` vs `ric`.
   - Risco: code paths que esperam chaves diferentes levam a KeyError/None.
   - Recomendação: padronizar nomes no contrato (ver `docs/database_manager_contract.md`) e adaptar leitura no adapter.

4) Parsing de datas espalhado
   - Vários arquivos fazem parse de strings de data em formatos diferentes (`fromisoformat`, `strptime` com vários formatos).
   - Recomendação: criar utilitário único (ex: `utils.datetime_parse`) para normalização.

5) Salvar/ler doses e campos nova/antigos
   - Campos novos como `dose_aplicada`, `dose_insulina`, `total_carbs` aparecem em lugares diferentes e com names distintos em SQL.
   - Recomendação: definir migrations controladas e atualizar read/writes atomically.

6) Falta de testes para camada DB
   - Poucos ou nenhum teste que validem a API do DatabaseManager.
   - Recomendação: criar testes unitários usando SQLite temporário e testes de integração leves.

Primers para a migração segura
- Fazer backups do DB `data/glicemia.db` antes de alterações de schema.
- Criar adaptador de compat (feito nesta etapa) para reduzir riscos de quebra ao trocar implementações.
- Criar PRs pequenos por tópico (ex: 1 PR para adapter e testes; 1 PR para consolidar DB; 1 PR para limpar `app.py`).

Riscos críticos
- ALTER TABLE em SQLite é limitado; para remoção/renomeação de colunas pode ser necessário criar tabela nova e migrar dados.

-- fim
