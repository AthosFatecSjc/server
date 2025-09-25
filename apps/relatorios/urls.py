from django.urls import path, include
from .views import index  

urlpatterns = [
    path('', index, name='relatorios_index'),  
    path('atividade/', include('apps.relatorios.atividade.urls')),
    path('comparacao/', include('apps.relatorios.comparacao.urls')),
    path('produtividade/', include('apps.relatorios.produtividade.urls')),
]