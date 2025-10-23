from django.shortcuts import render
from django.views.decorators.http import require_http_methods


@require_http_methods(["GET"])
def index(request):
    header_context = {
        "title": "Gerenciamento de Desenvolvedores",
        "subtitle": "Configure valores por hora e visualize estatísticas",
        "breadcrumb": "Gerenciamento",
    }
    return render(
        request, "desenvolvedores/index.html", {"header_context": header_context}
    )
