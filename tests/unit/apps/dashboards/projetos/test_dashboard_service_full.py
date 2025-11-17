# pylint: disable=protected-access

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase

from apps.dashboards.projetos.services import (
    CustoPorDesenvolvedorService,
    DashboardProjetoError,
    DashboardProjetoService,
    IssuesBugsDashboardService,
    OrcamentoInvalidoError,
    ProjetoNaoEncontradoError,
)
from apps.relatorios.models import Funcionario, Issue
from apps.relatorios.models import Projeto as ProjetoOLTP
from apps.relatorios.models import TipoIssue
from olap_models.models import DimFuncionario, DimProjeto, DimTempo, FatoRegistroHoras


class DashboardProjetoServiceTests(TestCase):
    databases = {"default", "olap"}

    @classmethod
    def setUpTestData(cls):
        cls.projeto_oltp = ProjetoOLTP.objects.create(
            nome="Projeto OLTP",
            orcamento_previsto=Decimal("10000.00"),
        )

        cls.dim_projeto = DimProjeto.objects.using("olap").create(
            id=cls.projeto_oltp.id,
            nome="Projeto OLAP",
            data_criacao=date(2024, 1, 1),
        )

        cls.funcionario = DimFuncionario.objects.using("olap").create(
            nome="Alice Developer",
            valor_hora=Decimal("80.00"),
        )

        cls.dim_tempo = DimTempo.objects.using("olap").create(
            data_completa=date(2024, 1, 15),
            dia=15,
            mes=1,
            ano=2024,
            trimestre="Q1",
            dia_da_semana="Segunda",
        )

        FatoRegistroHoras.objects.using("olap").create(
            funcionario=cls.funcionario,
            projeto=cls.dim_projeto,
            data=cls.dim_tempo,
            horas_trabalhadas=Decimal("40.00"),
            custo=Decimal("2000.00"),
        )

        cls.funcionario_oltp = Funcionario.objects.create(
            nome="Alice OLTP",
            valor_hora=Decimal("120.00"),
        )

        cls.tipo_issue = TipoIssue.objects.create(
            nome="Bug",
            descricao="Falha",
            jira_id=123,
            projeto=cls.projeto_oltp,
        )

        cls.issue = Issue.objects.create(
            jira_id=999,
            jira_key="BUG-999",
            projeto=cls.projeto_oltp,
            titulo="Bug crítico",
            tipo_issue=cls.tipo_issue,
            tempo_gasto_seconds=7200,
            funcionario=cls.funcionario_oltp,
            status="Em progresso",
        )

    def test_montar_contexto_dashboard_com_dados_retornar_metricas(self):
        contexto = DashboardProjetoService.montar_contexto_dashboard(
            self.projeto_oltp.id
        )

        self.assertEqual(contexto.projeto_selecionado_id, self.projeto_oltp.id)
        projeto = contexto.projetos_dimensao[0]
        self.assertEqual(projeto["nome_projeto"], "Projeto OLTP")
        self.assertGreater(projeto["percentual_utilizado"], 0)
        self.assertTrue(contexto.dados_grafico["has_data"])
        self.assertGreater(len(projeto["custo_por_dev"]), 0)
        self.assertIn("issues_bugs", projeto)
        self.assertEqual(projeto["issues_bugs"]["cards"]["total_bugs"], 1)
        self.assertEqual(len(projeto["issues_bugs"]["itens"]), 1)

    @patch.object(DashboardProjetoService, "_anexar_estatisticas_olap")
    @patch.object(DashboardProjetoService, "_montar_contextos_basicos", return_value={})
    def test_montar_contexto_dashboard_sem_dados(self, mock_contextos, _mock_anexar):
        contexto = DashboardProjetoService.montar_contexto_dashboard(None)

        self.assertEqual(contexto.projetos_dimensao, [])
        self.assertFalse(contexto.dados_grafico["has_data"])
        mock_contextos.assert_called_once()

    def test_obter_custo_por_dev_serializado(self):
        resultado = DashboardProjetoService._obter_custo_por_dev_serializado(
            self.projeto_oltp.id
        )

        self.assertEqual(len(resultado), 1)
        self.assertEqual(resultado[0]["funcionario_nome"], "Alice Developer")
        self.assertGreater(resultado[0]["custo_total"], 0)

    def test_atualizar_orcamento_previsto_sucesso(self):
        retorno = DashboardProjetoService.atualizar_orcamento_previsto(
            self.projeto_oltp.id, "12000"
        )

        self.assertAlmostEqual(retorno["orcamento_previsto"], 12000.0)
        projeto = ProjetoOLTP.objects.get(id=self.projeto_oltp.id)
        self.assertEqual(float(projeto.orcamento_previsto), 12000.0)

    def test_atualizar_orcamento_previsto_projeto_nao_encontrado(self):
        with self.assertRaises(ProjetoNaoEncontradoError):
            DashboardProjetoService.atualizar_orcamento_previsto(9999, "5000")

    def test_parse_valor_orcamento_validacoes(self):
        with self.assertRaises(OrcamentoInvalidoError):
            DashboardProjetoService._parse_valor_orcamento(None)
        with self.assertRaises(OrcamentoInvalidoError):
            DashboardProjetoService._parse_valor_orcamento("abc")
        with self.assertRaises(OrcamentoInvalidoError):
            DashboardProjetoService._parse_valor_orcamento("0")

        self.assertEqual(
            DashboardProjetoService._parse_valor_orcamento("123.45"),
            Decimal("123.45"),
        )

    def test_montar_dados_grafico_utiliza_servico(self):
        with (
            patch.object(
                CustoPorDesenvolvedorService,
                "obter_custo_por_desenvolvedor",
                return_value=[{"nome": "Alice", "custo": Decimal("100.00")}],
            ) as mock_obter,
            patch.object(
                CustoPorDesenvolvedorService,
                "formatar_para_grafico",
                return_value={
                    "labels": ["Alice"],
                    "values": [100.0],
                    "max_value": 110.0,
                },
            ) as mock_formatar,
        ):
            dados = DashboardProjetoService._montar_dados_grafico(self.projeto_oltp.id)

        mock_obter.assert_called_once_with(self.projeto_oltp.id)
        mock_formatar.assert_called_once()
        self.assertEqual(dados["labels"], ["Alice"])
        self.assertTrue(dados["has_data"])

    def test_calcular_metricas_financeiras(self):
        resultado = DashboardProjetoService._calcular_metricas_financeiras(
            self.projeto_oltp.id, Decimal("10000")
        )

        self.assertEqual(resultado["custo_realizado"], 2000.0)
        self.assertEqual(resultado["saldo_remanescente"], 8000.0)
        self.assertAlmostEqual(resultado["percentual_utilizado"], 20.0)

    def test_obter_dados_pdf_sucesso(self):
        dados = DashboardProjetoService.obter_dados_pdf(self.projeto_oltp.id)

        self.assertEqual(dados["nome_projeto"], "Projeto OLTP")
        self.assertIn("data_geracao", dados)
        self.assertIn("issues_bugs", dados)
        self.assertEqual(dados["issues_bugs"]["cards"]["total_bugs"], 1)

    def test_obter_dados_pdf_sem_projetos(self):
        contexto_vazio = DashboardProjetoService.montar_contexto_dashboard(
            self.projeto_oltp.id
        )
        contexto_vazio.projetos_dimensao.clear()

        with patch.object(
            DashboardProjetoService,
            "montar_contexto_dashboard",
            return_value=contexto_vazio,
        ):
            with self.assertRaises(DashboardProjetoError):
                DashboardProjetoService.obter_dados_pdf(self.projeto_oltp.id)

    def test_obter_dados_pdf_projeto_nao_encontrado(self):
        contexto = DashboardProjetoService.montar_contexto_dashboard(
            self.projeto_oltp.id
        )
        contexto.projeto_selecionado_id = 999

        with patch.object(
            DashboardProjetoService,
            "montar_contexto_dashboard",
            return_value=contexto,
        ):
            with self.assertRaises(ProjetoNaoEncontradoError):
                DashboardProjetoService.obter_dados_pdf(self.projeto_oltp.id)

    def test_normalizar_contexto_para_template_e_to_float(self):
        contexto = DashboardProjetoService._criar_contexto_base(
            projeto_id=1,
            nome="Teste",
            orcamento=Decimal("1500.50"),
        )
        contexto.update(
            {
                "total_horas": Decimal("10.5"),
                "total_custo": "300.75",
                "custo_realizado": None,
                "percentual_utilizado": Decimal("33.3"),
            }
        )

        normalizado = DashboardProjetoService._normalizar_contexto_para_template(
            contexto
        )
        self.assertEqual(normalizado["total_horas"], 10.5)
        self.assertEqual(normalizado["total_custo"], 300.75)
        self.assertEqual(normalizado["custo_realizado"], 0.0)
        self.assertEqual(normalizado["percentual_utilizado"], 33.3)

    def test_montar_contextos_basicos_completa_nome_e_data(self):
        fake_oltp = [
            SimpleNamespace(
                id=1,
                nome="",
                data_criacao=None,
                orcamento_previsto=None,
            )
        ]
        fake_dim = [
            SimpleNamespace(
                id=1,
                nome="Projeto Dim",
                data_criacao=date(2024, 2, 1),
            )
        ]

        with (
            patch("apps.dashboards.projetos.services.ProjetoOLTP.objects") as mock_oltp,
            patch("apps.dashboards.projetos.services.DimProjeto.objects") as mock_dim,
        ):
            mock_oltp.using.return_value.all.return_value.order_by.return_value = (
                fake_oltp
            )
            mock_dim.using.return_value.all.return_value = fake_dim

            contextos = DashboardProjetoService._montar_contextos_basicos()

        contexto = contextos[1]
        self.assertEqual(contexto["nome_projeto"], "Projeto Dim")
        self.assertEqual(contexto["data_criacao"], date(2024, 2, 1))

    def test_obter_custo_por_dev_serializado_sem_id(self):
        self.assertEqual(
            DashboardProjetoService._obter_custo_por_dev_serializado(0), []
        )


