from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from django.test import TestCase
from reportlab.platypus import Table

from apps.relatorios.models import (
    Cargo,
    Funcionario,
    Issue,
    MetaProdutividade,
    Projeto,
    RegistroProdutividade,
    TipoIssue,
)
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


class ProdutividadeServicesTests(TestCase):
    databases = {"default", "olap"}

    @classmethod
    def setUpTestData(cls):
        cargo = Cargo.objects.create(sigla="DEV")
        cls.funcionario = Funcionario.objects.create(
            nome="Ana Dev", cargo=cargo, time="Equipe Azul", contrato="CLT"
        )
        cls.funcionario2 = Funcionario.objects.create(
            nome="Bruno QA", cargo=cargo, time="", contrato="ESTAGIARIO"
        )

        cls.projeto = Projeto.objects.create(nome="Projeto Prod")
        cls.tipo_issue = TipoIssue.objects.create(
            nome="Task",
            jira_id=999,
            projeto=cls.projeto,
            data_criacao=datetime(2025, 1, 1).date(),
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

        RegistroProdutividade.objects.using(OLTP_ALIAS).create(
            funcionario=cls.funcionario,
            dia=date(2025, 11, 1),
            valor=Decimal("8"),
        )
        RegistroProdutividade.objects.using(OLTP_ALIAS).create(
            funcionario=cls.funcionario,
            dia=date(2025, 11, 2),
            valor=Decimal("-1"),
        )

        MetaProdutividade.objects.using(OLTP_ALIAS).create(
            funcionario=cls.funcionario, mes=11, ano=2025, meta_horas=Decimal("160")
        )

        cls.dim_func1 = DimFuncionario.objects.using("olap").create(
            id=cls.funcionario.id,
            nome=cls.funcionario.nome,
            time=cls.funcionario.time,
        )
        cls.dim_func2 = DimFuncionario.objects.using("olap").create(
            id=cls.funcionario2.id,
            nome=cls.funcionario2.nome,
            time=cls.funcionario2.time,
        )
        cls.dim_proj = DimProjeto.objects.using("olap").create(nome="Dim Projeto")

        cls.dim_tempo_1 = DimTempo.objects.using("olap").create(
            hora=0,
            dia=1,
            mes=11,
            ano=2025,
            data_completa="2025-11-01",
            trimestre="Q4",
            dia_da_semana="Segunda",
        )
        cls.dim_tempo_2 = DimTempo.objects.using("olap").create(
            hora=0,
            dia=2,
            mes=11,
            ano=2025,
            data_completa="2025-11-02",
            trimestre="Q4",
            dia_da_semana="Terça",
        )

        FatoRegistroHoras.objects.using("olap").create(
            funcionario=cls.dim_func1,
            projeto=cls.dim_proj,
            data=cls.dim_tempo_1,
            horas_trabalhadas=Decimal("4"),
            custo=Decimal("0"),
        )

    def test_listar_meses_disponiveis_com_dados(self):
        meses = listar_meses_disponiveis()
        self.assertEqual(meses[0]["mes"], 11)
        self.assertEqual(meses[0]["ano"], 2025)

    def test_listar_meses_disponiveis_sem_registros(self):
        Issue.objects.all().delete()
        meses = listar_meses_disponiveis()
        self.assertEqual(len(meses), 1)

    def test_listar_equipes_disponiveis(self):
        equipes = listar_equipes_disponiveis()
        self.assertEqual(equipes, ["Equipe Azul"])

    def test_listar_dias_mes_com_dim_e_sem_dim(self):
        dias_dim = _listar_dias_mes(11, 2025)
        self.assertEqual(dias_dim, [1, 2])

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
        sucesso, msg = _atualizar_codigo_especial(
            self.funcionario.id, 11, 2025, 1, "FE"
        )
        self.assertFalse(sucesso)
        self.assertIn("histórico", msg)

        RegistroProdutividade.objects.using(OLTP_ALIAS).create(
            funcionario=self.funcionario,
            dia=date(2025, 11, 4),
            valor=Decimal("4"),
        )
        sucesso, msg = _atualizar_codigo_especial(
            self.funcionario.id, 11, 2025, 4, "FE"
        )
        self.assertFalse(sucesso)
        self.assertIn("horas lançadas", msg)

        RegistroProdutividade.objects.using(OLTP_ALIAS).create(
            funcionario=self.funcionario,
            dia=date(2025, 11, 3),
            valor=Decimal("-1"),
        )
        sucesso, msg = _atualizar_codigo_especial(
            self.funcionario.id, 11, 2025, 3, "NONE"
        )
        self.assertTrue(sucesso)
        sucesso, msg = _atualizar_codigo_especial(
            self.funcionario.id, 11, 2025, 5, "XX"
        )
        self.assertFalse(sucesso)
        sucesso, msg = _atualizar_codigo_especial(
            self.funcionario.id, 11, 2025, 5, "FE"
        )
        self.assertTrue(sucesso)

    def test_atualizar_multiplos_dias(self):
        ok, erro = atualizar_multiplos_dias(self.funcionario.id, 11, 2025, [2], "FE")
        self.assertTrue(ok)
        self.assertIsNone(erro)

    def test_possui_horas_fato(self):
        self.assertTrue(_possui_horas_fato(self.funcionario.id, date(2025, 11, 1)))
        self.assertFalse(_possui_horas_fato(self.funcionario.id, date(2025, 11, 3)))

    def test_meta_e_percentual(self):
        atualizar_meta_funcionario(self.funcionario.id, 11, 2025, 150)
        meta = obter_meta_funcionario(self.funcionario, 11, 2025)
        self.assertEqual(meta, 150.0)

        meta_padrao = obter_meta_funcionario(self.funcionario2, 11, 2025)
        self.assertGreater(meta_padrao, 0)

        self.assertGreater(_meta_padrao(self.funcionario, 11, 2025), 0)
        self.assertEqual(_percentual(Decimal("10"), Decimal("20")), 50.0)
        self.assertEqual(_percentual(Decimal("10"), Decimal("0")), 0.0)

    def test_dias_uteis(self):
        self.assertEqual(_dias_uteis_no_mes(11, 2025), 20)

    def test_formatar_valor_celula(self):
        self.assertEqual(_formatar_valor_celula(None), 0.0)
        valor = _formatar_valor_celula(Decimal(str(list(CODIGOS_REVERSOS.keys())[0])))
        self.assertIsInstance(valor, dict)
        self.assertEqual(_formatar_valor_celula(Decimal("0")), 0.0)
        self.assertEqual(_formatar_valor_celula(Decimal("1.2")), 1.2)

    def test_exportar_pdf_e_helpers(self):
        resultados = calcular_spends_por_dev_com_legendas(11, 2025)["resultados"]
        pdf = exportar_produtividade_pdf(11, 2025, resultados)
        self.assertGreater(len(pdf), 0)

        titulo = _criar_titulo_pdf(11, 2025)
        self.assertIn("Relatório de Produtividade", titulo.getPlainText())

        tabela, dias = _montar_tabela_pdf(
            [
                {
                    "funcionario": "Teste",
                    "dias": {1: 1, 2: {"value": "FE"}},
                    "real": 1,
                    "meta": 2,
                    "percentual": 50,
                }
            ]
        )
        self.assertEqual(tabela[1][1], 1)
        self.assertEqual(tabela[1][2], "FE")
        tabela_obj = _aplicar_estilo_pdf(
            Table(tabela, repeatRows=1),
            [{"funcionario": "REALIZADO"}],
            dias,
        )
        self.assertIsNotNone(tabela_obj)
