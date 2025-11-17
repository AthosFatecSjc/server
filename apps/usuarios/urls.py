"""URLs do módulo de usuários."""

from django.urls import path

from .views import (
    UsuarioCreateView,
    UsuarioDeleteView,
    UsuarioDetailView,
    UsuarioListView,
    UsuarioStatusToggleView,
    UsuarioUpdateView,
)

app_name = "usuarios"

urlpatterns = [
    path("", UsuarioListView.as_view(), name="lista"),
    path("novo/", UsuarioCreateView.as_view(), name="criar"),
    path("<int:pk>/", UsuarioDetailView.as_view(), name="detalhe"),
    path("<int:pk>/editar/", UsuarioUpdateView.as_view(), name="editar"),
    path("<int:pk>/status/", UsuarioStatusToggleView.as_view(), name="status"),
    path("<int:pk>/excluir/", UsuarioDeleteView.as_view(), name="excluir"),
]
