from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='comparacao_index'),
    path('relatorio-anual', views.relatorio_anual_comparacao_json, name='relatorio_anual_comparacao_json'),
]
