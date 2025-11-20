from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from apps.usuarios.decorators import perfil_lider_required
from apps.usuarios.models import PerfilAcessoChoices

ACESSO_PRIORITY = [
    PerfilAcessoChoices.GERENTE,
    PerfilAcessoChoices.LIDER,
    PerfilAcessoChoices.MEMBRO,
]

DASHBOARDS_DEFINITIONS = [
    {
        "nome": "Gerenciamento de Desenvolvedores",
        "url_name": "desenvolvedores_index",
        "descricao": "Configure valores por hora e visualize estatísticas da equipe",
        "categoria": "Gestão",
        "categoria_badge": "Gestão",
        "funcionalidades": "Tabela de desenvolvedores, valores por hora e estatísticas de custos",
        "perfis": {PerfilAcessoChoices.GERENTE},
        "icon": "icon-users",
        "icon_container_class": "",
    },
    {
        "nome": "Dashboard de Saúde do Projeto",
        "url_name": "projetos_index",
        "descricao": "Análise completa de custos, issues e bugs do projeto",
        "categoria": "Análise",
        "categoria_badge": "Análise",
        "funcionalidades": "Três dashboards integrados: custos, issues abertas e bugs",
        "perfis": {PerfilAcessoChoices.GERENTE, PerfilAcessoChoices.LIDER},
        "icon": "icon-activity",
        "icon_container_class": "icon-container--orange",
    },
    {
        "nome": "Dashboard de Produtividade da Equipe",
        "url_name": "produtividade_index",
        "descricao": "Acompanhe horas por atividade, módulo e desenvolvedor",
        "categoria": "Produtividade",
        "categoria_badge": "Produtividade",
        "funcionalidades": "Análise de horas por módulo/epic e desenvolvedor",
        "perfis": {PerfilAcessoChoices.GERENTE, PerfilAcessoChoices.LIDER},
        "icon": "icon-trending-up",
        "icon_container_class": "icon-container--green",
    },
]


def _format_acesso(perfis: set[str]) -> str:
    ordered = [perfil for perfil in ACESSO_PRIORITY if perfil in perfis]
    labels = [PerfilAcessoChoices(perfil).label for perfil in ordered]
    return ", ".join(labels)


def _dashboards_visiveis(perfil_usuario: str) -> list[dict]:
    """Filtra dashboards conforme o perfil do usuário."""
    visiveis: list[dict] = []

    for dashboard in DASHBOARDS_DEFINITIONS:
        if perfil_usuario not in dashboard["perfis"]:
            continue

        visiveis.append(
            {
                **dashboard,
                "acesso_label": _format_acesso(dashboard["perfis"]),
            }
        )

    return visiveis


@perfil_lider_required
@require_http_methods(["GET"])
def index(request):
    perfil_usuario = getattr(request.user, "perfil_acesso", None)
    dashboards = _dashboards_visiveis(perfil_usuario)

    return render(
        request,
        "dashboards/index.html",
        {
            "dashboards": dashboards,
        },
    )
