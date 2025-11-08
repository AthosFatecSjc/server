import json
import logging
import time
from http import HTTPStatus
from typing import Dict, List

import requests
import sentry_sdk
from django.conf import settings

logger = logging.getLogger(__name__)
SENTRY_HTTP_OP = "http.client"


class JiraService:
    """
    Interage com a API do Jira para buscar projetos e tarefas.
    """

    def __init__(self):
        """
        Inicializa o serviço, valida as credenciais e configura os cabeçalhos.
        """
        self.base_url = settings.JIRA_BASE_URL
        self.user = getattr(settings, "JIRA_USER", None)
        self.token = getattr(settings, "JIRA_TOKEN", None)

        self.credentials_are_valid = self.user and self.token

        if not self.credentials_are_valid:
            logger.error(
                "Credenciais do JIRA (JIRA_USER ou JIRA_TOKEN) não estão configuradas."
            )
            sentry_sdk.capture_message(
                "As credenciais do JIRA não foram encontradas.", level="error"
            )

        self.auth = (self.user, self.token)
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _enrich_sentry_scope(self, url: str, payload: Dict = None):
        """
        Adiciona contexto extra ao escopo do Sentry para depuração.
        """
        with sentry_sdk.configure_scope() as scope:
            scope.set_tag("integration", "jira")
            scope.set_tag("integration.url", self.base_url)
            scope.set_extra("jira_api_endpoint", url)
            if payload:
                scope.set_extra("jira_request_payload", payload)

    def get_projects(self) -> List[Dict] | None:
        """
        Busca todos os projetos do Jira, monitorizando a performance.
        """
        if not self.credentials_are_valid:
            return None

        url = f"{self.base_url}/rest/api/3/project"
        self._enrich_sentry_scope(url)

        try:
            with sentry_sdk.start_span(
                op=SENTRY_HTTP_OP, description="Request Jira Projects"
            ):
                response = requests.get(
                    url, auth=self.auth, headers=self.headers, timeout=15
                )

            response.raise_for_status()

            projects = response.json()
            if not projects:
                sentry_sdk.capture_message(
                    "A API do Jira retornou uma lista de projetos vazia.",
                    level="warning",
                )
            return projects or []

        except requests.exceptions.RequestException as e:
            logger.error("Erro ao buscar projetos do Jira: %s", e)
            sentry_sdk.capture_exception(e)
            return None

    def get_tasks_by_project(
        self, project_key: str, max_results_per_page: int = 100
    ) -> List[Dict]:
        """
        Mantido para retrocompatibilidade: delega para `get_issues`.
        """
        return self.get_issues(project_key, max_results_per_page)

    def get_issues(
        self, project_key: str, max_results_per_page: int = 100
    ) -> List[Dict]:
        """
        Busca tarefas de um projeto específico, validando a resposta da API.
        """
        url = f"{self.base_url}/rest/api/3/search/jql"
        jql_query = f"project = {project_key}"

        all_issues = []

        next_page_token = None

        while True:

            payload = {
                "jql": jql_query,
                "fields": [
                    "summary",
                    "assignee",
                    "timetracking",
                    "issuetype",
                    "timeoriginalestimate",
                    "timeestimate",
                    "timespent",
                    "status",
                    "created",
                    "updated",
                ],
            }

            if max_results_per_page is not None:
                payload["maxResults"] = max_results_per_page

            if next_page_token is not None:
                payload["nextPageToken"] = next_page_token

            self._enrich_sentry_scope(url, payload=payload)

            try:
                with sentry_sdk.start_span(
                    op=SENTRY_HTTP_OP,
                    description=f"Request Jira Tasks for {project_key}",
                ):
                    response = requests.post(
                        url,
                        auth=self.auth,
                        headers=self.headers,
                        data=json.dumps(payload),
                        timeout=15,
                    )

                if response.status_code == HTTPStatus.TOO_MANY_REQUESTS:
                    retry_after = int(response.headers.get("Retry-After", 5))
                    time.sleep(retry_after)
                    continue

                response.raise_for_status()

                data = response.json()

                if "issues" not in data:
                    sentry_sdk.capture_message(
                        f"A resposta da API do Jira para o projeto {project_key} não continha a chave 'issues'.",
                        level="warning",
                    )
                    break

                issues = data.get("issues", [])
                if not issues:
                    sentry_sdk.capture_message(
                        f"Nenhuma task encontrada para o projeto '{project_key}'.",
                        level="info",
                    )
                    break

                all_issues.extend(issues)

                # Paging info
                is_last = data.get("isLast", True)
                if is_last:
                    break

                next_page_token = data.get("nextPageToken", None)

            except requests.exceptions.RequestException as e:
                logger.error("Erro ao buscar tasks do projeto %s: %s", project_key, e)
                sentry_sdk.capture_exception(e)
                return []

        return all_issues

    def get_all_tasks_data(self) -> List[Dict] | None:
        """
        Busca todos os projetos e formata os dados das suas tarefas.
        """
        projetos = self.get_projects()

        if projetos is None:
            return None

        projetos_com_tasks = []
        for projeto in projetos:
            project_key = projeto["key"]
            tasks = self.get_tasks_by_project(project_key, 100)

            tasks_formatadas = []
            for task in tasks:
                fields = task.get("fields", {})

                tasks_formatadas.append(
                    {
                        "key": task.get("key"),
                        "summary": fields.get("summary", "Sem título"),
                        "issue_type": fields.get("issuetype", {}).get(
                            "name", "Sem tipo"
                        ),
                        "assignee": (
                            fields.get("assignee", {}).get(
                                "displayName", "Sem responsável"
                            )
                            if fields.get("assignee")
                            else "Sem responsável"
                        ),
                        "time_spent": fields.get("timetracking", {}).get(
                            "timeSpent", "0h"
                        ),
                        "time_estimate": fields.get("timetracking", {}).get(
                            "timeEstimate", "0h"
                        ),
                        "status": fields.get("status", {}).get("name", "N/A"),
                        "created": (
                            fields.get("created", "N/A")[:10]
                            if fields.get("created")
                            else "N/A"
                        ),
                    }
                )

            projetos_com_tasks.append(
                {
                    "key": project_key,
                    "name": projeto.get("name", "Sem nome"),
                    "total_tasks": len(tasks),
                    "tasks": tasks_formatadas,
                }
            )

        return projetos_com_tasks

    def get_tipos_issue(self, projeto_id: int) -> List[Dict] | None:
        """
        Busca todos os projetos do Jira, monitorizando a performance.
        """

        if not self.credentials_are_valid:
            return None

        url = f"{self.base_url}/rest/api/3/issuetype/project?projectId={projeto_id}"
        self._enrich_sentry_scope(url)

        try:
            with sentry_sdk.start_span(
                op=SENTRY_HTTP_OP, description="Request Jira IssueTypes for Project"
            ):
                response = requests.get(
                    url, auth=self.auth, headers=self.headers, timeout=15
                )

            response.raise_for_status()

            tipos_issue = response.json()
            if not tipos_issue:
                sentry_sdk.capture_message(
                    "A API do Jira retornou uma lista de tipos de issue vazia.",
                    level="warning",
                )
            return tipos_issue or []

        except requests.exceptions.RequestException as e:
            logger.error(
                "Erro ao buscar tipos de issue para o projeto %s do Jira: %s",
                projeto_id,
                e,
            )
            sentry_sdk.capture_exception(e)
            return None
