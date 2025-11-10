"""Testes unitários para IssuesBugsService."""

from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import TestCase

from apps.dashboards.projetos.issues_bugs_service import IssuesBugsService
from olap_models.models import DimFuncionario, DimIssue, DimProjeto, DimTempo, FatoRegistroHoras


class IssuesBugsServiceTest(TestCase):
    """Testes para o service de issues e bugs."""

    databases = {"default", "olap"}

    @classmethod
    def setUpTestData(cls):
        """Configura dados de teste para todos os métodos."""
        cls.projeto = DimProjeto.objects.using("olap").create(nome="Projeto Teste")

        cls.funcionario = DimFuncionario.objects.using("olap").create(
            nome="João Silva", valor_hora=Decimal("50.00")
        )

        cls.tempo = DimTempo.objects.using("olap").create(
            data_completa="2024-01-15",
            dia=15,
            mes=1,
            ano=2024,
            trimestre="Q1",
            dia_da_semana="Segunda-feira",
        )

        cls.tempo2 = DimTempo.objects.using("olap").create(
            data_completa="2024-01-16",
            dia=16,
            mes=1,
            ano=2024,
            trimestre="Q1",
            dia_da_semana="Terça-feira",
        )

        cls.issue_tarefa = DimIssue.objects.using("olap").create(
            issue_id="PROJ-001",
            issue_type="Tarefa",
            issue_title="Implementar funcionalidade X",
            created_date="2024-01-10",
        )

        cls.issue_bug = DimIssue.objects.using("olap").create(
            issue_id="PROJ-002",
            issue_type="Bug",
            issue_title="Corrigir erro Y",
            created_date="2024-01-11",
        )

    def setUp(self):
        """Configura fixtures antes de cada teste."""
        FatoRegistroHoras.objects.using("olap").create(
            funcionario=self.funcionario,
            projeto=self.projeto,
            data=self.tempo,
            issue=self.issue_tarefa,
            horas_trabalhadas=Decimal("10.00"),
            custo=Decimal("500.00"),
        )

        FatoRegistroHoras.objects.using("olap").create(
            funcionario=self.funcionario,
            projeto=self.projeto,
            data=self.tempo2,
            issue=self.issue_bug,
            horas_trabalhadas=Decimal("5.00"),
            custo=Decimal("250.00"),
        )

    def test_obter_dados_dashboard_sem_projeto(self):
        """Testa obtenção de dados sem filtro de projeto."""
        resultado = IssuesBugsService.obter_dados_dashboard()

        self.assertIn("issues", resultado)
        self.assertIn("bugs", resultado)
        self.assertIn("totais", resultado)
        self.assertGreater(len(resultado["issues"]), 0)
        self.assertGreater(len(resultado["bugs"]), 0)

    def test_obter_dados_dashboard_com_projeto(self):
        """Testa obtenção de dados filtrados por projeto."""
        resultado = IssuesBugsService.obter_dados_dashboard(self.projeto.id)

        self.assertEqual(len(resultado["issues"]), 1)
        self.assertEqual(len(resultado["bugs"]), 1)
        self.assertEqual(resultado["issues"][0]["id"], "PROJ-001")
        self.assertEqual(resultado["bugs"][0]["id"], "PROJ-002")

    def test_estrutura_dados_issue(self):
        """Testa estrutura dos dados de uma issue."""
        resultado = IssuesBugsService.obter_dados_dashboard(self.projeto.id)
        issue = resultado["issues"][0]

        self.assertIn("id", issue)
        self.assertIn("tipo", issue)
        self.assertIn("developer", issue)
        self.assertIn("status", issue)
        self.assertIn("horas", issue)
        self.assertIn("custo", issue)
        self.assertEqual(issue["tipo"], "issue")

    def test_calcular_totais(self):
        """Testa cálculo de totalizações."""
        dados_issues = [
            {"status": "Em progresso", "custo": 100.0},
            {"status": "Concluído", "custo": 200.0},
        ]
        dados_bugs = [{"status": "Não iniciado", "custo": 50.0}]

        totais = IssuesBugsService._calcular_totais(dados_issues, dados_bugs)

        self.assertEqual(totais["total_issues"], 2)
        self.assertEqual(totais["total_bugs"], 1)
        self.assertEqual(totais["issues_abertas"], 1)
        self.assertEqual(totais["bugs_ativos"], 1)
        self.assertEqual(totais["valor_total"], 350.0)

    def test_inferir_status_padronizado_sem_horas(self):
        """Testa inferência de status quando não há horas."""
        item = {"total_horas": 0}
        status = IssuesBugsService._inferir_status_padronizado(item)
        self.assertEqual(status, "Não iniciado")

    def test_inferir_status_padronizado_com_horas(self):
        """Testa inferência de status quando há horas."""
        item = {"total_horas": 10}
        status = IssuesBugsService._inferir_status_padronizado(item)
        self.assertEqual(status, "Em progresso")

    def test_obter_dados_por_tipo_filtra_tarefas(self):
        """Testa filtragem por tipo Tarefa."""
        resultado = IssuesBugsService._obter_dados_por_tipo(
            self.projeto.id, ["Tarefa"], "issue"
        )

        self.assertEqual(len(resultado), 1)
        self.assertEqual(resultado[0]["id"], "PROJ-001")
        self.assertEqual(resultado[0]["tipo"], "issue")

    def test_obter_dados_por_tipo_filtra_bugs(self):
        """Testa filtragem por tipo Bug."""
        resultado = IssuesBugsService._obter_dados_por_tipo(
            self.projeto.id, ["Bug"], "bug"
        )

        self.assertEqual(len(resultado), 1)
        self.assertEqual(resultado[0]["id"], "PROJ-002")
        self.assertEqual(resultado[0]["tipo"], "bug")

    def test_dados_sem_issue_sao_ignorados(self):
        """Testa que registros sem issue são ignorados."""
        tempo3 = DimTempo.objects.using("olap").create(
            data_completa="2024-01-17",
            dia=17,
            mes=1,
            ano=2024,
            trimestre="Q1",
            dia_da_semana="Quarta-feira",
        )

        FatoRegistroHoras.objects.using("olap").create(
            funcionario=self.funcionario,
            projeto=self.projeto,
            data=tempo3,
            issue=None,
            horas_trabalhadas=Decimal("8.00"),
            custo=Decimal("400.00"),
        )

        resultado = IssuesBugsService.obter_dados_dashboard(self.projeto.id)

        self.assertEqual(len(resultado["issues"]), 1)
        self.assertEqual(len(resultado["bugs"]), 1)
