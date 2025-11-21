from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="equipes_index"),
]
