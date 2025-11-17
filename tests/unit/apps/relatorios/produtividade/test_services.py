from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase, TestCase

from apps.relatorios.models import (
    Cargo,
    Funcionario,
    Issue,
    MetaProdutividade,
    Projeto,
    RegistroProdutividade,
    TipoIssue,
)
from apps.relatorios.produtividade import services
from apps.relatorios.produtividade.services import (
    CODIGOS_REVERSOS,
    OLTP_ALIAS,
    _aplicar_estilo_pdf,
    _atualizar_codigo_especial,
    _buscar_fontes_horas,
    _buscar_funcionarios,
    _buscar_horas_fato,
    _buscar_horas_issue,
    _buscar_registros_diarios,
    _calcular_spends_por_dev,
    _criar_titulo_pdf,
    _dias_uteis_no_mes,
    _formatar_valor_celula,
    _listar_dias_mes,
    _meta_padrao,
    _montar_tabela_pdf,
    _percentual,
    _possui_horas_fato,
    atualizar_meta_funcionario,
    atualizar_multiplos_dias,
    calcular_spends_por_dev_com_legendas,
    exportar_produtividade_pdf,
    listar_equipes_disponiveis,
    listar_meses_disponiveis,
    obter_meta_funcionario,
)
from olap_models.models import DimFuncionario, DimProjeto, DimTempo, FatoRegistroHoras


class _FakeIterable:
    def __init__(self, data):
        self.data = data

    def __iter__(self):
        return iter(self.data)


class _FakeDimTempoQuery:
    def __init__(self, dias):
        self.dias = dias

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def values_list(self, *args, **kwargs):
        return _FakeIterable(self.dias)


class _FakeDimTempoManager:
    def __init__(self, dias):
        self.dias = dias

    def using(self, alias):
        return _FakeDimTempoQuery(self.dias)


class _FakeFatoHorasQuery(_FakeIterable):
    def __init__(self, rows):
        super().__init__(rows)

    def filter(self, *args, **kwargs):
        return self

    def values(self, *args, **kwargs):
        return self

    def annotate(self, *args, **kwargs):
        return _FakeIterable(self.data)


class _FakeFatoHorasManager:
    def __init__(self, rows):
        self.rows = rows

    def using(self, alias):
        return _FakeFatoHorasQuery(self.rows)


class _FakeAggregateQuery:
    def __init__(self, total):
        self.total = total

    def filter(self, *args, **kwargs):
        return self

    def aggregate(self, **kwargs):
        return {"total": self.total}


class _FakeAggregateManager:
    def __init__(self, total):
        self.total = total

    def using(self, alias):
        return _FakeAggregateQuery(self.total)


class ListarMesesDisponiveisTests(SimpleTestCase):
    def _mock_issue_queryset(self, mock_issue, order_by_result):
        queryset = mock.MagicMock()
        queryset.filter.return_value = queryset
        queryset.values_list.return_value = queryset
        queryset.distinct.return_value = queryset
        queryset.order_by.return_value = order_by_result
        mock_issue.objects.using.return_value = queryset
        return queryset

    @mock.patch("apps.relatorios.produtividade.services.Issue")
    def test_usa_datas_das_issues(self, mock_issue):
        self._mock_issue_queryset(mock_issue, [(2025, 11)])

        meses = listar_meses_disponiveis()

        self.assertEqual(meses[0]["mes"], 11)
        self.assertEqual(meses[0]["ano"], 2025)

    @mock.patch("apps.relatorios.produtividade.services.Issue")
    def test_listar_meses_disponiveis_com_dados(self, mock_issue):
        self._mock_issue_queryset(mock_issue, [(2025, 11), (2024, 12)])

        meses = listar_meses_disponiveis()

        self.assertEqual([meses[0]["mes"], meses[1]["mes"]], [11, 12])
        self.assertEqual([meses[0]["ano"], meses[1]["ano"]], [2025, 2024])

    @mock.patch("apps.relatorios.produtividade.services.Issue")
    def test_listar_meses_disponiveis_sem_registros(self, mock_issue):
        self._mock_issue_queryset(mock_issue, [])

        meses = listar_meses_disponiveis()

        self.assertEqual(len(meses), 1)

    @mock.patch("apps.relatorios.produtividade.services.datetime")
    @mock.patch("apps.relatorios.produtividade.services.Issue")
    def test_retorna_mes_atual_quando_sem_dados(self, mock_issue, mock_datetime):
        mock_datetime.now.return_value = datetime(2024, 12, 15, 10, 0, 0)
        self._mock_issue_queryset(mock_issue, [])

        meses = services.listar_meses_disponiveis()

        self.assertEqual(meses, [{"mes": 12, "ano": 2024, "mes_nome": "Dezembro"}])


