from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='comparacao_index'),
    path('relatorio-anual', views.relatorio_anual_comparacao, name='relatorio_anual_comparacao'),
    path('exportar-pdf', views.exportar_pdf, name='exportar_pdf'),
    path('horas-previstas', views.set_horas_previstas_projeto, name='set_horas_previstas_projeto')
]