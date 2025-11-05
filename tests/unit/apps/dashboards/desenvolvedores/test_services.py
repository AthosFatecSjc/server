from unittest.mock import patch

from django.test import SimpleTestCase

from apps.dashboards.desenvolvedores import services
from apps.dashboards.desenvolvedores.services import DesenvolvedoresService


class FakeCursor:
    def __init__(
        self,
        results=None,
        rowcount=1,
        execute_exception=None,
        enter_exception=None,
    ):
        self.results = results or []
        self.rowcount = rowcount
        self.execute_exception = execute_exception
        self.enter_exception = enter_exception
        self.last_query = None
        self.last_params = None
        self.executed_queries = []

    def __enter__(self):
        if self.enter_exception:
            raise self.enter_exception
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query, params=None):
        if self.execute_exception:
            raise self.execute_exception
        self.last_query = query
        self.last_params = params
        self.executed_queries.append(query)

    def fetchall(self):
        return self.results


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor


class DesenvolvedoresServiceTests(SimpleTestCase):
    def setUp(self):
        super().setUp()
        self.original_connections = services.connections
        services.connections = {
            "default": FakeConnection(FakeCursor()),
            "olap": FakeConnection(FakeCursor()),
        }

    def tearDown(self):
        super().tearDown()
        services.connections = self.original_connections

    def test_get_desenvolvedores_olap_sucesso(self):
        results = [
            (1, "Alice Wonderland", 55.0),
            (2, "Bob Builder", 40.0),
        ]
        services.connections["olap"] = FakeConnection(FakeCursor(results=results))

        desenvolvedores = DesenvolvedoresService.get_desenvolvedores_olap()

        self.assertEqual(len(desenvolvedores), 2)
        self.assertEqual(desenvolvedores[0]["iniciais"], "AW")
        self.assertEqual(desenvolvedores[0]["valor_hora"], 55.0)
        self.assertEqual(desenvolvedores[1]["iniciais"], "BB")

    def test_get_desenvolvedores_olap_trata_excecao(self):
        services.connections["olap"] = FakeConnection(
            FakeCursor(execute_exception=RuntimeError("fail"))
        )

        desenvolvedores = DesenvolvedoresService.get_desenvolvedores_olap()

        self.assertEqual(desenvolvedores, [])

    def test_get_desenvolvedores_olap_excecao_no_enter(self):
        services.connections["olap"] = FakeConnection(
            FakeCursor(enter_exception=RuntimeError("cursor error"))
        )

        desenvolvedores = DesenvolvedoresService.get_desenvolvedores_olap()

        self.assertEqual(desenvolvedores, [])

    def test_gerar_iniciais_variacoes(self):
        self.assertEqual(DesenvolvedoresService._gerar_iniciais("Alice B."), "AB")
        self.assertEqual(DesenvolvedoresService._gerar_iniciais("Plácido"), "PL")
        self.assertEqual(DesenvolvedoresService._gerar_iniciais(""), "XX")
        self.assertEqual(DesenvolvedoresService._gerar_iniciais("   "), "XX")

    def test_calcular_estatisticas_vazio(self):
        stats = DesenvolvedoresService.calcular_estatisticas([])

        self.assertEqual(stats["total_desenvolvedores"], 0)
        self.assertEqual(stats["valor_medio"], 0)

    def test_calcular_estatisticas_com_dados(self):
        stats = DesenvolvedoresService.calcular_estatisticas(
            [
                {"valor_hora": 50},
                {"valor_hora": 100},
                {"valor_hora": 150},
            ]
        )

        self.assertEqual(stats["total_desenvolvedores"], 3)
        self.assertEqual(stats["menor_valor"], 50)
        self.assertEqual(stats["maior_valor"], 150)
        self.assertEqual(stats["valor_medio"], 100)
        self.assertEqual(stats["soma_total_valor_hora"], 300)

    @patch.object(DesenvolvedoresService, "_atualizar_valor_hora_olap")
    def test_atualizar_valor_hora_oltp_atualiza_existente(self, mock_atualizar_olap):
        cursor = FakeCursor(rowcount=1)
        services.connections = {
            "default": FakeConnection(cursor),
            "olap": FakeConnection(FakeCursor()),
        }

        sucesso = DesenvolvedoresService.atualizar_valor_hora_oltp(1, "Alice", 123.45)

        self.assertTrue(sucesso)
        self.assertIn("UPDATE funcionario", cursor.last_query)
        mock_atualizar_olap.assert_called_once()

    @patch.object(DesenvolvedoresService, "_atualizar_valor_hora_olap")
    def test_atualizar_valor_hora_oltp_insere_quando_nao_existe(
        self, mock_atualizar_olap
    ):
        cursor = FakeCursor(rowcount=0)
        services.connections = {
            "default": FakeConnection(cursor),
            "olap": FakeConnection(FakeCursor()),
        }

        sucesso = DesenvolvedoresService.atualizar_valor_hora_oltp(2, "Bob", 75.0)

        self.assertTrue(sucesso)
        self.assertTrue(
            any("INSERT INTO funcionario" in q for q in cursor.executed_queries)
        )
        mock_atualizar_olap.assert_called_once_with(2, "Bob", 75.0)

    def test_atualizar_valor_hora_oltp_trata_excecao(self):
        failing_cursor = FakeCursor(execute_exception=RuntimeError("db error"))
        services.connections = {
            "default": FakeConnection(failing_cursor),
            "olap": FakeConnection(FakeCursor()),
        }

        sucesso = DesenvolvedoresService.atualizar_valor_hora_oltp(1, "Alice", 10)

        self.assertFalse(sucesso)

    def test_atualizar_valor_hora_olap_sucesso(self):
        cursor = FakeCursor()
        services.connections["olap"] = FakeConnection(cursor)

        DesenvolvedoresService._atualizar_valor_hora_olap(1, "Alice", 60.0)

        self.assertIn("UPDATE dim_funcionario", cursor.last_query)
        self.assertEqual(cursor.last_params, [60.0, 1, "Alice"])

    def test_atualizar_valor_hora_olap_trata_excecao(self):
        services.connections["olap"] = FakeConnection(
            FakeCursor(execute_exception=RuntimeError("oops"))
        )

        # Deve não lançar (captura internamente) e apenas seguir
        DesenvolvedoresService._atualizar_valor_hora_olap(1, "Alice", 60.0)
