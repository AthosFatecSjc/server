import requests
import json
import logging
from typing import List, Dict, Any
from django.conf import settings
import sentry_sdk

logger = logging.getLogger(__name__)

class JiraService:
    """
    Interage com a API do Jira para buscar projetos e tarefas.

    Esta classe encapsula a lógica de negócio para a comunicação com o Jira,
    incluindo a validação de credenciais, a formatação de requisições e o
    tratamento de erros, com integração ao Sentry para monitorização.
    """

    def __init__(self):
        """
        Inicializa o serviço, valida as credenciais e configura os cabeçalhos.
        """
        self.base_url = settings.JIRA_BASE_URL
        self.user = getattr(settings, 'JIRA_USER', None)
        self.token = getattr(settings, 'JIRA_TOKEN', None)
        
        self.credentials_are_valid = self.user and self.token

        if not self.credentials_are_valid:
            logger.error("Credenciais do JIRA (JIRA_USER ou JIRA_TOKEN) não estão configuradas.")
            sentry_sdk.capture_message("As credenciais do JIRA não foram encontradas.", level="error")

        self.auth = (self.user, self.token)
        self.headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}

    def _enrich_sentry_scope(self, url: str, payload: Dict = None):
        """
        Adiciona contexto extra ao escopo do Sentry para depuração.

        Args:
            url (str): O endpoint da API do Jira que está a ser acedido.
            payload (Dict, optional): O corpo da requisição enviado ao Jira.
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

        Retorna uma lista de projetos em caso de sucesso. Em caso de falha de
        comunicação ou credenciais inválidas, retorna None.

        Returns:
            List[Dict] | None: Uma lista de dicionários, onde cada um representa
            um projeto, ou None se ocorrer um erro.
        """
        if not self.credentials_are_valid:
            return None

        url = f"{self.base_url}/rest/api/3/project"
        self._enrich_sentry_scope(url)

        try:
            # SUGESTÃO 2: Monitoramento de Performance (APM)
            with sentry_sdk.start_span(op="http.client", description="Request Jira Projects"):
                response = requests.get(url, auth=self.auth, headers=self.headers, timeout=15)
            
            response.raise_for_status()
            
            projects = response.json()
            if not projects:
                sentry_sdk.capture_message(
                    "A API do Jira retornou uma lista de projetos vazia.",
                    level="warning"
                )
            return projects or []

        except requests.exceptions.RequestException as e:
            logger.error(f"Erro ao buscar projetos do Jira: {e}")
            sentry_sdk.capture_exception(e)
            return None

    def get_tasks_by_project(self, project_key: str, max_results: int = 100) -> List[Dict]:
        """
        Busca tarefas de um projeto específico, validando a resposta da API.

        Args:
            project_key (str): A chave do projeto no Jira (ex: 'PROJ').
            max_results (int): O número máximo de tarefas a serem retornadas.

        Returns:
            List[Dict]: Uma lista de tarefas (issues) encontradas, ou uma lista
            vazia se ocorrer um erro ou se nenhuma tarefa for encontrada.
        """
        url = f"{self.base_url}/rest/api/3/search/jql"
        jql_query = f"project = {project_key}"
        
        payload = {
            "jql": jql_query,
            "fields": [
                "summary", "assignee", "timetracking", "issuetype", 
                "timeoriginalestimate", "timeestimate", "timespent",
                "status", "created", "updated"
            ],
            "maxResults": max_results
        }

        self._enrich_sentry_scope(url, payload=payload)
        
        try:
            with sentry_sdk.start_span(op="http.client", description=f"Request Jira Tasks for {project_key}"):
                response = requests.post(
                    url,
                    auth=self.auth,
                    headers=self.headers,
                    data=json.dumps(payload),
                    timeout=15
                )
            response.raise_for_status()
            
            data = response.json()

            # SUGESTÃO 1: Monitoramento de Respostas Inesperadas
            if 'issues' not in data:
                sentry_sdk.capture_message(
                    f"A resposta da API do Jira para o projeto {project_key} não continha a chave 'issues'.",
                    level="warning"
                )
                return []

            issues = data.get('issues', [])
            if not issues:
                sentry_sdk.capture_message(
                    f"Nenhuma task encontrada para o projeto '{project_key}'.",
                    level="info"
                )
            return issues

        except requests.exceptions.RequestException as e:
            logger.error(f"Erro ao buscar tasks do projeto {project_key}: {e}")
            sentry_sdk.capture_exception(e)
            return []

    def get_all_tasks_data(self) -> List[Dict] | None:
        """
        Busca todos os projetos e formata os dados das suas tarefas.

        Este método orquestra a busca de projetos e, para cada um, busca as
        suas tarefas, consolidando tudo numa única estrutura de dados para
        ser usada no dashboard.

        Returns:
            List[Dict] | None: Uma lista contendo os dados formatados de cada
            projeto e as suas tarefas, ou None se a busca inicial de projetos falhar.
        """
        projetos = self.get_projects()
        
        if projetos is None:
            return None
            
        projetos_com_tasks = []
        for projeto in projetos:
            project_key = projeto['key']
            tasks = self.get_tasks_by_project(project_key, max_results=100)
            
            tasks_formatadas = []
            for task in tasks:
                fields = task.get('fields', {})
                
                tasks_formatadas.append({
                    'key': task.get('key'),
                    'summary': fields.get('summary', 'Sem título'),
                    'issue_type': fields.get('issuetype', {}).get('name', 'Sem tipo'),
                    'assignee': fields.get('assignee', {}).get('displayName', 'Sem responsável') if fields.get('assignee') else 'Sem responsável',
                    'time_spent': fields.get('timetracking', {}).get('timeSpent', '0h'),
                    'time_estimate': fields.get('timetracking', {}).get('timeEstimate', '0h'),
                    'status': fields.get('status', {}).get('name', 'N/A'),
                    'created': fields.get('created', 'N/A')[:10] if fields.get('created') else 'N/A'
                })
            
            projetos_com_tasks.append({
                'key': project_key,
                'name': projeto.get('name', 'Sem nome'),
                'total_tasks': len(tasks),
                'tasks': tasks_formatadas
            })
        
        return projetos_com_tasks