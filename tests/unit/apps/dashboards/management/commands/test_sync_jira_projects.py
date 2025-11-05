from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.db import IntegrityError
from django.test import TestCase

from apps.dashboards.management.commands.sync_jira_projects import DEFAULT_ORCAMENTO
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
        self.assertIn("Sincronização concluída: 2 criados, 0 atualizados.", output)

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
        self.assertIn("Sincronização concluída: 0 criados, 1 atualizados.", output)

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
            "Sincronização concluída: 1 criados, 0 atualizados.", out.getvalue()
        )

    @patch("apps.dashboards.management.commands.sync_jira_projects.logger")
    @patch(
        "apps.dashboards.management.commands.sync_jira_projects.Projeto.objects.update_or_create"
    )
    @patch(
        "apps.dashboards.management.commands.sync_jira_projects.JiraService.get_projects"
    )
    def test_sync_registra_integrity_error(
        self, mock_get_projects, mock_update_or_create, mock_logger
    ):
        mock_get_projects.return_value = [{"name": "Projeto Alpha"}]
        mock_update_or_create.side_effect = IntegrityError("duplicated")

        out = StringIO()
        call_command("sync_jira_projects", stdout=out)

        mock_logger.error.assert_called()
        self.assertIn(
            "Sincronização concluída: 0 criados, 0 atualizados.", out.getvalue()
        )
