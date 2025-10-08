from django.shortcuts import render
from .services import JiraService

def dashboard_view(request):
    """View simples para o dashboard"""
    jira_service = JiraService()
    projetos_com_tasks = jira_service.get_all_tasks_data()
    
    total_projetos = len(projetos_com_tasks)
    total_tasks_geral = sum(proj['total_tasks'] for proj in projetos_com_tasks)
    
    context = {
        'projetos_com_tasks': projetos_com_tasks,
        'total_projetos': total_projetos,
        'total_tasks_geral': total_tasks_geral
    }
    
    return render(request, 'dashboards/index.html', context)