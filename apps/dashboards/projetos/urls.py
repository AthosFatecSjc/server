from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="projetos_index"),
    path(
        "api/projetos/<int:projeto_id>/orcamento/",
        views.atualizar_orcamento_previsto,
        name="projetos_atualizar_orcamento",
    ),
    path(
        "api/projetos/exportar-pdf/",
        views.exportar_relatorio_pdf,
        name="projetos_exportar_pdf",
    ),
]
