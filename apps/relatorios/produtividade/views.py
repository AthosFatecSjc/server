from django.shortcuts import render
from apps.relatorios.produtividade.services import calcular_spends_por_dev  

def index(request):
    mes = 9  
    ano = 2025  

    resultados = calcular_spends_por_dev(mes, ano)
    dias = list(range(1, 32))  

    return render(request, 'produtividade/index.html', {
        'resultados': resultados,
        'mes': mes,
        'ano': ano,
        'dias': dias,
    })
