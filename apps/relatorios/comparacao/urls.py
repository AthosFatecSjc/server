from django.urls import path
from . import views

urlpatterns = [
    path('relatorio-anual/json/', views.relatorio_anual_comparacao_json, name='relatorio_anual_comparacao_json'),
]
