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


class BolusServiceTests(unittest.TestCase):
    def test_calcular_bolus_total_success(self):
        parametros = {
            'glicemia_alvo': 100,
            'fsi_manha': 50,
            'ric_manha': 10,
            'fsi_almoco': 50,
            'ric_almoco': 10,
            'fsi_jantar': 50,
            'ric_jantar': 10,
        }

        mock_db = MockDB(parametros=parametros, doses=[])
        service = BolusService(mock_db)
        # Injeta tempo fixo (manhã) para previsibilidade
        fixed_now = datetime(2026, 4, 11, 8, 0, 0)
        service.set_now_fn(lambda: fixed_now)

        resultado, err = service.calcular_bolus_total(gc_atual=180, carboidratos=50, paciente_id=1)
        self.assertIsNone(err)
        # bolus_refeicao = 50/10 = 5.0
        self.assertAlmostEqual(resultado['bolus_refeicao'], 5.0)
        # bolus_correcao = (180-100)/50 = 1.6 -> round 1.6
        self.assertAlmostEqual(resultado['bolus_correcao'], 1.6)
        # insulina_ativa = 0
        self.assertAlmostEqual(resultado['insulina_ativa'], 0.0)
        # bolus_total = round((5+1.6)*2)/2 = round(13.2)/2 = 13/2 = 6.5
        self.assertAlmostEqual(resultado['bolus_total'], 6.5)

    def test_calcular_bolus_total_missing_params(self):
        mock_db = MockDB(parametros={})
        service = BolusService(mock_db)
        service.set_now_fn(lambda: datetime(2026, 4, 11, 9, 0, 0))
        service.obter_fsi_por_horario = lambda p: 50.0
        service.obter_ric_por_horario = lambda p: 10.0

        resultado, err = service.calcular_bolus_total(gc_atual=120, carboidratos=30, paciente_id=1)
        self.assertIsNone(resultado)
        self.assertIsNotNone(err)

    def test_calcular_bolus_total_invalid_fsi(self):
        parametros = {'glicemia_alvo': 100, 'fsi_manha': 0, 'ric_manha': 10}
        mock_db = MockDB(parametros=parametros)
        service = BolusService(mock_db)
        service.set_now_fn(lambda: datetime(2026, 4, 11, 8, 30, 0))
        service.obter_fsi_por_horario = lambda p: 0
        service.obter_ric_por_horario = lambda p: 10

        resultado, err = service.calcular_bolus_total(gc_atual=150, carboidratos=20, paciente_id=1)
        self.assertIsNone(resultado)
        self.assertIn('FSI inválido', err)

    def test_calcular_insulina_ativa_single_dose(self):
        fixed_now = datetime(2026, 4, 11, 12, 0, 0)
        data_2h_atras = (fixed_now - timedelta(hours=2)).isoformat()
        doses = [{'dose_insulina': 2.0, 'data_hora': data_2h_atras}]
        mock_db = MockDB(doses=doses)
        service = BolusService(mock_db)
        service.set_now_fn(lambda: fixed_now)

        ia = service.calcular_insulina_ativa(user_id=1)
        # DOA_MAX_HORAS = 4.0 -> fator = (4-2)/4 = 0.5 -> IA = 2.0 * 0.5 = 1.0
        self.assertAlmostEqual(ia, 1.0)

    def test_calcular_insulina_ativa_multiplas_doses(self):
        fixed_now = datetime(2026, 4, 11, 12, 0, 0)
        d1 = {'dose_insulina': 1.0, 'data_hora': (fixed_now - timedelta(hours=1)).isoformat()}
        d2 = {'dose_insulina': 2.0, 'data_hora': (fixed_now - timedelta(hours=3)).isoformat()}
        d3 = {'dose_insulina': 1.0, 'data_hora': (fixed_now - timedelta(hours=5)).isoformat()}  # deve ser ignorada
        mock_db = MockDB(doses=[d1, d2, d3])
        service = BolusService(mock_db)
        service.set_now_fn(lambda: fixed_now)

        ia = service.calcular_insulina_ativa(user_id=1)
        # IA d1 = 1 * (4-1)/4 = 0.75 ; IA d2 = 2 * (4-3)/4 = 0.5 ; soma = 1.25 -> arredondado para 1.2
        self.assertAlmostEqual(ia, round(0.75 + 0.5, 1))

    def test_arredondamento_bolus(self):
        # Valida o arredondamento para 0.5 UI mais próximo
        parametros = {'glicemia_alvo': 100, 'fsi_manha': 50, 'ric_manha': 10}
        mock_db = MockDB(parametros=parametros, doses=[])
        service = BolusService(mock_db)
        service.set_now_fn(lambda: datetime(2026, 4, 11, 8, 0, 0))
        # força IA pequena
        service.calcular_insulina_ativa = lambda pid: 0.15

        resultado, err = service.calcular_bolus_total(gc_atual=105, carboidratos=12, paciente_id=1)
        self.assertIsNone(err)
        # bolus_nutricional = 12/10 = 1.2 ; correcao = (105-100)/50 = 0.1 ; bruto = 1.3 ; final = 1.15
        # *2 = 2.3 -> round = 2 -> /2 = 1.0
        self.assertAlmostEqual(resultado['bolus_total'], 1.0)


if __name__ == '__main__':
    unittest.main()
