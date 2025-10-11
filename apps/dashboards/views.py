"""Views do dashboard"""

from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from apps.utils.simple_cache import SimpleCache

from .services import JiraService


@require_http_methods(["GET"])
def dashboard_view(request):
    """View para exibição do dashboard JIRA"""

    context = SimpleCache.get()

    if context:

        context['from_cache'] = True
        cache_info = SimpleCache.get_info()
        context['tempo_restante'] = cache_info['tempo_restante']
    else:
        jira_service = JiraService()
        projetos_com_tasks = jira_service.get_all_tasks_data()

        total_projetos = len(projetos_com_tasks)
        total_tasks_geral = sum(proj['total_tasks']
                                for proj in projetos_com_tasks)

        context = {
            'projetos_com_tasks': projetos_com_tasks,
            'total_projetos': total_projetos,
            'total_tasks_geral': total_tasks_geral,
            'from_cache': False
        }

    return render(request, 'dashboards/index.html', context)
