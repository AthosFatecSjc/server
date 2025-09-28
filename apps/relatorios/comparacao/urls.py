from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='comparacao_index'),
    path('relatorio-anual', views.relatorio_anual_comparacao, name='relatorio_anual_comparacao'),
    path('exportar-pdf', views.exportar_pdf, name='exportar_pdf'),
]