class ListarDiasDisponiveisTests(SimpleTestCase):
    def setUp(self):
        self.funcionario = SimpleNamespace(id=1, nome="Alice", time="Alpha")
        self.funcionario2 = SimpleNamespace(id=2, nome="Bob", time="Beta")
        self.funcionarios = [self.funcionario, self.funcionario2]

    def test_listar_dias_mes_usando_dimtempo(self):
        fake_manager = _FakeDimTempoManager([1, 5, 10])
        with mock.patch.object(services.DimTempo, "objects", fake_manager):
            dias = services._listar_dias_mes(7, 2025)

        self.assertEqual(dias, [1, 5, 10])

    def test_listar_dias_mes_faz_fallback_para_calendar(self):
        fake_manager = _FakeDimTempoManager([])
        with mock.patch.object(services.DimTempo, "objects", fake_manager):
            dias = services._listar_dias_mes(4, 2025)

        self.assertEqual(len(dias), 30)
        self.assertEqual(dias[0], 1)
        self.assertEqual(dias[-1], 30)

    def test_listar_dias_mes_com_dim_e_sem_dim(self):
        fake_manager = _FakeDimTempoManager([1, 2, 3])
        with mock.patch.object(services.DimTempo, "objects", fake_manager):
            dias_dim = _listar_dias_mes(11, 2025)
        self.assertEqual(dias_dim, [1, 2, 3])

        fake_empty = _FakeDimTempoManager([])
        with mock.patch.object(services.DimTempo, "objects", fake_empty):
            dias_fallback = _listar_dias_mes(1, 2025)

        self.assertEqual(dias_fallback[0], 1)
        self.assertEqual(dias_fallback[-1], 31)

    @mock.patch("apps.relatorios.produtividade.services.obter_meta_funcionario")
    @mock.patch("apps.relatorios.produtividade.services._buscar_horas_fato")
    @mock.patch("apps.relatorios.produtividade.services._buscar_horas_issue")
    @mock.patch("apps.relatorios.produtividade.services._buscar_registros_diarios")
    @mock.patch("apps.relatorios.produtividade.services._buscar_funcionarios")
    @mock.patch("apps.relatorios.produtividade.services._listar_dias_mes")
    def test_calcular_spends_por_dev(
        self,
        mock_listar_dias,
        mock_buscar_func,
        mock_registros,
        mock_horas_issue,
        mock_horas_fato,
        mock_meta,
    ):
        mock_listar_dias.return_value = [1, 2, 3]
        mock_buscar_func.return_value = [self.funcionario]
        mock_registros.return_value = {
            (self.funcionario.id, 1): Decimal("8"),
            (self.funcionario.id, 2): Decimal("2"),
        }
        mock_horas_issue.return_value = {(self.funcionario.id, 3): Decimal("3")}
        mock_horas_fato.return_value = {}
        mock_meta.return_value = Decimal("200")

        dados = calcular_spends_por_dev_com_legendas(11, 2025)

        resultado = dados["resultados"][0]
        self.assertEqual(resultado["real"], 13.0)
        self.assertEqual(resultado["dias"][1], 8.0)
        self.assertEqual(resultado["dias"][2], 2.0)
        self.assertEqual(resultado["dias"][3], 3.0)
        self.assertEqual(resultado["meta"], 200.0)
        self.assertAlmostEqual(resultado["percentual"], round(13 / 200 * 100, 1))
        self.assertEqual(dados["resultados"][-1]["funcionario"], "REALIZADO")

    @mock.patch(
        "apps.relatorios.produtividade.services._buscar_funcionarios", return_value=[]
    )
    def test_calcular_spends_sem_funcionarios(self, mock_buscar):
        resultado = _calcular_spends_por_dev(11, 2025, [1, 2], equipe="Inexistente")
        self.assertEqual(resultado, [])
        mock_buscar.assert_called_once_with("Inexistente")

    @mock.patch(
        "apps.relatorios.produtividade.services._buscar_horas_fato",
        return_value={"hf": 1},
    )
    @mock.patch(
        "apps.relatorios.produtividade.services._buscar_horas_issue",
        return_value={"hi": 1},
    )
    @mock.patch(
        "apps.relatorios.produtividade.services._buscar_registros_diarios",
        return_value={"rd": 1},
    )
    def test_buscas_de_fontes_de_dados(
        self,
        mock_registros,
        mock_horas_issue,
        mock_horas_fato,
    ):
        registros, horas_issue, horas_fato = _buscar_fontes_horas(
            self.funcionarios, 11, 2025
        )
        self.assertEqual(registros, {"rd": 1})
        self.assertEqual(horas_issue, {"hi": 1})
        self.assertEqual(horas_fato, {"hf": 1})
        mock_registros.assert_called_once()
        mock_horas_issue.assert_called_once()
        mock_horas_fato.assert_called_once()

    def test_registros_diarios_e_horas_issue(self):
        manager = mock.MagicMock()
        queryset = mock.MagicMock()
        queryset.filter.return_value = queryset
        queryset.values_list.return_value = [
            (self.funcionario.id, 1, Decimal("8")),
        ]
        manager.using.return_value = queryset
        with mock.patch.object(services.RegistroProdutividade, "objects", manager):
            registros = _buscar_registros_diarios(11, 2025, [self.funcionario.id])

        self.assertEqual(registros[(self.funcionario.id, 1)], Decimal("8"))

        issue_manager = mock.MagicMock()
        issue_qs = mock.MagicMock()
        issue_qs.filter.return_value = issue_qs
        issue_qs.annotate.return_value = issue_qs
        values_qs = mock.MagicMock()
        values_qs.annotate.return_value = [
            {"funcionario_id": self.funcionario.id, "dia": 1, "total": 7200}
        ]
        issue_qs.values.return_value = values_qs
        issue_manager.using.return_value = issue_qs
        with mock.patch.object(services.Issue, "objects", issue_manager):
            horas_issue = _buscar_horas_issue(11, 2025, [self.funcionario.id])
        self.assertEqual(horas_issue[(self.funcionario.id, 1)], Decimal("2"))

    @mock.patch(
        "apps.relatorios.produtividade.services._buscar_funcionarios", return_value=[]
    )
    def test_calcular_spends_sem_funcionarios(self, mock_buscar):
        resultado = services._calcular_spends_por_dev(7, 2025, [1, 2], None)

        self.assertEqual(resultado, [])
        mock_buscar.assert_called_once_with(None)

    @mock.patch("apps.relatorios.produtividade.services.Funcionario")
    def test_buscar_funcionarios_filtra_por_equipe(self, mock_funcionario):
        class FakeQuery:
            def __init__(self, data):
                self.data = data

            def order_by(self, *_args, **_kwargs):
                return self

            def filter(self, **kwargs):
                time = kwargs.get("time")
                if time:
                    return FakeQuery([f for f in self.data if f.time == time])
                return self

            def __iter__(self):
                return iter(self.data)

        fake_data = [
            SimpleNamespace(id=1, nome="Alice", time="Alpha"),
            SimpleNamespace(id=2, nome="Bob", time="Beta"),
        ]
        fake_query = FakeQuery(fake_data)
        manager = mock.MagicMock()
        manager.using.return_value = fake_query
        mock_funcionario.objects = manager

        todos = services._buscar_funcionarios(None)
        alpha = services._buscar_funcionarios("Alpha")

        self.assertEqual(len(todos), 2)
        self.assertEqual([f.nome for f in alpha], ["Alice"])

    @mock.patch("apps.relatorios.produtividade.services._buscar_horas_fato")
    @mock.patch("apps.relatorios.produtividade.services._buscar_horas_issue")
    @mock.patch("apps.relatorios.produtividade.services._buscar_registros_diarios")
    def test_buscar_fontes_horas_coordena_fontes(
        self, mock_registros, mock_issue, mock_fato
    ):
        dev = SimpleNamespace(id=99)
        mock_registros.return_value = {"reg": 1}
        mock_issue.return_value = {"issue": 2}
        mock_fato.return_value = {"fato": 3}

        resultado = services._buscar_fontes_horas([dev], 7, 2025)

        self.assertEqual(
            resultado,
            (
                {"reg": 1},
                {"issue": 2},
                {"fato": 3},
            ),
        )
        mock_registros.assert_called_once_with(7, 2025, [99])
        mock_issue.assert_called_once_with(7, 2025, [99])
        mock_fato.assert_called_once_with(7, 2025, [99])

    def test_buscar_registros_diarios_mapeia_valores(self):
        manager = mock.MagicMock()
        queryset = mock.MagicMock()
        queryset.filter.return_value = queryset
        queryset.values_list.return_value = [
            (self.funcionario.id, 2, Decimal("6")),
        ]
        manager.using.return_value = queryset
        with mock.patch.object(services.RegistroProdutividade, "objects", manager):
            resultado = services._buscar_registros_diarios(
                7, 2025, [self.funcionario.id]
            )

        self.assertEqual(resultado[(self.funcionario.id, 2)], Decimal("6"))

    def test_buscar_horas_issue_converte_segundos_em_horas(self):
        issue_manager = mock.MagicMock()
        issue_qs = mock.MagicMock()
        issue_qs.filter.return_value = issue_qs
        issue_qs.annotate.return_value = issue_qs
        values_qs = mock.MagicMock()
        values_qs.annotate.return_value = [
            {"funcionario_id": self.funcionario.id, "dia": 3, "total": 7200}
        ]
        issue_qs.values.return_value = values_qs
        issue_manager.using.return_value = issue_qs
        with mock.patch.object(services.Issue, "objects", issue_manager):
            resultado = services._buscar_horas_issue(7, 2025, [self.funcionario.id])

        self.assertEqual(resultado[(self.funcionario.id, 3)], Decimal("2"))

    def test_buscar_horas_fato_usa_resultado_iteravel(self):
        rows = [
            {"funcionario_id": 1, "data__dia": 5, "horas": Decimal("4.5")},
            {"funcionario_id": 2, "data__dia": 6, "horas": None},
        ]
        fake_manager = _FakeFatoHorasManager(rows)
        with mock.patch.object(services.FatoRegistroHoras, "objects", fake_manager):
            resultado = services._buscar_horas_fato(7, 2025, [1])

        self.assertEqual(resultado[(1, 5)], Decimal("4.5"))
        self.assertNotIn((2, 6), resultado)

    @mock.patch("apps.relatorios.produtividade.services.transaction.atomic")
    @mock.patch("apps.relatorios.produtividade.services._atualizar_codigo_especial")
    def test_atualiza_registro_com_legenda(self, mock_atualizar, mock_atomic):
        ctx = mock.MagicMock()
        mock_atomic.return_value = ctx
        ctx.__enter__.return_value = None
        ctx.__exit__.return_value = None
        mock_atualizar.return_value = (True, None)

        sucesso, erro = services.atualizar_multiplos_dias(1, 7, 2025, [1, 2], "FE")

        self.assertTrue(sucesso)
        self.assertIsNone(erro)
        mock_atualizar.assert_has_calls(
            [
                mock.call(1, 7, 2025, 1, "FE"),
                mock.call(1, 7, 2025, 2, "FE"),
            ]
        )

    @mock.patch("apps.relatorios.produtividade.services.transaction.atomic")
    @mock.patch("apps.relatorios.produtividade.services._atualizar_codigo_especial")
    def test_atualiza_registro_bloqueia_quando_ha_horas(
        self, mock_atualizar, mock_atomic
    ):
        ctx = mock.MagicMock()
        mock_atomic.return_value = ctx
        ctx.__enter__.return_value = None
        ctx.__exit__.return_value = None
        mock_atualizar.side_effect = [(False, "Dia já possui horas lançadas.")]

        sucesso, erro = services.atualizar_multiplos_dias(1, 7, 2025, [1], "FE")

        self.assertFalse(sucesso)
        self.assertIn("horas", erro)
        mock_atualizar.assert_called_once()


