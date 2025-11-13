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


class ProdutividadeServiceBaseTestCase(TestCase):
    databases = {"default", "olap"}

    @classmethod
    def setUpTestData(cls):
        cls.cargo = Cargo.objects.create(sigla="DEV")
        cls.funcionario = Funcionario.objects.create(
            nome="Alice",
            time="Alpha",
            cargo=cls.cargo,
            valor_hora=Decimal("120"),
        )
        cls.funcionario2 = Funcionario.objects.create(
            nome="Bob",
            time="Beta",
            cargo=cls.cargo,
            valor_hora=Decimal("110"),
        )
        cls.projeto = Projeto.objects.create(nome="Projeto Teste")
        cls.tipo_issue = TipoIssue.objects.create(
            nome="Bug",
            descricao="Bug",
            jira_id=101,
            projeto=cls.projeto,
        )

        Issue.objects.create(
            jira_id=1,
            jira_key="PROD-1",
            projeto=cls.projeto,
            titulo="Implantação",
            tipo_issue=cls.tipo_issue,
            criado_em=datetime(2025, 11, 1, 10, 0),
            tempo_gasto_seconds=7200,
            funcionario=cls.funcionario,
        )
        Issue.objects.create(
            jira_id=2,
            jira_key="PROD-2",
            projeto=cls.projeto,
            titulo="Homologação",
            tipo_issue=cls.tipo_issue,
            criado_em=datetime(2025, 11, 2, 9, 0),
            tempo_gasto_seconds=3600,
            funcionario=cls.funcionario,
        )

        RegistroProdutividade.objects.create(
            funcionario=cls.funcionario, dia=date(2025, 11, 1), valor=Decimal("8")
        )
        RegistroProdutividade.objects.create(
            funcionario=cls.funcionario, dia=date(2025, 11, 2), valor=Decimal("2")
        )
        RegistroProdutividade.objects.create(
            funcionario=cls.funcionario, dia=date(2025, 11, 3), valor=Decimal("3")
        )

        MetaProdutividade.objects.create(
            funcionario=cls.funcionario, mes=11, ano=2025, meta_horas=Decimal("200")
        )

        cls.dim_func1 = DimFuncionario.objects.using("olap").create(
            id=cls.funcionario.id,
            nome=cls.funcionario.nome,
            time=cls.funcionario.time,
            valor_hora=cls.funcionario.valor_hora,
        )
        cls.dim_func2 = DimFuncionario.objects.using("olap").create(
            id=cls.funcionario2.id,
            nome=cls.funcionario2.nome,
            time=cls.funcionario2.time,
            valor_hora=cls.funcionario2.valor_hora,
        )
        cls.dim_proj = DimProjeto.objects.using("olap").create(
            id=cls.projeto.id,
            nome=cls.projeto.nome,
            data_criacao=date(2025, 1, 1),
        )

        cls.dim_tempo_1 = DimTempo.objects.using("olap").create(
            hora=0,
            dia=1,
            mes=11,
            ano=2025,
            data_completa=date(2025, 11, 1),
            trimestre="Q4",
            dia_da_semana="Segunda",
        )
        cls.dim_tempo_2 = DimTempo.objects.using("olap").create(
            hora=0,
            dia=2,
            mes=11,
            ano=2025,
            data_completa=date(2025, 11, 2),
            trimestre="Q4",
            dia_da_semana="Terça",
        )
        cls.dim_tempo_3 = DimTempo.objects.using("olap").create(
            hora=0,
            dia=3,
            mes=11,
            ano=2025,
            data_completa=date(2025, 11, 3),
            trimestre="Q4",
            dia_da_semana="Quarta",
        )

        FatoRegistroHoras.objects.using("olap").create(
            funcionario=cls.dim_func1,
            projeto=cls.dim_proj,
            data=cls.dim_tempo_1,
            horas_trabalhadas=Decimal("4"),
            custo=Decimal("0"),
        )


class ListarMesesDisponiveisTests(ProdutividadeServiceBaseTestCase):
    def test_usa_datas_das_issues(self):
        meses = listar_meses_disponiveis()
        self.assertTrue(any(m["mes"] == 11 and m["ano"] == 2025 for m in meses))

    def test_listar_meses_disponiveis_com_dados(self):
        meses = listar_meses_disponiveis()
        self.assertEqual(meses[0]["mes"], 11)
        self.assertEqual(meses[0]["ano"], 2025)

    def test_listar_meses_disponiveis_sem_registros(self):
        Issue.objects.all().delete()
        meses = listar_meses_disponiveis()
        self.assertEqual(len(meses), 1)

    @mock.patch("apps.relatorios.produtividade.services.datetime")
    def test_retorna_mes_atual_quando_sem_dados(self, mock_datetime):
        mock_datetime.now.return_value = datetime(2024, 12, 15, 10, 0, 0)
        Issue.objects.all().delete()
        RegistroProdutividade.objects.all().delete()
        MetaProdutividade.objects.all().delete()

        meses = services.listar_meses_disponiveis()

        self.assertEqual(meses, [{"mes": 12, "ano": 2024, "mes_nome": "Dezembro"}])


