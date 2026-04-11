import os
import tempfile
import shutil
import unittest
import sqlite3
from datetime import datetime

from database_manager import DatabaseManager


class DatabaseManagerIntegrationTests(unittest.TestCase):
    def setUp(self):
        # cria um diretório temporário e um arquivo sqlite absoluto
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, 'glicemia_integration_test.db')
        # Use caminho absoluto para forçar DatabaseManager a usar este arquivo
        self.db = DatabaseManager(db_path=self.db_path)

    def tearDown(self):
        try:
            shutil.rmtree(self.tmpdir)
        except Exception:
            pass

    def test_inicializar_cria_tabelas_basicas(self):
        # Verifica que as tabelas essenciais existem
        conn = self.db.get_db_connection()
        cur = conn.cursor()
        # verificar tabela users
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        self.assertIsNotNone(cur.fetchone(), 'Tabela users não criada')
        # verificar tabela registros
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='registros'")
        self.assertIsNotNone(cur.fetchone(), 'Tabela registros não criada')
        conn.close()

    def test_add_new_columns_adiciona_colunas_users(self):
        # Remove a coluna caso já exista - garantir estado limpo
        # Executa add_new_columns e verifica colunas em users
        self.db.add_new_columns()
        conn = self.db.get_db_connection()
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(users)")
        cols = [row[1] for row in cur.fetchall()]
        # colunas esperadas adicionadas pelo método
        for expected in ('nome_completo', 'telefone', 'medico_id'):
            self.assertIn(expected, cols, f"Coluna esperada '{expected}' não encontrada em users")
        conn.close()

    def test_salvar_glicemia_via_api_apos_migracao_parcial(self):
        # Salva usuário
        username = 'integ_test_user2'
        user_data = {
            'username': username,
            'password_hash': 'x',
            'role': 'paciente',
        }
        saved = self.db.salvar_usuario(user_data)
        self.assertTrue(saved)
        user_id = self.db.get_user_id_by_username(username)
        self.assertIsNotNone(user_id)

        # Garantir que coluna dose_aplicada exista
        try:
            self.db.adicionar_colunas_ausentes()
        except Exception:
            pass

        # Garantir que a coluna tipo_medicao exista na tabela registros (adicionar manualmente no teste)
        conn = self.db.get_db_connection()
        cur = conn.cursor()
        # Verifica se tipo_medicao existe; se não, adiciona
        cur.execute("PRAGMA table_info(registros)")
        cols = [r[1] for r in cur.fetchall()]
        if 'tipo_medicao' not in cols:
            cur.execute("ALTER TABLE registros ADD COLUMN tipo_medicao TEXT;")
            conn.commit()

        conn.close()

        # Agora deve funcionar o salvar_glicemia
        now_iso = datetime.now().isoformat()
        ok = self.db.salvar_glicemia(user_id, 99.1, now_iso, 'Jejum')
        self.assertTrue(ok, 'salvar_glicemia falhou mesmo após adicionar colunas necessárias')

    def test_fluxo_usuario_salvar_registro_via_api(self):
        # cria usuário e usa salvar_registro para inserir um registro completo
        username = 'integ_flow_user'
        user_data = {'username': username, 'password_hash': 'x', 'role': 'paciente'}
        self.assertTrue(self.db.salvar_usuario(user_data))
        user_id = self.db.get_user_id_by_username(username)
        # garantir colunas esperadas na tabela registros usadas por salvar_registro
        conn = self.db.get_db_connection()
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(registros)")
        existing = [r[1] for r in cur.fetchall()]
        needed = {
            'alimentos_json': 'TEXT',
            'total_calorias': 'REAL',
            'total_carbs': 'REAL',
            'dose_aplicada': 'REAL'
        }
        for col, typ in needed.items():
            if col not in existing:
                try:
                    cur.execute(f"ALTER TABLE registros ADD COLUMN {col} {typ};")
                except sqlite3.OperationalError:
                    pass
        conn.commit()
        conn.close()

        registro = {
            'user_id': user_id,
            'data_hora': datetime.now().isoformat(),
            'tipo': 'Glicemia',
            'valor': 88.8,
            'observacoes': 'teste flow',
            'alimentos_json': None,
            'total_calorias': None,
            'total_carbs': None,
            'dose_aplicada': None
        }
        ok = self.db.salvar_registro(registro)
        self.assertTrue(ok)

        registros = self.db.carregar_registros(user_id)
        self.assertTrue(isinstance(registros, list))
        self.assertGreaterEqual(len(registros), 1)


if __name__ == '__main__':
    unittest.main()
