"""Testes do relatório de comparação anual."""

from datetime import datetime

from django.test import TestCase
from django.utils import timezone

from apps.relatorios.comparacao.services import ComparacaoService
from apps.relatorios.models import Cargo, Funcionario, Issue, Projeto


class SomaHorasTest(TestCase):
    """Testa os serviços de soma de horas do relatório de comparação anual."""

    def setUp(self):
        # dados comuns
        self.cargo = Cargo.objects.create(sigla="DEV")
        self.func1 = Funcionario.objects.create(nome="Renato", cargo=self.cargo)
        self.func2 = Funcionario.objects.create(nome="Maria", cargo=self.cargo)
        self.projeto = Projeto.objects.create(nome="Projeto X")

        # Issues de janeiro para Renato: 10h + 5h realizados, 20h estimados
        Issue.objects.create(
            jira_id=1,
            jira_key="PRJ-1",
            titulo="Planejar sprint",
            projeto=self.projeto,
            funcionario=self.func1,
            criado_em=datetime(2025, 1, 10, 10, 0, 0),
            tempo_gasto_seconds=10 * 3600,
            tempo_estimado_seconds=20 * 3600,
        )
        Issue.objects.create(
            jira_id=2,
            jira_key="PRJ-2",
            titulo="Revisar arquitetura",
            projeto=self.projeto,
            funcionario=self.func1,
            criado_em=datetime(2025, 1, 20, 9, 0, 0),
            tempo_gasto_seconds=5 * 3600,
            tempo_estimado_seconds=0,
        )

        # Issue de fevereiro para Maria: 8h realizados/estimados
        Issue.objects.create(
            jira_id=3,
            jira_key="PRJ-3",
            titulo="Configurar pipelines",
            projeto=self.projeto,
            funcionario=self.func2,
            criado_em=datetime(2025, 2, 5, 14, 0, 0),
            tempo_gasto_seconds=8 * 3600,
            tempo_estimado_seconds=8 * 3600,
        )

    def test_soma_horas_realizadas(self):
        """Testa a soma das horas realizadas por desenvolvedor e mês."""
        resultado = ComparacaoService.soma_horas_por_dev_mes(2025)
        self.assertIn("Renato", resultado)
        self.assertIn("Maria", resultado)
        self.assertEqual(resultado["Renato"][1], 15.0)
        self.assertEqual(resultado["Maria"][2], 8.0)

    def test_soma_horas_previstas(self):
        """Testa a soma das horas previstas por desenvolvedor e mês."""
        previsto = ComparacaoService.soma_horas_previstas_por_dev_mes(2025)
        self.assertIn("Renato", previsto)
        self.assertIn("Maria", previsto)
        self.assertEqual(previsto["Renato"][1], 20.0)
        self.assertEqual(previsto["Maria"][2], 8.0)

    def test_totais_anuais_e_diferenca(self):
        """Testa o cálculo dos totais anuais e diferença."""
        resumo = ComparacaoService.totais_anuais_e_diferenca(2025)
        # Renato: previsto 20, realizado 15 -> diferença 5
        self.assertIn("Renato", resumo)
        self.assertAlmostEqual(resumo["Renato"]["total_previsto"], 20.0)
        self.assertAlmostEqual(resumo["Renato"]["total_realizado"], 15.0)
        self.assertAlmostEqual(resumo["Renato"]["diferenca"], 5.0)
        # Maria: previsto 8, realizado 8 -> diferença 0
        self.assertIn("Maria", resumo)
        self.assertAlmostEqual(resumo["Maria"]["total_previsto"], 8.0)
        self.assertAlmostEqual(resumo["Maria"]["total_realizado"], 8.0)
        self.assertAlmostEqual(resumo["Maria"]["diferenca"], 0.0)