class ListarDiasDisponiveisTests(ProdutividadeServiceBaseTestCase):
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
        dias_dim = _listar_dias_mes(11, 2025)
        self.assertEqual(dias_dim, [1, 2, 3])

        dias_fallback = _listar_dias_mes(1, 2025)
        self.assertEqual(dias_fallback[0], 1)
        self.assertEqual(dias_fallback[-1], 31)

    def test_calcular_spends_por_dev(self):
        dados = calcular_spends_por_dev_com_legendas(11, 2025)
        self.assertIn("dias", dados)
        self.assertTrue(dados["resultados"])
        self.assertEqual(dados["resultados"][-1]["funcionario"], "REALIZADO")

    def test_calcular_spends_sem_funcionarios(self):
        resultado = _calcular_spends_por_dev(11, 2025, [1, 2], equipe="Inexistente")
        self.assertEqual(resultado, [])

    def test_buscas_de_fontes_de_dados(self):
        funcionarios = _buscar_funcionarios(None)
        registros, horas_issue, horas_fato = _buscar_fontes_horas(
            funcionarios, 11, 2025
        )
        self.assertTrue(registros)
        self.assertTrue(horas_issue)
        self.assertTrue(horas_fato)

    def test_registros_diarios_e_horas_issue(self):
        funcionarios = [self.funcionario.id]
        registros = _buscar_registros_diarios(11, 2025, funcionarios)
        self.assertEqual(registros[(self.funcionario.id, 1)], Decimal("8"))

        horas_issue = _buscar_horas_issue(11, 2025, funcionarios)
        self.assertIn((self.funcionario.id, 1), horas_issue)

    def test_horas_fato(self):
        funcionarios = [self.funcionario.id]
        horas = _buscar_horas_fato(11, 2025, funcionarios)
        self.assertEqual(horas[(self.funcionario.id, 1)], Decimal("4"))

    def test_atualizar_codigo_especial_fluxos(self):
        _, _ = _atualizar_codigo_especial(self.funcionario.id, 11, 2025, 10, "FE")

        data = services.calcular_spends_por_dev_com_legendas(11, 2025)

        resultado = data["resultados"][0]
        self.assertEqual(resultado["real"], 13.0)
        self.assertEqual(resultado["dias"][1], 8.0)
        self.assertEqual(resultado["dias"][2], 2.0)
        self.assertEqual(resultado["dias"][3], 3.0)
        self.assertEqual(resultado["meta"], 200.0)
        self.assertAlmostEqual(resultado["percentual"], round(13 / 200 * 100, 1))
        self.assertIn("REALIZADO", data["resultados"][-1]["funcionario"])

    @mock.patch(
        "apps.relatorios.produtividade.services._buscar_funcionarios", return_value=[]
    )
    def test_calcular_spends_sem_funcionarios(self, mock_buscar):
        resultado = services._calcular_spends_por_dev(7, 2025, [1, 2], None)

        self.assertEqual(resultado, [])
        mock_buscar.assert_called_once_with(None)

    def test_buscar_funcionarios_filtra_por_equipe(self):
        Funcionario.objects.all().delete()
        Funcionario.objects.create(nome="Alice", time="Alpha")
        Funcionario.objects.create(nome="Bob", time="Beta")

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
        func = Funcionario.objects.create(nome="Carol")
        RegistroProdutividade.objects.create(
            funcionario=func, dia=date(2025, 7, 2), valor=Decimal("6")
        )

        resultado = services._buscar_registros_diarios(7, 2025, [func.id])

        self.assertEqual(resultado[(func.id, 2)], Decimal("6"))

    def test_buscar_horas_issue_converte_segundos_em_horas(self):
        func = Funcionario.objects.create(nome="Alice")
        projeto = Projeto.objects.create(nome="Projeto Horas")
        Issue.objects.create(
            jira_id=10,
            jira_key="PH-1",
            projeto=projeto,
            titulo="Apontamento",
            funcionario=func,
            tempo_gasto_seconds=7200,
            criado_em="2025-07-03T12:00:00Z",
        )

        resultado = services._buscar_horas_issue(7, 2025, [func.id])

        self.assertEqual(resultado[(func.id, 3)], Decimal("2"))

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

    @mock.patch(
        "apps.relatorios.produtividade.services._possui_horas_fato", return_value=False
    )
    def test_atualiza_registro_com_legenda(self, mock_horas):
        func = Funcionario.objects.create(nome="Alice")
        sucesso, erro = services.atualizar_multiplos_dias(func.id, 7, 2025, [1], "FE")
        self.assertTrue(sucesso)
        self.assertIsNone(erro)
        registro = RegistroProdutividade.objects.get(funcionario=func)
        self.assertEqual(registro.valor, Decimal("-1"))
        mock_horas.assert_called_once()

    @mock.patch(
        "apps.relatorios.produtividade.services._possui_horas_fato", return_value=True
    )
    def test_atualiza_registro_bloqueia_quando_ha_horas(self, mock_horas):
        func = Funcionario.objects.create(nome="Alice")
        sucesso, erro = services.atualizar_multiplos_dias(func.id, 7, 2025, [1], "FE")
        self.assertFalse(sucesso)
        self.assertIn("histórico", erro)

        RegistroProdutividade.objects.using(OLTP_ALIAS).create(
            funcionario=self.funcionario,
            dia=date(2025, 11, 4),
            valor=Decimal("4"),
        )
        MetaProdutividade.objects.create(
            funcionario=func, mes=7, ano=2025, meta_horas=Decimal("200")
        )
        valor = services.obter_meta_funcionario(func, 7, 2025)
        self.assertEqual(valor, 200.0)


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
