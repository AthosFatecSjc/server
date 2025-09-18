from django.http import JsonResponse
import datetime
from .services import (
    soma_horas_por_dev_mes,
    soma_horas_previstas_por_dev_mes,
    totais_anuais_e_diferenca,
)

def index(request):
    return render(request, 'comparacao/index.html')

def relatorio_anual_comparacao_json(request, ano=None):
 
    try:
        ano = int(ano or request.GET.get('ano') or datetime.date.today().year)
    except Exception:
        ano = datetime.date.today().year

    realizados = soma_horas_por_dev_mes(ano)
    previstos = soma_horas_previstas_por_dev_mes(ano)
    resumo = totais_anuais_e_diferenca(ano)

    por_dev = {}
    for dev in sorted(set(list(realizados.keys()) + list(previstos.keys()))):
        meses = {}
        for m in range(1, 13):
            meses[m] = {
                'previsto': float(previstos.get(dev, {}).get(m, 0.0)),
                'realizado': float(realizados.get(dev, {}).get(m, 0.0)),
            }
        por_dev[dev] = {
            'mensal': meses,
            'totais': resumo.get(dev, {'total_previsto': 0.0, 'total_realizado': 0.0, 'diferenca': 0.0})
        }

    payload = {
        'ano': ano,
        'por_dev': por_dev,
    }
    return JsonResponse(payload, safe=True)