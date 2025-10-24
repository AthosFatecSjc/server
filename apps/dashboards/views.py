from django.db.models import Avg, Count, Max, Min, Sum
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from olap_models.models import DimProjeto, FatoRegistroHoras

from .services import JiraService

# A linha abaixo pode ser necessária dependendo de onde o SimpleCache foi implementado.
# from apps.utils.cache import SimpleCache


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

    projetos_dimensao = []
    for projeto in DimProjeto.objects.using("olap").all():
        estatisticas = (
            FatoRegistroHoras.objects.using("olap")
            .filter(projeto=projeto)
            .aggregate(
                total_horas=Sum("horas_gastas"),
                total_custo=Sum("custo_total"),
                total_registros=Count("id"),
                media_horas=Avg("horas_gastas"),
                primeiro_registro=Min("data__data_completa"),
                ultimo_registro=Max("data__data_completa"),
            )
        )

        funcionarios_count = (
            FatoRegistroHoras.objects.using("olap")
            .filter(projeto=projeto)
            .values("funcionario")
            .distinct()
            .count()
        )

        custo_por_dev = (
            FatoRegistroHoras.objects.using("olap")
            .filter(projeto=projeto)
            .values(
                "funcionario__id",
                "funcionario__nome_funcionario",
                "funcionario__valor_hora",
            )
            .annotate(total_horas_dev=Sum("horas_gastas"), custo_dev=Sum("custo_total"))
            .order_by("-custo_dev")
        )

        custo_por_dev_list = [
            {
                "funcionario_id": dev["funcionario__id"],
                "funcionario_nome": dev["funcionario__nome_funcionario"],
                "valor_hora": float(dev["funcionario__valor_hora"] or 0),
                "total_horas": float(dev["total_horas_dev"] or 0),
                "custo_total": float(dev["custo_dev"] or 0),
            }
            for dev in custo_por_dev
        ]

        custo_realizado = float(estatisticas["total_custo"] or 0)

        projetos_dimensao.append(
            {
                "id": projeto.id,
                "nome_projeto": projeto.nome_projeto,
                "data_criacao": projeto.data_criacao,
                "total_horas": float(estatisticas["total_horas"] or 0),
                "total_custo": float(estatisticas["total_custo"] or 0),
                "custo_realizado": custo_realizado,
                "custo_por_dev": custo_por_dev_list,
                "total_registros": estatisticas["total_registros"],
                "media_horas": float(estatisticas["media_horas"] or 0),
                "primeiro_registro": estatisticas["primeiro_registro"],
                "ultimo_registro": estatisticas["ultimo_registro"],
                "funcionarios_count": funcionarios_count,
            }
        )

    context = {
        "error_message": None,
        "projetos_com_tasks": [],
        "projetos_dimensao": list(projetos_dimensao),
        "total_projetos": 0,
        "total_tasks_geral": 0,
        "from_cache": False,
    }

    if projetos_com_tasks is None:
        context["error_message"] = (
            "Falha na comunicação com a API do Jira. Tente atualizar a página. Caso o erro persista, entre em contato com o time de suporte."
        )
    else:
        context["projetos_com_tasks"] = projetos_com_tasks
        context["total_projetos"] = len(projetos_com_tasks)
        context["total_tasks_geral"] = sum(
            proj["total_tasks"] for proj in projetos_com_tasks
        )

        # Armazena o resultado de sucesso no cache para futuras requisições
        # SimpleCache.set(context)

    return render(request, "dashboards/index.html", context)
