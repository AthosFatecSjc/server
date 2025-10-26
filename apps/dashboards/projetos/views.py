from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from .services import CustoPorDesenvolvedorService


@require_http_methods(["GET"])
def index(request):
    """View principal do dashboard de saúde do projeto."""
    projeto_id = request.GET.get("projeto_id", 2)

    service = CustoPorDesenvolvedorService()
    dados_custo = service.obter_custo_por_desenvolvedor(projeto_id)
    dados_grafico = service.formatar_para_grafico(dados_custo)

    context_dados = {
        "labels": dados_grafico["labels"],
        "values": dados_grafico["values"],
        "max_value": dados_grafico["max_value"],
        "has_data": len(dados_grafico["labels"]) > 0,
    }

    header_context = {
        "title": "Dashboard de Saúde do Projeto",
        "subtitle": "Análise financeira e operacional do projeto",
        "breadcrumb": "Saúde do Projeto",
    }

    context = {
        "header_context": header_context,
        "dados_grafico": context_dados,
    }

    return render(request, "projeto/index.html", context)
