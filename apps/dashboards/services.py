import requests
import json
import logging
from typing import List, Dict, Any
from django.conf import settings
import sentry_sdk

logger = logging.getLogger(__name__)

class JiraService:
    """
    Camada de serviço para interagir com a API do Jira, com monitorização
    integrada ao Sentry para falhas de comunicação.
    """
    def __init__(self):
        """Inicializa o serviço com as credenciais e URLs do Jira."""
        self.base_url = settings.JIRA_BASE_URL
        self.auth = (settings.JIRA_USER, settings.JIRA_TOKEN)
        self.headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }

    def _enrich_sentry_scope(self, url: str, payload: Dict = None):
        """
        Adiciona contexto extra (tags e dados) ao escopo do Sentry para
        facilitar a depuração de erros relacionados ao Jira.
        """
        with sentry_sdk.configure_scope() as scope:
            scope.set_tag("integration", "jira")
            scope.set_tag("integration.url", self.base_url)
            scope.set_extra("jira_api_endpoint", url)
            if payload:
                scope.set_extra("jira_request_payload", payload)

    def get_projects(self) -> List[Dict]:
        """
        Busca todos os projetos do Jira.

        Captura falhas de conexão, erros HTTP e respostas vazias, reportando-os
        ao Sentry.
        """
        url = f"{self.base_url}/rest/api/3/project"
        self._enrich_sentry_scope(url)

        try:
            response = requests.get(
                url,
                auth=self.auth,
                headers=self.headers,
                timeout=15  # Timeout reduzido para uma resposta mais rápida
            )
            response.raise_for_status()  # Levanta exceção para erros 4xx/5xx

            projects = response.json()

            if not projects:
                sentry_sdk.capture_message(
                    "A API do Jira retornou uma lista de projetos vazia.",
                    level="warning"
                )
                return []

            return projects

        except requests.exceptions.RequestException as e:
            logger.error(f"Erro ao buscar projetos do Jira: {e}")
            sentry_sdk.capture_exception(e)
            return []

    def get_tasks_by_project(self, project_key: str, max_results: int = 100) -> List[Dict]:
        """
        Busca tasks de um projeto específico usando o método POST.
        Captura falhas de conexão, erros HTTP e respostas vazias, reportando-os
        ao Sentry.
        """
        # ALTERAÇÃO 1: O URL foi atualizado para o endpoint específico de JQL.
        url = f"{self.base_url}/rest/api/3/search/jql"
        
        # A consulta JQL agora é mais simples, sem aspas extras que podem causar problemas.
        jql_query = f"project = {project_key}"
        
        # ALTERAÇÃO 2: O payload é um dicionário que será enviado no corpo da requisição.
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
                "updated"
            ],
            "maxResults": max_results
        }

        self._enrich_sentry_scope(url, payload=payload)
        
        try:
            # ALTERAÇÃO 3: A requisição agora usa requests.post().
            response = requests.post(
                url,
                auth=self.auth,
                headers=self.headers,
                # ALTERAÇÃO 4: Os dados são enviados como JSON no corpo da requisição.
                data=json.dumps(payload),
                timeout=15
            )
            response.raise_for_status()
            
            issues = response.json().get('issues', [])

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


    def get_all_tasks_data(self) -> List[Dict]:
        """Busca todos os projetos e suas tasks para o dashboard."""
        projetos = self.get_projects()
        
        # Se a busca de projetos falhar, retorna uma lista vazia para evitar mais erros.
        if not projetos:
            return []
            
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