class AtualizarCodigoEspecialTests(TestCase):
    def setUp(self):
        self.func = Funcionario.objects.create(nome="Daniel")

    @mock.patch("apps.relatorios.produtividade.services._possui_horas_fato")
    def test_retorna_erro_quando_dia_ja_tem_horas(self, mock_possui):
        mock_possui.return_value = False
        RegistroProdutividade.objects.create(
            funcionario=self.func, dia=date(2025, 7, 1), valor=Decimal("8")
        )

        sucesso, erro = services._atualizar_codigo_especial(
            self.func.id, 7, 2025, 1, "FE"
        )

        self.assertFalse(sucesso)
        self.assertIn("horas lançadas", erro)

    @mock.patch(
        "apps.relatorios.produtividade.services._possui_horas_fato", return_value=False
    )
    def test_remove_registro_quando_codigo_none(self, _):
        RegistroProdutividade.objects.create(
            funcionario=self.func, dia=date(2025, 7, 1), valor=Decimal("-1")
        )

        sucesso, erro = services._atualizar_codigo_especial(
            self.func.id, 7, 2025, 1, "NONE"
        )

        self.assertTrue(sucesso)
        self.assertIsNone(erro)
        self.assertEqual(RegistroProdutividade.objects.count(), 0)

    @mock.patch(
        "apps.relatorios.produtividade.services._possui_horas_fato", return_value=False
    )
    def test_codigo_invalido(self, _):
        sucesso, erro = services._atualizar_codigo_especial(
            self.func.id, 7, 2025, 1, "??"
        )

        self.assertFalse(sucesso)
        self.assertIn("inválido", erro)

    @mock.patch(
        "apps.relatorios.produtividade.services._possui_horas_fato", return_value=False
    )
    def test_atualiza_registro_existente(self, _):
        registro = RegistroProdutividade.objects.create(
            funcionario=self.func, dia=date(2025, 7, 1), valor=Decimal("-1")
        )

        sucesso, erro = services._atualizar_codigo_especial(
            self.func.id, 7, 2025, 1, "FO"
        )

        self.assertTrue(sucesso)
        self.assertIsNone(erro)
        registro.refresh_from_db()
        self.assertEqual(registro.valor, Decimal("-3"))


