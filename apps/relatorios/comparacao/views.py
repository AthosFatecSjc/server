import datetime
import json
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST
from .services import ComparacaoService

@require_GET
def index(request):
    hoje = datetime.date.today()
    anos_disponiveis = range(hoje.year - 5, hoje.year + 2)

    context = {
        'ano_atual': hoje.year,
        'nome_projetos': ComparacaoService.get_nome_projetos(),
        'anos_disponiveis': anos_disponiveis,
    }

    return render(request, 'comparacao/index.html', context)

@require_GET
def relatorio_anual_comparacao(request: any):
    """
    Método de consolidação de dados e geração das informações utilizadas no Relatório de Comparação Anual.
    """
    try:
        ano = int(request.GET.get('ano'))
    except (TypeError, ValueError):
        ano = datetime.date.today().year
    
    try:
        nome_projeto = str(request.GET.get('nome_projeto'))
    except (TypeError, ValueError):
        return HttpResponse("Nome do projeto inválido")
    
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

    payload = {
        "ano": ano,
        "horas_planejadas_projeto": ComparacaoService.get_horas_previstas_projeto(ano, nome_projeto), 
        "por_dev": por_dev
    }

    return JsonResponse(payload, safe=True)

@require_POST
def exportar_pdf(request):
    try:
        data = json.loads(request.body)
        ano = int(data.get('year', datetime.date.today().year))
        projeto_nome = data.get('project_name', '')
        horas_planejadas = float(data.get('total_planned_hours', 0))
        
        response = ComparacaoService.exportar_relatorio_pdf(ano, projeto_nome, horas_planejadas)
        return response
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@require_POST
def set_horas_previstas_projeto(request: any) -> (HttpResponse | JsonResponse | Exception):
    try:
        data = json.loads(request.body)
        nome_projeto = data.get('nome_projeto', '')
        ano = int(data.get('ano', datetime.date.today().year))
        horas_previstas = float(data.get('horas_previstas', 0))
        
        return ComparacaoService.set_horas_previstas_projeto(nome_projeto, ano, horas_previstas)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
