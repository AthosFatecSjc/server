"""Testes do relatório de comparação anual."""

from datetime import date

from django.test import TestCase

from apps.relatorios.comparacao.services import ComparacaoService
from apps.relatorios.models import (
    Cargo,
    ControleHorasEquipe,
    Funcionario,
    Projeto,
    TempoControleValores,
    TempoGastoEquipe,
)


class SomaHorasTest(TestCase):
    """Testa os serviços de soma de horas do relatório de comparação anual."""

    def setUp(self):
        # dados comuns
        self.cargo = Cargo.objects.create(sigla="DEV")
        self.func1 = Funcionario.objects.create(nome="Renato", cargo=self.cargo)
        self.func2 = Funcionario.objects.create(nome="Maria", cargo=self.cargo)
        self.projeto = Projeto.objects.create(nome="Projeto X")

        # realizado: Renato mês 1 = 10, somar mais 5 -> total 15
        ControleHorasEquipe.objects.create(
            mes=date(2025, 1, 1), projeto=self.projeto, funcionario=self.func1, horas=10
        )
        obj = ControleHorasEquipe.objects.get(
            mes=date(2025, 1, 1), projeto=self.projeto, funcionario=self.func1
        )
        obj.horas = obj.horas + 5
        obj.save()

        # realizado: Maria mês 2 = 8
        ControleHorasEquipe.objects.create(
            mes=date(2025, 2, 1), projeto=self.projeto, funcionario=self.func2, horas=8
        )

        # previstas: usaremos TempoGastoEquipe + TempoControleValores.total_meta
        # Renato mês 1 previsto 20
        tge1 = TempoGastoEquipe.objects.create(
            dia_semana="Seg",
            dia_mes=1,
            mes=date(2025, 1, 1),
            funcionario=self.func1,
            tempo_gasto=15,  # campo opcional para fonte alternativa
            meta=None,
        )
        TempoControleValores.objects.create(
            controle_tempo_equipe=tge1,
            realizado_equipe=15,
            total_real=15,
            total_meta=20,
            aproveitamento=75,
        )

        # Maria mês 2 previsto 8
        tge2 = TempoGastoEquipe.objects.create(
            dia_semana="Ter",
            dia_mes=1,
            mes=date(2025, 2, 1),
            funcionario=self.func2,
            tempo_gasto=8,
            meta=None,
        )
        TempoControleValores.objects.create(
            controle_tempo_equipe=tge2,
            realizado_equipe=8,
            total_real=8,
            total_meta=8,
            aproveitamento=100,
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
        previsto = ComparacaoService.soma_horas_previstas_por_dev_mes(
            2025
        )  # usa TempoControleValores por padrão
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
