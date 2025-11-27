"""Testes unitários focados nos helpers puros do dashboard de projetos."""

from decimal import Decimal

from django.test import SimpleTestCase
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, Table

from apps.dashboards.projetos.services import (
    DEFAULT_STATUS_LABEL,
    DashboardProjetoPdfService,
    IssuesBugsDashboardService,
)


class IssuesBugsDashboardHelpersTests(SimpleTestCase):
    def test_obter_dados_para_projetos_retorna_vazio_para_ids_invalidos(self):
        self.assertEqual(IssuesBugsDashboardService.obter_dados_para_projetos([]), {})
        self.assertEqual(
            IssuesBugsDashboardService.obter_dados_para_projetos({None}), {}
        )

    def test_construir_dashboard_vazio(self):
        esperado = IssuesBugsDashboardService.estrutura_vazia()
        self.assertEqual(
            IssuesBugsDashboardService._construir_dashboard([]),
            esperado,
        )

    def test_calcular_chart_usa_palette_para_status_desconhecido(self):
        itens = [{"status": "Custom", "tipo": "issue"}]
        chart = IssuesBugsDashboardService._calcular_chart(itens)
        self.assertEqual(chart["labels"], ["Custom"])
        self.assertEqual(chart["values"], [1])
        self.assertEqual(
            chart["colors"][0], IssuesBugsDashboardService.COLOR_PALETTE[0]
        )

    def test_filtrar_itens_visiveis_vazio(self):
        self.assertEqual(IssuesBugsDashboardService._filtrar_itens_visiveis([]), [])

    def test_parse_float_trata_none_e_invalido(self):
        self.assertEqual(IssuesBugsDashboardService._parse_float(None), 0.0)
        self.assertEqual(IssuesBugsDashboardService._parse_float("abc"), 0.0)
        self.assertEqual(IssuesBugsDashboardService._parse_float("3.2"), 3.2)

    def test_is_nao_atribuido(self):
        self.assertTrue(IssuesBugsDashboardService._is_nao_atribuido(None))
        self.assertTrue(IssuesBugsDashboardService._is_nao_atribuido("Não atribuído"))
        self.assertFalse(IssuesBugsDashboardService._is_nao_atribuido("Lucas"))

    def test_is_mr_status(self):
        self.assertFalse(IssuesBugsDashboardService._is_mr_status(None))
        self.assertFalse(IssuesBugsDashboardService._is_mr_status(""))
        self.assertTrue(IssuesBugsDashboardService._is_mr_status("MR pronto"))

    def test_esta_concluido(self):
        self.assertFalse(IssuesBugsDashboardService._esta_concluido(None))
        self.assertFalse(IssuesBugsDashboardService._esta_concluido("doing"))
        self.assertTrue(IssuesBugsDashboardService._esta_concluido("done"))


class DashboardProjetoPdfServiceHelpersTests(SimpleTestCase):
    def setUp(self):
        self.base_style = getSampleStyleSheet()["Normal"]

    def test_truncate_text_curto_e_longo(self):
        curto = DashboardProjetoPdfService._truncate_text("abc", 5)
        longo = DashboardProjetoPdfService._truncate_text("abcdef", 5)
        self.assertEqual(curto, "abc")
        self.assertEqual(longo, "abcd…")

    def test_build_single_pie_table_sem_dados(self):
        tabela = DashboardProjetoPdfService._build_single_pie_table(
            "Titulo", None, self.base_style
        )
        self.assertIsInstance(tabela, Table)
        corpo = tabela._cellvalues[1][0]
        self.assertIsInstance(corpo, Paragraph)
        self.assertEqual(corpo.getPlainText(), "Sem dados disponíveis.")

    def test_build_single_pie_table_com_dados(self):
        chart = {"labels": ["A"], "values": [2], "colors": ["#000000"]}
        tabela = DashboardProjetoPdfService._build_single_pie_table(
            "Titulo", chart, self.base_style
        )
        self.assertIsInstance(tabela, Table)
        corpo = tabela._cellvalues[1][0]
        # corpo é uma Table com desenho e legenda
        self.assertIsInstance(corpo, Table)
        self.assertEqual(len(corpo._cellvalues), 2)

    def test_normalize_chart_data_fallback_palette(self):
        chart = {"labels": ["A", "B"], "values": [1, 2], "colors": ["#111111"]}
        labels, values, color_objs = DashboardProjetoPdfService._normalize_chart_data(
            chart
        )
        self.assertEqual(labels, ["A", "B"])
        self.assertEqual(values, [1, 2])
        self.assertEqual(len(color_objs), 2)
        self.assertEqual(
            color_objs[1], colors.HexColor(IssuesBugsDashboardService.COLOR_PALETTE[1])
        )

    def test_create_pie_drawing_labels_e_cores(self):
        valores = [1, 2]
        color_objs = [colors.red, colors.blue]
        desenho, pie = DashboardProjetoPdfService._create_pie_drawing(
            valores, color_objs
        )
        self.assertIsInstance(desenho, Drawing)
        self.assertIsInstance(pie, Pie)
        self.assertEqual(pie.data, valores)
        self.assertEqual(len(pie.labels), 2)
        self.assertEqual(pie.slices[0].fillColor, colors.red)
        self.assertEqual(pie.slices[1].fillColor, colors.blue)

    def test_create_pie_legend(self):
        labels = ["A", "B"]
        values = [1, 3]
        color_objs = [colors.red, colors.blue]
        tabela = DashboardProjetoPdfService._create_pie_legend(
            labels, values, color_objs, total=4
        )
        self.assertIsInstance(tabela, Table)
        self.assertEqual(len(tabela._cellvalues), 2)
        perc_text = tabela._cellvalues[0][2].getPlainText()
        self.assertIn("25.0%", perc_text)

    def test_build_issues_table_limita_itens(self):
        itens = []
        for idx in range(30):
            itens.append(
                {
                    "id": f"ISSUE-{idx}",
                    "tipo": "issue" if idx % 2 == 0 else "bug",
                    "developer": "Dev Teste",
                    "status": DEFAULT_STATUS_LABEL,
                    "horas": Decimal("1.23"),
                    "custo": Decimal("10.0"),
                }
            )
        tabela = DashboardProjetoPdfService._build_issues_table({"itens": itens})
        self.assertIsInstance(tabela, Table)
        # 1 linha de header + 25 itens
        self.assertEqual(len(tabela._cellvalues), 26)
        self.assertEqual(len(tabela._cellvalues[0]), 6)
