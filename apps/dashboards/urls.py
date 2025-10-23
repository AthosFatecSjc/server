from django.urls import include, path

from .views import index

urlpatterns = [
    path("", index, name="dashboards_index"),
    path("desenvolvedores/", include("apps.dashboards.desenvolvedores.urls")),
    path("projeto/", include("apps.dashboards.projetos.urls")),
]
