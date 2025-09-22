from django.shortcuts import render
from apps.relatorios.produtividade.services import calcular_spends_por_dev
from datetime import datetime

def index(request):
    mes_param = request.GET.get('mes')
    ano_param = request.GET.get('ano')
    
    if mes_param and ano_param:
        mes = int(mes_param)
        ano = int(ano_param)
    else:
        hoje = datetime.now()
        mes = hoje.month
        ano = hoje.year
    
    resultados = calcular_spends_por_dev(mes, ano)
    dias = list(range(1, 32))

    return render(request, 'produtividade/index.html', {
        'resultados': resultados,
        'mes': mes,
        'ano': ano,
        'dias': dias,
    })