from __future__ import annotations

from datetime import datetime

from django.http import HttpResponse
from django.test import TestCase
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph

from apps.relatorios.comparacao.services import ComparacaoService
from apps.relatorios.models import (
    Cargo,
    Funcionario,
    Issue,
    PlanejamentoProjeto,
    Projeto,
    TipoIssue,
)


class ComparacaoServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cargo = Cargo.objects.create(sigla="DEV")
        cls.func1 = Funcionario.objects.create(nome="Ana Dev", cargo=cargo)
        cls.func2 = Funcionario.objects.create(nome="Beto QA", cargo=cargo)

        cls.projeto_a = Projeto.objects.create(nome="Projeto Alpha")
        cls.projeto_b = Projeto.objects.create(nome="Projeto Beta")

        cls.tipo_issue_a = TipoIssue.objects.create(
            nome="Tarefa",
            jira_id=111,
            projeto=cls.projeto_a,
            data_criacao=datetime(2025, 1, 1).date(),
        )
        cls.tipo_issue_b = TipoIssue.objects.create(
            nome="Bug",
            jira_id=112,
            projeto=cls.projeto_b,
            data_criacao=datetime(2025, 1, 1).date(),
        )

        Issue.objects.create(
            jira_id=1,
            jira_key="ALPHA-1",
            projeto=cls.projeto_a,
            titulo="Feature 1",
            tipo_issue=cls.tipo_issue_a,
            criado_em=datetime(2025, 1, 10, 10, 0),
            tempo_gasto_seconds=7200,
            tempo_estimado_seconds=3600,
            funcionario=cls.func1,
        )
        Issue.objects.create(
            jira_id=2,
            jira_key="ALPHA-2",
            projeto=cls.projeto_a,
            titulo="Feature 2",
            tipo_issue=cls.tipo_issue_a,
            criado_em=datetime(2025, 2, 5, 11, 0),
            tempo_gasto_seconds=3600,
            tempo_estimado_seconds=3600,
            funcionario=cls.func2,
        )
        Issue.objects.create(
            jira_id=3,
            jira_key="BETA-1",
            projeto=cls.projeto_b,
            titulo="Bugfix",
            tipo_issue=cls.tipo_issue_b,
            criado_em=datetime(2025, 2, 20, 12, 0),
            tempo_gasto_seconds=1800,
            tempo_estimado_seconds=3600,
            funcionario=cls.func1,
        )

        PlanejamentoProjeto.objects.create(
            projeto=cls.projeto_a, ano=2025, horas_previstas=200
        )

    def test_soma_horas_por_dev_mes(self):
        horas = ComparacaoService.soma_horas_por_dev_mes(2025, "Projeto Alpha")
        self.assertIn("Ana Dev", horas)
        self.assertEqual(horas["Ana Dev"][1], 2.0)  # 7200 segundos = 2h

    def test_soma_horas_previstas_por_dev_mes(self):
        horas = ComparacaoService.soma_horas_previstas_por_dev_mes(
            2025, "Projeto Alpha"
        )
        self.assertAlmostEqual(horas["Ana Dev"][1], 1.0)

    def test_totais_anuais_e_diferenca(self):
        totais = ComparacaoService.totais_anuais_e_diferenca(2025, "Projeto Alpha")
        self.assertIn("Ana Dev", totais)
        self.assertIn("diferenca", totais["Ana Dev"])
        self.assertNotEqual(totais["Ana Dev"]["diferenca"], 0)

    def test_get_nome_projetos(self):
        nomes = ComparacaoService.get_nome_projetos()
        self.assertEqual(nomes, ["Projeto Alpha", "Projeto Beta"])

    def test_criar_estilo_e_container(self):
        styles = getSampleStyleSheet()
        estilo = ComparacaoService._criar_estilo_padrao(
            "Custom", styles["Normal"], fontSize=9
        )
        self.assertEqual(estilo.fontSize, 9)
        paragrafo = Paragraph("Teste", estilo)
        container = ComparacaoService._criar_container_tabela(paragrafo, 200)
        self.assertEqual(container._argW[0], 200)

    def test_preparar_dados_para_relatorio(self):
        dados = ComparacaoService._preparar_dados_para_relatorio(2025, "Projeto Alpha")
        self.assertEqual(dados["ano"], 2025)
        self.assertIn("Ana Dev", dados["por_dev"])

    def test_gerar_pdf_e_exportar_relatorio(self):
        dados = ComparacaoService._preparar_dados_para_relatorio(2025, "Projeto Alpha")
        buffer = ComparacaoService._gerar_pdf(dados, 200, "Projeto Alpha", 2025)
        self.assertGreater(len(buffer.getvalue()), 0)

        response = ComparacaoService.exportar_relatorio_pdf(2025, "Projeto Alpha", 200)
        self.assertIsInstance(response, HttpResponse)
        self.assertIn("application/pdf", response.headers["Content-Type"])

    def test_cards_resumo_e_metricas(self):
        dados = ComparacaoService._preparar_dados_para_relatorio(2025, "Projeto Alpha")
        cards = ComparacaoService._criar_cards_resumo(dados, 200)
        self.assertTrue(cards)

        total, count = ComparacaoService._obter_metricas_resumo(dados)
        self.assertGreater(total, 0)
        self.assertEqual(count, len(dados["por_dev"]))

        vazio_total, vazio_count = ComparacaoService._obter_metricas_resumo(
            {"por_dev": {}}
        )
        self.assertEqual((vazio_total, vazio_count), (0, 0))

    def test_criar_card_individual(self):
        card = ComparacaoService._criar_card_individual(
            "Título",
            "10h",
            "Descrição",
            colors.HexColor("#123456"),
            info_extra="Extra",
        )
        self.assertEqual(card._nrows, 4)

    def test_tabela_comparacao_com_dados_e_vazia(self):
        dados = ComparacaoService._preparar_dados_para_relatorio(2025, "Projeto Alpha")
        tabela = ComparacaoService._criar_tabela_comparacao(dados)
        self.assertTrue(tabela)
        vazio = ComparacaoService._criar_tabela_comparacao({"por_dev": {}})
        self.assertEqual(vazio, [])

    def test_obter_estilo_tabela(self):
        estilo = ComparacaoService._obter_estilo_tabela()
        self.assertGreater(len(estilo.getCommands()), 0)

    def test_secao_graficos_e_subsecao(self):
        dados = ComparacaoService._preparar_dados_para_relatorio(2025, "Projeto Alpha")
        styles = getSampleStyleSheet()
        secoes = ComparacaoService._criar_secao_graficos(dados, 200, styles)
        self.assertTrue(secoes)

        drawing = Drawing(100, 50)
        subsecao = ComparacaoService._criar_subsecao_grafico(
            "Título Gráfico", drawing, styles
        )
        self.assertEqual(len(subsecao), 3)

    def test_criar_graficos(self):
        dados = ComparacaoService._preparar_dados_para_relatorio(2025, "Projeto Alpha")
        pie = ComparacaoService._criar_grafico_pizza(dados)
        self.assertIsNotNone(pie)

        barras = ComparacaoService._criar_grafico_barras(dados, 200)
        self.assertIsNotNone(barras)

        vazio = ComparacaoService._criar_grafico_pizza({"por_dev": {}})
        self.assertIsNone(vazio)

    def test_get_e_set_horas_previstas(self):
        horas = ComparacaoService.get_horas_previstas_projeto(2025, "Projeto Alpha")
        self.assertEqual(horas, 200.0)

        resposta = ComparacaoService.set_horas_previstas_projeto(
            "Projeto Alpha", 2025, 250
        )
        self.assertIsInstance(resposta, HttpResponse)
        self.assertEqual(
            ComparacaoService.get_horas_previstas_projeto(2025, "Projeto Alpha"), 250.0
        )

    def test_get_projeto(self):
        projeto = ComparacaoService._get_projeto("Projeto Alpha")
        self.assertEqual(projeto, self.projeto_a)
        self.assertIsNone(ComparacaoService._get_projeto(""))
