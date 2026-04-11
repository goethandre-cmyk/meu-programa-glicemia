import unittest
from datetime import datetime, timedelta

from service_manager import BolusService


class MockDB:
    def __init__(self, parametros=None, doses=None):
        self._parametros = parametros or {}
        self._doses = doses or []

    def obter_parametros_clinicos(self, paciente_id):
        return self._parametros

    def buscar_doses_insulina_recentes(self, user_id, horas_limite=4):
        return self._doses


class QuickTests(unittest.TestCase):
    def test_refactor_now_fn_and_bolus(self):
        parametros = {'glicemia_alvo': 100, 'fsi_manha': 50, 'ric_manha': 10}
        mock_db = MockDB(parametros=parametros, doses=[])
        service = BolusService(mock_db)
        service.set_now_fn(lambda: datetime(2026,4,11,8,0,0))
        service.obter_fsi_por_horario = lambda p: 50
        service.obter_ric_por_horario = lambda p: 10

        resultado, err = service.calcular_bolus_total(gc_atual=180, carboidratos=50, paciente_id=1)
        self.assertIsNone(err)
        self.assertAlmostEqual(resultado['bolus_refeicao'], 5.0)


if __name__ == '__main__':
    unittest.main()