class PossuiHorasFatoTests(SimpleTestCase):
    def test_possui_horas_fato_true_quando_total_positivo(self):
        fake_manager = _FakeAggregateManager(Decimal("1"))
        with mock.patch.object(services.FatoRegistroHoras, "objects", fake_manager):
            resultado = services._possui_horas_fato(1, date(2025, 7, 1))

        self.assertTrue(resultado)

    def test_possui_horas_fato_false_quando_sem_horas(self):
        fake_manager = _FakeAggregateManager(None)
        with mock.patch.object(services.FatoRegistroHoras, "objects", fake_manager):
            resultado = services._possui_horas_fato(1, date(2025, 7, 1))

        self.assertFalse(resultado)


class UtilitariosProdutividadeTests(TestCase):
    def test_atualizar_meta_funcionario_cria_registro(self):
        func = Funcionario.objects.create(nome="Eva")

        services.atualizar_meta_funcionario(func.id, 7, 2025, 155.5)

        meta = MetaProdutividade.objects.get(funcionario=func, ano=2025, mes=7)
        self.assertEqual(meta.meta_horas, Decimal("155.5"))

    @mock.patch(
        "apps.relatorios.produtividade.services._dias_uteis_no_mes", return_value=21
    )
    def test_meta_padrao_para_clt(self, mock_dias):
        func = Funcionario.objects.create(nome="Fred", contrato="CLT")

        valor = services._meta_padrao(func, 7, 2025)

        self.assertEqual(valor, Decimal("168"))
        mock_dias.assert_called_once_with(7, 2025)

    def test_dias_uteis_no_mes_conta_sem_finais_de_semana(self):
        dias = services._dias_uteis_no_mes(2, 2024)
        self.assertEqual(dias, 21)

    def test_formatar_valor_celula_trata_variacoes(self):
        self.assertEqual(services._formatar_valor_celula(None), 0.0)
        self.assertEqual(
            services._formatar_valor_celula(Decimal("-1")),
            {"type": "leave", "value": "FE"},
        )
        self.assertEqual(services._formatar_valor_celula(Decimal("0")), 0.0)
        self.assertEqual(services._formatar_valor_celula(Decimal("2.5")), 2.5)

    def test_percentual_com_meta_zero_retorna_zero(self):
        self.assertEqual(services._percentual(Decimal("5"), Decimal("0")), 0.0)
        self.assertEqual(services._percentual(Decimal("5"), Decimal("10")), 50.0)

    def test_exportar_produtividade_pdf_gera_documento(self):
        resultados = [
            {
                "funcionario": "Alice",
                "dias": {1: {"type": "leave", "value": "FE"}, 2: 4.0},
                "real": 4.0,
                "meta": 8.0,
                "percentual": 50.0,
            },
            {
                "funcionario": "REALIZADO",
                "dias": {1: 0.0, 2: 4.0},
                "real": 4.0,
                "meta": 8.0,
                "percentual": 50.0,
            },
        ]

        pdf = services.exportar_produtividade_pdf(7, 2025, resultados)

        self.assertGreater(len(pdf), 0)
        self.assertTrue(pdf.startswith(b"%PDF"))
