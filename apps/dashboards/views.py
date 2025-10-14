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
        context = SimpleCache.get_info()
    else:
        jira_service = JiraService()
        context = jira_service.get_dashboard_context(include_timestamp=False)
        context['from_cache'] = False

    return render(request, 'dashboards/index.html', context)
