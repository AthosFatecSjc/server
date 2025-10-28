from django.db.models import Avg, Count, Max, Min, Sum
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from olap_models.models import DimProjeto, FatoRegistroHoras

from .services import CustoPorDesenvolvedorService


@require_http_methods(["GET"])
def index(request):
    """View principal do dashboard de saúde do projeto."""
    projeto_id = request.GET.get("projeto_id", 2)

    header_context = {
        "title": "Dashboard de Saúde do Projeto",
        "subtitle": "Análise financeira e operacional do projeto",
        "breadcrumb": "Saúde do Projeto",
    }

    projetos_dimensao = []
    for projeto in DimProjeto.objects.using("olap").all():
        estatisticas = (
            FatoRegistroHoras.objects.using("olap")
            .filter(projeto=projeto)
            .aggregate(
                total_horas=Sum("horas_trabalhadas"),
                total_custo=Sum("custo"),
                total_registros=Count("id"),
                media_horas=Avg("horas_trabalhadas"),
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
                "funcionario__nome",
                "funcionario__valor_hora",
            )
            .annotate(total_horas_dev=Sum("horas_trabalhadas"), custo_dev=Sum("custo"))
            .order_by("-custo_dev")
        )

        custo_por_dev_list = [
            {
                "funcionario_id": dev["funcionario__id"],
                "funcionario_nome": dev["funcionario__nome"],
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
                "nome_projeto": projeto.nome,
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

    service = CustoPorDesenvolvedorService()
    dados_custo = service.obter_custo_por_desenvolvedor(projeto_id)
    dados_grafico = service.formatar_para_grafico(dados_custo)

    context_dados = {
        "labels": dados_grafico["labels"],
        "values": dados_grafico["values"],
        "max_value": dados_grafico["max_value"],
        "has_data": len(dados_grafico["labels"]) > 0,
    }

    context = {
        "header_context": header_context,
        "projetos_dimensao": list(projetos_dimensao),
        "dados_grafico": context_dados,
    }

    return render(request, "projeto/index.html", context)
