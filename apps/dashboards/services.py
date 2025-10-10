import requests
import json
import logging
from typing import List, Dict, Any
from django.conf import settings
import sentry_sdk

logger = logging.getLogger(__name__)

class JiraService:
    def __init__(self):
        self.base_url = settings.JIRA_BASE_URL
        self.auth = (settings.JIRA_USER, settings.JIRA_TOKEN)
        self.headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
    
    def get_projects(self) -> List[Dict]:
        """Busca todos os projetos do Jira"""
        url = f"{self.base_url}/rest/api/3/project"
        
        try:
            response = requests.get(
                url, 
                auth=self.auth, 
                headers=self.headers,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro ao buscar projetos: {e}")
            sentry_sdk.capture_exception(e)
            return []
    
    def get_tasks_by_project(self, project_key: str, max_results: int = 100) -> List[Dict]:
        """Busca tasks de um projeto específico"""
        url = f"{self.base_url}/rest/api/3/search/jql"
        
        jql_query = f"project = {project_key}"
        
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
        
        try:
            response = requests.post(
                url,
                auth=self.auth,
                headers=self.headers,
                data=json.dumps(payload),
                timeout=30
            )
            response.raise_for_status()
            return response.json().get('issues', [])
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro ao buscar tasks do projeto {project_key}: {e}")
            sentry_sdk.capture_exception(e)
            return []
    
    def get_all_tasks_data(self) -> List[Dict]:
        """Busca todos os projetos e suas tasks para o dashboard"""
        projetos = self.get_projects()
        
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