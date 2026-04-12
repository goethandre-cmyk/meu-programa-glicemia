## Resumo

Este PR agrupa os batches 3–6 do processo de arquivamento seguro de código legado.

Principais mudanças:
- Adiciona implementações originais em `archive/archived_functions_batch2.py`, `archive/archived_functions_batch3.py`, `archive/archived_functions_batch4.py`, `archive/archived_functions_batch5.py`.
- Substitui implementações pesadas por delegadores que importam as versões arquivadas com fallback local, nos arquivos: `database_manager.py`, `logica.py`, `app.py`, `db_adapter.py`, `service_manager.py`.
- Mantém fallbacks locais para garantir compatibilidade caso o arquivo `archive/*` não seja importável.
- Adiciona testes e validação local (suíte `tests/` permanece verde).

Motivação:
- Permitir remoção segura de código legado em pequenos passos reversíveis.
- Centralizar lógica canônica e facilitar testes.

## Como testar localmente

Execute a suíte de testes:

```bash
python -m venv venv
# Ative o venv (PowerShell)
& "venv\Scripts\Activate.ps1"
python -m pip install -r requirements.txt  # se houver
python -m unittest discover -s tests -p "test_*.py" -v
```

Verifique que todos os testes passam (16 testes no meu ambiente local).

## Checklist para revisão

- [ ] Código arquivado contém implementação original e está em `archive/`.
- [ ] Substituições em `database_manager.py`, `logica.py`, `app.py`, `db_adapter.py`, `service_manager.py` mantêm fallback.
- [ ] Testes unitários e de integração passando localmente.
- [ ] Nenhuma rota crítica removida sem substituição (verificar manualmente templates Jinja onde aplicável).
- [ ] DB migration helpers permanecem disponíveis via archive para validação antes de remoção final.

## Notas para o revisor


Obrigado! Se quiser, abro um PR description menor/mais técnico ou adiciono pontos específicos para validação manual (templates, endpoints).
 
## Reviewers e Labels sugeridos

- Reviewers sugeridos:
	- @goethandre-cmyk
	- @team/backend (se existir)

- Labels sugeridos:
	- `refactor`
	- `tech-debt`
	- `needs-review`
	- `database`

Adicione ou substitua conforme o fluxo do repositório.