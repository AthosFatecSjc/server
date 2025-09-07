
from django.urls import path, include

urlpatterns = [
    path('atividade/', include('apps.relatorios.atividade.urls')),
    path('comparacao/', include('apps.relatorios.comparacao.urls')),
    path('produtividade/', include('apps.relatorios.produtividade.urls')),
]
