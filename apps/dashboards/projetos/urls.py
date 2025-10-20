from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='projetos_index'),
]