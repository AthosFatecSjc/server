from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='atividade_index'),
    path('tabela/', views.relatorio_tabela_e_cards, name='relatorio_tabela_e_cards'),
    path('exportar-pdf/', views.exportar_pdf, name='exportar_atividade_pdf'),
]