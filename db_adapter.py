"""Adapter leve que expõe a API canônica do DatabaseManager delegando
para a instância real (`db_manager` de `db_instance.py`).

O objetivo é permitir uma migração incremental: o restante da aplicação
pode depender da API do adaptador (estável) enquanto o backend do DB
é consolidado progressivamente.
"""
from typing import Any
from db_instance import db_manager as global_db


class DBAdapterError(Exception):
    pass


class CanonicalDB:
    """Wrapper que tenta chamar métodos conhecidos no DB subjacente.

    Uso:
        from db_adapter import CanonicalDB
        db = CanonicalDB()
        params = db.obter_parametros_clinicos(user_id)
    """

    def __init__(self, db=None):
        self._db = db or global_db

    def _call(self, candidates, *args, **kwargs) -> Any:
        """Tenta chamar a primeira função válida encontrada no objeto DB.

        candidates: lista de nomes de método possíveis no DB real.
        """
        try:
            # Delegamos à cópia arquivada para facilitar remoção futura
            from archive.archived_functions_batch2 import _call_original
            return _call_original(self._db, candidates, *args, **kwargs)
        except Exception:
            # Fallback: comportamento original em caso de problema com archive
            for name in candidates:
                if hasattr(self._db, name):
                    func = getattr(self._db, name)
                    if callable(func):
                        return func(*args, **kwargs)
            raise NotImplementedError(f"Nenhum dos métodos {candidates} implementado no db_manager")

    # Método canônico: obter_parametros_clinicos
    def obter_parametros_clinicos(self, user_id: int):
        return self._call([
            'obter_parametros_clinicos',
            'obter_parametros_clinicos',
            'get_parametros_clinicos',
            'carregar_parametros_clinicos',
        ], user_id)

    def buscar_doses_insulina_recentes(self, user_id: int, horas_limite=5):
        return self._call([
            'buscar_doses_insulina_recentes',
            'buscar_doses_insulina',
            'get_recent_insulin_doses',
            'buscar_doses_insulina_recentes'
        ], user_id, horas_limite)

    def buscar_ultima_glicemia(self, user_id: int):
        return self._call(['buscar_ultima_glicemia', 'get_last_glicemia', 'buscar_ultima_glicemia'], user_id)

    def salvar_refeicao(self, user_id, data_hora_str, tipo_refeicao, total_carbs, total_kcal, alimentos_json, observacoes=None, dose_aplicada=None):
        return self._call(['salvar_refeicao', 'salvar_refeicao'], user_id, data_hora_str, tipo_refeicao, total_carbs, total_kcal, alimentos_json, observacoes, dose_aplicada)

    def salvar_registro_insulina(self, user_id, dose_insulina, data_hora):
        return self._call(['salvar_registro_insulina', 'salvar_insulina', 'salvar_registro_insulina'], user_id, dose_insulina, data_hora)

    def carregar_usuario_por_id(self, user_id):
        return self._call(['carregar_usuario_por_id', 'obter_usuario_por_id', 'get_user_by_id', 'carregar_usuario_por_id'], user_id)

    def carregar_alimentos(self):
        return self._call(['carregar_alimentos', 'buscar_alimentos', 'carregar_todos_alimentos', 'carregar_alimentos'])

    def salvar_glicemia(self, user_id, valor_glicemia, data_hora_str, tipo_medicao, observacoes=None, dose_aplicada=None):
        return self._call(['salvar_glicemia', 'salvar_glicemia'], user_id, valor_glicemia, data_hora_str, tipo_medicao, observacoes, dose_aplicada)

    # Generic passthrough for other methods
    def __getattr__(self, item):
        if hasattr(self._db, item):
            return getattr(self._db, item)
        raise AttributeError(item)


# For convenience, expose a module-level instance that other modules can import.
db = CanonicalDB()
