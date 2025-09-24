import datetime
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET
from .services import ComparacaoService

@require_GET
def index(request):
    return render(request, 'comparacao/index.html')

@require_GET
def relatorio_anual_comparacao(request: any, ano: int = None):
    """
    Método de consolidação de dados e geração das informações utilizadas no Relatório de Comparação Anual.

    Parameters:
        ano (int): Ano para geração do relatório.
    
    Returns:
        dict (str, any): Dicionário com um inteiro e uma lista 'ano' e 'por_dev'.
    """

    try:
        ano = int(ano or request.GET.get('ano') or datetime.date.today().year)
    except Exception:
        ano = datetime.date.today().year

    realizados = ComparacaoService.soma_horas_por_dev_mes(ano)
    previstos = ComparacaoService.soma_horas_previstas_por_dev_mes(ano)
    resumo = ComparacaoService.totais_anuais_e_diferenca(ano)

    por_dev = {}
    for dev in sorted(set(list(realizados.keys()) + list(previstos.keys()))):
        meses = {}
        for m in range(1, 13):
            meses[m] = {
                "previsto": float(previstos.get(dev, {}).get(m, 0.0)),
                "realizado": float(realizados.get(dev, {}).get(m, 0.0)),
            }
        por_dev[dev] = {
            "mensal": meses,
            "totais": resumo.get(
                dev,
                {"total_previsto": 0.0, "total_realizado": 0.0, "diferenca": 0.0},
            ),
        }

    payload = {"ano": ano, "por_dev": por_dev}
    return JsonResponse(payload, safe=True)
