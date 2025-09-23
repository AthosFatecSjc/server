from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='produtividade_index'),
    path('exportar-pdf/', views.exportar_pdf, name='exportar_produtividade_pdf'),
] 

