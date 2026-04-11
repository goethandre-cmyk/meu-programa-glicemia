import unittest
from db_adapter import CanonicalDB


class MockDB:
    def __init__(self):
        pass

    def obter_parametros_clinicos(self, user_id):
        return {
            'glicemia_alvo': 120.0,
            'ric_manha': 10.0,
            'ric_almoco': 12.0,
            'ric_jantar': 9.0,
            'fsi_manha': 50.0,
            'fsi_almoco': 40.0,
            'fsi_jantar': 45.0
        }

    def buscar_doses_insulina_recentes(self, user_id, horas_limite=5):
        return [
            {'dose_insulina': 2.0, 'data_hora': '2026-04-11T08:00:00'},
            {'dose_insulina': 1.0, 'data_hora': '2026-04-11T10:00:00'}
        ]

    def buscar_ultima_glicemia(self, user_id):
        return 140.0

    def salvar_refeicao(self, user_id, data_hora_str, tipo_refeicao, total_carbs, total_kcal, alimentos_json, observacoes=None, dose_aplicada=None):
        return True

    def salvar_registro_insulina(self, user_id, dose_insulina, data_hora):
        return True

    def carregar_usuario_por_id(self, user_id):
        return {'id': user_id, 'username': 'mockuser', 'role': 'paciente'}

    def carregar_alimentos(self):
        return [{'alimento': 'Arroz', 'peso': 100, 'carbs': 28.0, 'kcal': 130, 'medida_caseira': 'xícara'}]


class TestDBAdapter(unittest.TestCase):
    def setUp(self):
        self.mock_db = MockDB()
        self.adapter = CanonicalDB(self.mock_db)

    def test_obter_parametros_clinicos(self):
        params = self.adapter.obter_parametros_clinicos(1)
        self.assertIsInstance(params, dict)
        self.assertIn('glicemia_alvo', params)

    def test_buscar_doses_insulina_recentes(self):
        doses = self.adapter.buscar_doses_insulina_recentes(1, horas_limite=6)
        self.assertIsInstance(doses, list)
        self.assertGreaterEqual(len(doses), 1)

    def test_buscar_ultima_glicemia(self):
        val = self.adapter.buscar_ultima_glicemia(1)
        self.assertEqual(val, 140.0)

    def test_salvar_refeicao_and_insulina(self):
        ok = self.adapter.salvar_refeicao(1, '2026-04-11T12:00:00', 'Almoço', 60.0, 600.0, '[]')
        self.assertTrue(ok)
        ok2 = self.adapter.salvar_registro_insulina(1, 4.0, '2026-04-11T12:00:00')
        self.assertTrue(ok2)

    def test_carregar_usuario_e_alimentos(self):
        u = self.adapter.carregar_usuario_por_id(1)
        self.assertEqual(u['username'], 'mockuser')
        alimentos = self.adapter.carregar_alimentos()
        self.assertIsInstance(alimentos, list)


if __name__ == '__main__':
    unittest.main()
