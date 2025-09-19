from django.shortcuts import render
from django.db.models import Min
from apps.relatorios.produtividade.services import calcular_spends_por_dev
from datetime import datetime

from apps.relatorios.models import TempoGastoEquipe

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
    
    MESES_PORTUGUES = {
        1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril',
        5: 'Maio', 6: 'Junho', 7: 'Julho', 8: 'Agosto',
        9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'
    }
    
    meses_disponiveis_query = TempoGastoEquipe.objects.extra(
        select={'ano': 'EXTRACT(YEAR FROM mes)', 'mes_num': 'EXTRACT(MONTH FROM mes)'}
    ).values('ano', 'mes_num').distinct()
    
    meses_disponiveis = []
    for item in meses_disponiveis_query:
        mes_num = int(item['mes_num'])
        meses_disponiveis.append({
            'mes': mes_num,
            'ano': int(item['ano']),
            'mes_nome': MESES_PORTUGUES.get(mes_num, f'Mês {mes_num}')
        })
    
    meses_disponiveis.sort(key=lambda x: (x['ano'], x['mes']), reverse=True)
    
    resultados = calcular_spends_por_dev(mes, ano)
    dias = list(range(1, 32))

    return render(request, 'produtividade/index.html', {
        'resultados': resultados,
        'mes': mes,
        'ano': ano,
        'dias': dias,
        'meses_disponiveis': meses_disponiveis,
        'mes_nome': MESES_PORTUGUES.get(mes, f'Mês {mes}')  
    })