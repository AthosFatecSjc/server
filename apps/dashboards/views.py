from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from .services import JiraService

# Mantido para futura reativação de cache
# from apps.utils.cache import SimpleCache  # NOSONAR


@require_http_methods(["GET"])
def dashboard_view(request):
    """
    Exibe o dashboard de projetos e tarefas do Jira.

    Esta view busca os dados através da JiraService, utilizando um cache para
    melhorar a performance, trata possíveis falhas de comunicação e prepara
    o contexto para a renderização do template. Se a comunicação com o Jira
    falhar, uma mensagem de erro é passada para o frontend.

    Args:
        request: O objeto HttpRequest.

    Returns:
        Uma HttpResponse com a página do dashboard renderizada.
    """
    # Lógica de Cache (vinda da branch 'develop')
    # context = SimpleCache.get()
    # if context:
    #     context['from_cache'] = True
    #     return render(request, 'dashboards/index.html', context)

    # Se não estiver no cache, busca os dados (lógica da sua branch 'ATHOS-113')
    jira_service = JiraService()
    projetos_com_tasks = jira_service.get_all_tasks_data()

    context = {
        "error_message": None,
        "projetos_com_tasks": [],
        "total_projetos": 0,
        "total_tasks_geral": 0,
        "from_cache": False,
    }

    # Tratamento de erro (lógica da sua branch 'ATHOS-113')
    if projetos_com_tasks is None:
        context["error_message"] = (
            "Falha na comunicação com a API do Jira. Tente atualizar a página. Caso o erro persista, entre em contato com o time de suporte."
        )
    else:
        # Montagem do contexto de sucesso (lógica de ambas as branches)
        context["projetos_com_tasks"] = projetos_com_tasks
        context["total_projetos"] = len(projetos_com_tasks)
        context["total_tasks_geral"] = sum(
            proj["total_tasks"] for proj in projetos_com_tasks
        )

        # Armazena o resultado de sucesso no cache para futuras requisições
        # SimpleCache.set(context)

    return render(request, "dashboards/index.html", context)
