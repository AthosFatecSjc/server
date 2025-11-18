from django.shortcuts import render
from django.views.decorators.http import require_http_methods


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
        {
            "nome": "Dashboard de Produtividade da Equipe",
            "url": "equipes/",
            "descricao": "Análise completa de Productividade da Equipe",
            "categoria": "Análise",
        },
    ]
    return render(request, "dashboards/index.html", {"dashboards": dashboards})
