from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='atividade_index'),
    path('relatorio/dev/', views.relatorio_horas_por_dev, name='relatorio_por_dev'),
    path('relatorio/projeto/', views.relatorio_horas_por_projeto, name='relatorio_por_projeto'),
]
