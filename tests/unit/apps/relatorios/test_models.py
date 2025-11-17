from datetime import datetime

from django.test import TestCase

from apps.relatorios.models import (
    Cargo,
    Funcionario,
    Issue,
    MetaProdutividade,
    PlanejamentoProjeto,
    Projeto,
    RegistroProdutividade,
    TipoIssue,
)


class RelatoriosModelsTests(TestCase):
    def setUp(self):
        self.cargo = Cargo.objects.create(sigla="DEV")
        self.funcionario = Funcionario.objects.create(nome="Alice", cargo=self.cargo)
        self.projeto = Projeto.objects.create(nome="Projeto X")
        self.tipo_issue = TipoIssue.objects.create(
            nome="Bug",
            jira_id=123,
            projeto=self.projeto,
            data_criacao=datetime(2025, 1, 1).date(),
        )

    def test_str_representations(self):
        issue = Issue.objects.create(
            jira_id=1,
            jira_key="PROJ-1",
            projeto=self.projeto,
            titulo="Corrigir bug",
            tipo_issue=self.tipo_issue,
        )
        planejamento = PlanejamentoProjeto.objects.create(
            projeto=self.projeto, ano=2025, horas_previstas=100
        )
        registro = RegistroProdutividade.objects.create(
            funcionario=self.funcionario, dia=datetime(2025, 1, 2).date(), valor=8
        )
        meta = MetaProdutividade.objects.create(
            funcionario=self.funcionario, ano=2025, mes=1, meta_horas=154
        )

        self.assertEqual(str(self.cargo), "DEV")
        self.assertIn("Projeto X", str(self.projeto))
        self.assertIn("Bug", str(self.tipo_issue))
        self.assertIn("Corrigir bug", str(issue))
        self.assertEqual(str(self.funcionario), "Alice")
        self.assertIn("2025", str(planejamento))
        self.assertIn("Alice", str(registro))
        self.assertIn("2025", str(meta))
