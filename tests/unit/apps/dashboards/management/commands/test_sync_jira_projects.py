from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.db import IntegrityError
from django.test import TestCase

from apps.dashboards.management.commands.sync_jira_projects import (
    DEFAULT_ORCAMENTO,
    Command,
)
from apps.relatorios.models import Projeto


class SyncJiraProjectsCommandTests(TestCase):
    @patch(
        "apps.dashboards.management.commands.sync_jira_projects.JiraService.get_projects"
    )
    def test_sync_cria_projetos(self, mock_get_projects):
        mock_get_projects.return_value = [
            {"name": "Projeto Alpha"},
            {"name": "Projeto Beta"},
        ]

        out = StringIO()
        call_command("sync_jira_projects", stdout=out)

        self.assertEqual(Projeto.objects.count(), 2)
        projeto = Projeto.objects.get(nome="Projeto Alpha")
        self.assertEqual(float(projeto.orcamento_previsto), DEFAULT_ORCAMENTO)

        output = out.getvalue()
        self.assertIn(
            "Sincronização concluída: 2 criados, 0 atualizados, 0 ignorados.", output
        )

    @patch(
        "apps.dashboards.management.commands.sync_jira_projects.JiraService.get_projects"
    )
    def test_sync_atualiza_projetos_existentes(self, mock_get_projects):
        Projeto.objects.create(nome="Projeto Alpha", orcamento_previsto=5000)
        mock_get_projects.return_value = [
            {"name": "Projeto Alpha"},
        ]

        out = StringIO()
        call_command("sync_jira_projects", stdout=out)

        self.assertEqual(Projeto.objects.count(), 1)
        projeto = Projeto.objects.get(nome="Projeto Alpha")
        self.assertEqual(float(projeto.orcamento_previsto), DEFAULT_ORCAMENTO)

        output = out.getvalue()
        self.assertIn(
            "Sincronização concluída: 0 criados, 1 atualizados, 0 ignorados.", output
        )

    @patch(
        "apps.dashboards.management.commands.sync_jira_projects.JiraService.get_projects"
    )
    def test_sync_atualiza_projeto_com_ids(self, mock_get_projects):
        Projeto.objects.create(
            nome="Projeto Alpha", jira_id=123, jira_key="OLD", orcamento_previsto=100
        )
        mock_get_projects.return_value = [
            {"name": "Projeto Alpha", "id": "456", "key": "NEW"},
        ]

        call_command("sync_jira_projects")

        projeto = Projeto.objects.get(nome="Projeto Alpha")
        self.assertEqual(projeto.jira_id, 456)
        self.assertEqual(projeto.jira_key, "NEW")
        self.assertEqual(float(projeto.orcamento_previsto), DEFAULT_ORCAMENTO)

    @patch(
        "apps.dashboards.management.commands.sync_jira_projects.JiraService.get_projects"
    )
    def test_sync_lida_com_lista_vazia(self, mock_get_projects):
        mock_get_projects.return_value = []

        out = StringIO()
        call_command("sync_jira_projects", stdout=out)

        self.assertEqual(Projeto.objects.count(), 0)
        self.assertIn("Nenhum projeto retornado pela API do Jira.", out.getvalue())

    @patch("apps.dashboards.management.commands.sync_jira_projects.logger")
    @patch(
        "apps.dashboards.management.commands.sync_jira_projects.JiraService.get_projects"
    )
    def test_sync_ignora_projetos_sem_nome(self, mock_get_projects, mock_logger):
        mock_get_projects.return_value = [
            {"name": "   "},
            {"key": "ABC"},
            {"name": "Projeto Válido"},
        ]

        out = StringIO()
        call_command("sync_jira_projects", stdout=out)

        self.assertEqual(Projeto.objects.count(), 1)
        self.assertTrue(Projeto.objects.filter(nome="Projeto Válido").exists())
        mock_logger.warning.assert_called()
        self.assertIn(
            "Sincronização concluída: 1 criados, 0 atualizados, 2 ignorados.",
            out.getvalue(),
        )

    @patch("apps.dashboards.management.commands.sync_jira_projects.logger")
    @patch(
        "apps.dashboards.management.commands.sync_jira_projects.Projeto.objects.create"
    )
    @patch(
        "apps.dashboards.management.commands.sync_jira_projects.JiraService.get_projects"
    )
    def test_sync_registra_integrity_error(
        self, mock_get_projects, mock_projeto_create, mock_logger
    ):
        mock_get_projects.return_value = [{"name": "Projeto Alpha"}]
        mock_projeto_create.side_effect = IntegrityError("duplicated")

        out = StringIO()
        call_command("sync_jira_projects", stdout=out)

        mock_logger.error.assert_called()
        self.assertIn(
            "Sincronização concluída: 0 criados, 0 atualizados, 1 ignorados.",
            out.getvalue(),
        )

    def test_clean_str_trims_value(self):
        command = Command()
        self.assertEqual(command._clean_str("  valor  "), "valor")
        self.assertEqual(command._clean_str(None), "")
