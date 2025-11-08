from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase

from apps.dashboards.management.commands.test_jira_sentry import Command


class TestJiraSentryCommandTests(SimpleTestCase):
    def test_handle_sem_opcoes_dispara_erro(self):
        with self.assertRaises(CommandError):
            call_command("test_jira_sentry")

    @patch(
        "apps.dashboards.management.commands.test_jira_sentry.Command.simulate_empty_response"
    )
    @patch(
        "apps.dashboards.management.commands.test_jira_sentry.Command.simulate_auth_error"
    )
    @patch(
        "apps.dashboards.management.commands.test_jira_sentry.Command.simulate_connection_error"
    )
    def test_handle_dispara_cenarios_solicitados(
        self,
        mock_simulate_connection,
        mock_simulate_auth,
        mock_simulate_empty,
    ):
        out = StringIO()
        call_command(
            "test_jira_sentry",
            fail_connection=True,
            fail_auth=True,
            empty_response=True,
            stdout=out,
        )

        mock_simulate_connection.assert_called_once()
        mock_simulate_auth.assert_called_once()
        mock_simulate_empty.assert_called_once()
        self.assertIn("Teste concluído.", out.getvalue())

    @patch("apps.dashboards.management.commands.test_jira_sentry.sentry_sdk.flush")
    @patch("apps.dashboards.management.commands.test_jira_sentry.JiraService")
    def test_simulate_connection_error_chama_jira_e_sentry(
        self, mock_jira_service, mock_flush
    ):
        command = Command()
        command.stdout = StringIO()

        command.simulate_connection_error()

        mock_jira_service.assert_called_once()
        mock_jira_service.return_value.get_projects.assert_called_once()
        mock_flush.assert_called_once()

    @patch("apps.dashboards.management.commands.test_jira_sentry.sentry_sdk.flush")
    @patch("apps.dashboards.management.commands.test_jira_sentry.JiraService")
    def test_simulate_auth_error_chama_jira_e_sentry(
        self, mock_jira_service, mock_flush
    ):
        command = Command()
        command.stdout = StringIO()

        command.simulate_auth_error()

        mock_jira_service.assert_called_once()
        mock_jira_service.return_value.get_projects.assert_called_once()
        mock_flush.assert_called_once()

    @patch("apps.dashboards.management.commands.test_jira_sentry.sentry_sdk.flush")
    @patch("apps.dashboards.management.commands.test_jira_sentry.JiraService")
    def test_simulate_empty_response_chama_jira_e_sentry(
        self, mock_jira_service, mock_flush
    ):
        command = Command()
        command.stdout = StringIO()

        command.simulate_empty_response()

        mock_jira_service.assert_called_once()
        mock_jira_service.return_value.get_projects.assert_called_once()
        mock_flush.assert_called_once()
