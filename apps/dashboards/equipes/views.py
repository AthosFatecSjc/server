import json

from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from apps.usuarios.decorators import perfil_lider_required

from .services import DashboardEquipesService


@require_http_methods(["GET"])
@perfil_lider_required
def index(request):
    """View principal do dashboard de equipes"""
    return dashboard_equipes(request)


@require_http_methods(["GET"])
@perfil_lider_required
def dashboard_equipes(request):
    """View do dashboard de equipes - agora muito mais limpa"""

    projeto_id, data_inicio, data_fim, desenvolvedores_ids = (
        DashboardEquipesService.processar_filtros(request)
    )
    # Sem filtro manual de devs, mantemos todos selecionados (None).
    desenvolvedores_ids = None

    registros_horas, data_inicio_dt, data_fim_dt = (
        DashboardEquipesService.aplicar_filtros_horas(
            projeto_id, data_inicio, data_fim, desenvolvedores_ids
        )
    )

    dados_grafico = DashboardEquipesService.gerar_dados_grafico_horas(registros_horas)

    desenvolvedores_dropdown = DashboardEquipesService.get_desenvolvedores_dropdown(
        projeto_id,
        data_inicio_dt,
        data_fim_dt,
        desenvolvedores_ids,
    )
    devs_selected_count = DashboardEquipesService.contar_desenvolvedores_selecionados(
        desenvolvedores_dropdown
    )
    projetos = DashboardEquipesService.get_projetos()
    header_context = DashboardEquipesService.get_header_context()

    context = {
        "header_context": header_context,
        "daily_data": dados_grafico,
        "module_data": [],
        "devs": desenvolvedores_dropdown,
        "devs_selected_count": devs_selected_count,
        "projetos": projetos,
        "data_inicio_default": data_inicio_dt.strftime("%Y-%m-%d"),
        "data_fim_default": data_fim_dt.strftime("%Y-%m-%d"),
    }

    if request.headers.get("HX-Request"):
        return render(request, "equipes/partials/_dashboard_content.html", context)

    return render(request, "equipes/index.html", context)
