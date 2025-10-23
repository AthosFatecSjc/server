from django.shortcuts import render
from django.views.decorators.http import require_http_methods


@require_http_methods(["GET"])
def index(request):
    header_context = {
        "title": "Dashboard de Saúde do Projeto",
        "subtitle": "Análise financeira e operacional do projeto",
        "breadcrumb": "Saúde do Projeto",
    }
    return render(request, "projeto/index.html", {"header_context": header_context})
