import json
from http import HTTPStatus
from unittest.mock import MagicMock, patch

import requests
from django.test import SimpleTestCase, override_settings

from apps.dashboards.services import JiraService


def _mock_sentry(mock_sentry):
    """Configure sentry mock to behave as context managers."""
    span = MagicMock()
    span.__enter__.return_value = None
    span.__exit__.return_value = None
    mock_sentry.start_span.return_value = span

    scope = MagicMock()
    mock_sentry.configure_scope.return_value.__enter__.return_value = scope
    mock_sentry.configure_scope.return_value.__exit__.return_value = None

    return scope


class JiraServiceTests(SimpleTestCase):
    @override_settings(JIRA_USER=None, JIRA_TOKEN=None)
    @patch("apps.dashboards.services.requests.get")
    @patch("apps.dashboards.services.sentry_sdk")
    def test_get_projects_retorna_none_quando_sem_credenciais(
        self, mock_sentry, mock_get
    ):
        _mock_sentry(mock_sentry)

        service = JiraService()
        result = service.get_projects()

        self.assertIsNone(result)
        mock_get.assert_not_called()
        mock_sentry.capture_message.assert_called_once()

    @override_settings(JIRA_USER="user", JIRA_TOKEN="token")
    @patch("apps.dashboards.services.requests.get")
    @patch("apps.dashboards.services.sentry_sdk")
    def test_get_projects_retorna_lista_e_avisa_quando_vazia(
        self, mock_sentry, mock_get
    ):
        _mock_sentry(mock_sentry)
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.return_value = []
        mock_get.return_value = response

        service = JiraService()
        result = service.get_projects()

        self.assertEqual(result, [])
        mock_get.assert_called_once()
        mock_sentry.capture_message.assert_called_once()

    @override_settings(JIRA_USER="user", JIRA_TOKEN="token")
    @patch("apps.dashboards.services.requests.get")
    @patch("apps.dashboards.services.sentry_sdk")
    def test_get_projects_trata_request_exception(self, mock_sentry, mock_get):
        _mock_sentry(mock_sentry)
        mock_get.side_effect = requests.exceptions.RequestException("boom")

        service = JiraService()
        result = service.get_projects()

        self.assertIsNone(result)
        mock_sentry.capture_exception.assert_called_once()

    @override_settings(JIRA_USER="user", JIRA_TOKEN="token")
    @patch("apps.dashboards.services.requests.post")
    @patch("apps.dashboards.services.sentry_sdk")
    def test_get_tasks_by_project_quando_resposta_sem_issues(
        self, mock_sentry, mock_post
    ):
        _mock_sentry(mock_sentry)
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"total": 1}
        mock_post.return_value = response

        service = JiraService()
        result = service.get_tasks_by_project("ABC")

        self.assertEqual(result, [])
        mock_sentry.capture_message.assert_called_once()

    @override_settings(JIRA_USER="user", JIRA_TOKEN="token")
    @patch("apps.dashboards.services.requests.post")
    @patch("apps.dashboards.services.sentry_sdk")
    def test_get_tasks_by_project_formata_resposta(self, mock_sentry, mock_post):
        _mock_sentry(mock_sentry)
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "issues": [
                {
                    "key": "ISSUE-1",
                    "fields": {
                        "summary": "Task 1",
                        "issuetype": {"name": "Bug"},
                        "assignee": {"displayName": "Alice"},
                        "timetracking": {"timeSpent": "1h", "timeEstimate": "2h"},
                        "status": {"name": "To Do"},
                        "created": "2024-01-01T12:00:00.000Z",
                    },
                },
                {
                    "key": "ISSUE-2",
                    "fields": {
                        "summary": "Task 2",
                        "issuetype": {"name": "Task"},
                        "assignee": None,
                        "timetracking": {},
                        "status": {},
                        "created": None,
                    },
                },
            ]
        }
        mock_post.return_value = response

        service = JiraService()
        result = service.get_tasks_by_project("ABC")

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["fields"]["assignee"]["displayName"], "Alice")
        self.assertIsNone(result[1]["fields"]["assignee"])
        mock_sentry.capture_message.assert_not_called()

    @override_settings(JIRA_USER="user", JIRA_TOKEN="token")
    @patch("apps.dashboards.services.requests.post")
    @patch("apps.dashboards.services.sentry_sdk")
    def test_get_tasks_by_project_informa_quando_sem_tasks(
        self, mock_sentry, mock_post
    ):
        _mock_sentry(mock_sentry)
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"issues": []}
        mock_post.return_value = response

        service = JiraService()
        result = service.get_tasks_by_project("ABC")

        self.assertEqual(result, [])
        mock_sentry.capture_message.assert_called_once()

    @override_settings(JIRA_USER="user", JIRA_TOKEN="token")
    @patch("apps.dashboards.services.requests.post")
    @patch("apps.dashboards.services.sentry_sdk")
    def test_get_tasks_by_project_trata_excecao(self, mock_sentry, mock_post):
        _mock_sentry(mock_sentry)
        mock_post.side_effect = requests.exceptions.RequestException("danger")

        service = JiraService()
        result = service.get_tasks_by_project("ABC")

        self.assertEqual(result, [])
        mock_sentry.capture_exception.assert_called_once()

    @override_settings(JIRA_USER="user", JIRA_TOKEN="token")
    @patch("apps.dashboards.services.time.sleep")
    @patch("apps.dashboards.services.requests.post")
    @patch("apps.dashboards.services.sentry_sdk")
    def test_get_tasks_by_project_respeita_rate_limit_e_paginacao(
        self, mock_sentry, mock_post, mock_sleep
    ):
        _mock_sentry(mock_sentry)

        rate_limited = MagicMock()
        rate_limited.status_code = HTTPStatus.TOO_MANY_REQUESTS
        rate_limited.headers = {"Retry-After": "7"}

        first_page = MagicMock()
        first_page.status_code = HTTPStatus.OK
        first_page.raise_for_status.return_value = None
        first_page.json.return_value = {
            "issues": [{"key": "ISS-1", "fields": {}}],
            "isLast": False,
            "nextPageToken": "token-1",
        }

        second_page = MagicMock()
        second_page.status_code = HTTPStatus.OK
        second_page.raise_for_status.return_value = None
        second_page.json.return_value = {
            "issues": [{"key": "ISS-2", "fields": {}}],
            "isLast": True,
        }

        mock_post.side_effect = [rate_limited, first_page, second_page]

        service = JiraService()
        result = service.get_tasks_by_project("ABC", 1)

        self.assertEqual(len(result), 2)
        mock_sleep.assert_called_once_with(7)
        self.assertEqual(mock_post.call_count, 3)

    @override_settings(JIRA_USER="user", JIRA_TOKEN="token")
    @patch("apps.dashboards.services.time.sleep")
    @patch("apps.dashboards.services.requests.post")
    @patch("apps.dashboards.services.sentry_sdk")
    def test_get_issues_aplica_next_page_token_apos_primeira_pagina(
        self, mock_sentry, mock_post, mock_sleep
    ):
        _mock_sentry(mock_sentry)

        class FakeResponse:
            def __init__(self, status_code, data=None, headers=None):
                self.status_code = status_code
                self._data = data or {}
                self.headers = headers or {}

            def raise_for_status(self):
                if self.status_code >= 400:
                    raise requests.exceptions.HTTPError("error")

            def json(self):
                return self._data

        first_page = FakeResponse(
            HTTPStatus.OK,
            {
                "issues": [{"key": "ISS-10", "fields": {}}],
                "isLast": False,
                "nextPageToken": "next-token",
            },
        )
        second_page = FakeResponse(
            HTTPStatus.OK,
            {"issues": [{"key": "ISS-20", "fields": {}}], "isLast": True},
        )

        mock_post.side_effect = [first_page, second_page]

        service = JiraService()
        issues = service.get_issues("DEF", 1)

        self.assertEqual(len(issues), 2)
        self.assertEqual(mock_post.call_count, 2)
        # Quando a segunda chamada ocorre, o nextPageToken precisa estar presente no payload.
        payload_segunda_chamada = json.loads(mock_post.call_args_list[1].kwargs["data"])
        self.assertEqual(payload_segunda_chamada.get("nextPageToken"), "next-token")
        mock_sleep.assert_not_called()

    @override_settings(JIRA_USER="user", JIRA_TOKEN="token")
    @patch("apps.dashboards.services.JiraService.get_projects", return_value=None)
    def test_get_all_tasks_data_retorna_none_quando_sem_projetos(
        self, mock_get_projects
    ):
        service = JiraService()

        result = service.get_all_tasks_data()

        self.assertIsNone(result)
        mock_get_projects.assert_called_once()

    @override_settings(JIRA_USER="user", JIRA_TOKEN="token")
    @patch("apps.dashboards.services.JiraService.get_tasks_by_project")
    @patch("apps.dashboards.services.JiraService.get_projects")
    def test_get_all_tasks_data_compila_dados(self, mock_get_projects, mock_get_tasks):
        mock_get_projects.return_value = [
            {"key": "ABC", "name": "Projeto ABC"},
            {"key": "XYZ", "name": "Projeto Sem Tasks"},
        ]
        mock_get_tasks.side_effect = [
            [
                {
                    "key": "ISSUE-1",
                    "fields": {
                        "summary": "Task 1",
                        "assignee": {"displayName": "Alice"},
                        "issuetype": {"name": "Bug"},
                        "timetracking": {"timeSpent": "1h", "timeEstimate": "2h"},
                        "status": {"name": "Done"},
                        "created": "2024-01-01T00:00:00.000Z",
                    },
                }
            ],
            [],
        ]

        service = JiraService()
        result = service.get_all_tasks_data()

        self.assertEqual(len(result), 2)
        projeto = result[0]
        self.assertEqual(projeto["key"], "ABC")
        self.assertEqual(projeto["total_tasks"], 1)
        self.assertEqual(projeto["tasks"][0]["assignee"], "Alice")
        self.assertEqual(result[1]["tasks"], [])

    @override_settings(JIRA_USER=None, JIRA_TOKEN=None)
    @patch("apps.dashboards.services.requests.get")
    def test_get_tipos_issue_sem_credenciais_retorna_none(self, mock_get):
        service = JiraService()
        result = service.get_tipos_issue(1)
        self.assertIsNone(result)
        mock_get.assert_not_called()

    @override_settings(JIRA_USER="user", JIRA_TOKEN="token")
    @patch("apps.dashboards.services.requests.get")
    @patch("apps.dashboards.services.sentry_sdk")
    def test_get_tipos_issue_retorna_lista_e_avisa_quando_vazia(
        self, mock_sentry, mock_get
    ):
        _mock_sentry(mock_sentry)
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.return_value = []
        mock_get.return_value = response

        service = JiraService()
        result = service.get_tipos_issue(10)

        self.assertEqual(result, [])
        mock_get.assert_called_once()
        mock_sentry.capture_message.assert_called_once()

    @override_settings(JIRA_USER="user", JIRA_TOKEN="token")
    @patch("apps.dashboards.services.requests.get")
    @patch("apps.dashboards.services.sentry_sdk")
    def test_get_tipos_issue_trata_excecao(self, mock_sentry, mock_get):
        _mock_sentry(mock_sentry)
        mock_get.side_effect = requests.exceptions.RequestException("err")

        service = JiraService()
        result = service.get_tipos_issue(5)

        self.assertIsNone(result)
        mock_sentry.capture_exception.assert_called_once()