class IssuesBugsDashboardServiceTests(TestCase):
    databases = {"default"}

    def setUp(self):
        self.projeto = ProjetoOLTP.objects.create(
            nome="Projeto Issues",
            orcamento_previsto=Decimal("5000.00"),
        )
        self.funcionario = Funcionario.objects.create(
            nome="Dev QA",
            valor_hora=Decimal("150.00"),
        )
        self.tipo_issue = TipoIssue.objects.create(
            nome="Bug",
            descricao="Tipo bug",
            jira_id=321,
            projeto=self.projeto,
        )
        self.tipo_story = TipoIssue.objects.create(
            nome="Story",
            descricao="Tipo issue",
            jira_id=322,
            projeto=self.projeto,
        )
        Issue.objects.create(
            jira_id=555,
            jira_key="BUG-555",
            projeto=self.projeto,
            titulo="Bug teste",
            tipo_issue=self.tipo_issue,
            tempo_gasto_seconds=3600,
            funcionario=self.funcionario,
            status="Concluído",
        )

    def test_obter_dados_para_projetos(self):
        dados = IssuesBugsDashboardService.obter_dados_para_projetos([self.projeto.id])
        self.assertIn(self.projeto.id, dados)
        info = dados[self.projeto.id]
        self.assertEqual(info["cards"]["total_bugs"], 1)
        self.assertEqual(info["cards"]["total_issues"], 0)
        self.assertAlmostEqual(info["cards"]["valor_total"], 150.0)
        self.assertEqual(len(info["itens"]), 1)
        self.assertEqual(info["itens"][0]["status"], "Concluído")

    def test_estrutura_vazia(self):
        vazio = IssuesBugsDashboardService.estrutura_vazia()
        self.assertEqual(vazio["cards"]["total_issues"], 0)
        self.assertEqual(vazio["cards"]["valor_total"], 0.0)
        self.assertEqual(vazio["chart"]["labels"], [])
        self.assertEqual(vazio["itens"], [])

    def test_oculta_itens_sem_horas_e_nao_atribuidos(self):
        Issue.objects.create(
            jira_id=556,
            jira_key="ISSUE-556",
            projeto=self.projeto,
            titulo="Issue pendente",
            tipo_issue=self.tipo_story,
            tempo_gasto_seconds=0,
            tempo_estimado_seconds=0,
            funcionario=None,
            status="Em progresso",
        )

        dados = IssuesBugsDashboardService.obter_dados_para_projetos([self.projeto.id])
        info = dados[self.projeto.id]

        self.assertEqual(info["cards"]["total_issues"], 1)
        self.assertEqual(info["cards"]["total_bugs"], 1)
        self.assertEqual(len(info["itens"]), 1)
        self.assertNotIn("ISSUE-556", [item["id"] for item in info["itens"]])
        self.assertEqual(sum(info["chart"]["values"]), len(info["itens"]))
        self.assertEqual(info["chart_por_tipo"]["issues"]["labels"], [])

    def test_cards_mantem_contagem_quando_somente_pendentes(self):
        Issue.objects.all().delete()
        Issue.objects.create(
            jira_id=600,
            jira_key="ISSUE-600",
            projeto=self.projeto,
            titulo="Issue sem horas",
            tipo_issue=self.tipo_story,
            tempo_gasto_seconds=0,
            tempo_estimado_seconds=0,
            funcionario=None,
            status="Novo",
        )

        dados = IssuesBugsDashboardService.obter_dados_para_projetos([self.projeto.id])
        info = dados[self.projeto.id]

        self.assertEqual(info["cards"]["total_issues"], 1)
        self.assertEqual(info["cards"]["total_bugs"], 0)
        self.assertEqual(info["itens"], [])
        self.assertEqual(info["chart"]["labels"], [])

    def test_serializar_issue_classifica_nao_iniciado(self):
        issue = Issue(
            jira_id=700,
            jira_key="ISSUE-700",
            projeto=self.projeto,
            titulo="Issue backlog",
            tipo_issue=self.tipo_story,
            tempo_gasto_seconds=0,
            tempo_estimado_seconds=0,
            funcionario=None,
            status="Backlog",
        )

        dado = IssuesBugsDashboardService._serializar_issue(issue)
        self.assertEqual(dado["status"], "Não iniciado")

    def test_serializar_issue_classifica_em_progresso_para_quem_tem_dev(self):
        issue = Issue(
            jira_id=701,
            jira_key="ISSUE-701",
            projeto=self.projeto,
            titulo="Issue em andamento",
            tipo_issue=self.tipo_story,
            tempo_gasto_seconds=0,
            tempo_estimado_seconds=7200,
            funcionario=self.funcionario,
            status="Em andamento",
        )

        dado = IssuesBugsDashboardService._serializar_issue(issue)
        self.assertEqual(dado["status"], "Em progresso")

    def test_serializar_issue_classifica_mr(self):
        issue = Issue(
            jira_id=702,
            jira_key="ISSUE-702",
            projeto=self.projeto,
            titulo="Issue em MR",
            tipo_issue=self.tipo_story,
            tempo_gasto_seconds=3600,
            funcionario=self.funcionario,
            status="Merge Request",
        )

        dado = IssuesBugsDashboardService._serializar_issue(issue)
        self.assertEqual(dado["status"], "MR")

    def test_serializar_issue_classifica_concluido(self):
        issue = Issue(
            jira_id=703,
            jira_key="ISSUE-703",
            projeto=self.projeto,
            titulo="Issue finalizada",
            tipo_issue=self.tipo_story,
            tempo_gasto_seconds=7200,
            funcionario=self.funcionario,
            status="Done",
        )

        dado = IssuesBugsDashboardService._serializar_issue(issue)
        self.assertEqual(dado["status"], "Concluído")
