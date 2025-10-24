from django.db.models import Avg, Count, Max, Min, Sum
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from olap_models.models import DimProjeto, FatoRegistroHoras


@require_http_methods(["GET"])
def index(request):
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
        "header_context": header_context,
        "projetos_dimensao": list(projetos_dimensao),
    }

    return render(request, "projeto/index.html", context)
