# urls.py
from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="desenvolvedores_index"),
    path("dados/", views.get_dados_desenvolvedores, name="get_dados_desenvolvedores"),
    path("atualizar-valor/", views.atualizar_valor_hora, name="atualizar_valor_hora"),
]
