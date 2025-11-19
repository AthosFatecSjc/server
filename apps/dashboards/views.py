from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from apps.usuarios.decorators import perfil_gerente_required


@perfil_gerente_required
@require_http_methods(["GET"])
def index(request):
    dashboards = [
        {
            "nome": "Gerenciamento de Desenvolvedores",
            "url": "desenvolvedores/",
            "descricao": "Configure valores por hora e visualize estatísticas da equipe",
            "categoria": "Gestão",
        },
        {
            "nome": "Dashboard de Saúde do Projeto",
            "url": "projeto/",
            "descricao": "Análise completa de custos, issues e bugs do projeto",
            "categoria": "Análise",
        },
    ]
    return render(request, "dashboards/index.html", {"dashboards": dashboards})
