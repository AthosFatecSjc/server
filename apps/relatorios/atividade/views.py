from django.http import JsonResponse
from apps.relatorios.atividade.services import AtividadeService


def relatorio_horas_por_dev(request):
    mes = request.GET.get('mes')

    if not mes:
        return JsonResponse({'erro': 'Parâmetro "mes" é obrigatório.'}, status=400)

    service = AtividadeService()
    dados = service.soma_horas_por_dev_por_mes(mes)
    return JsonResponse({'resultado': dados}, safe=False)


def relatorio_horas_por_projeto(request):
    mes = request.GET.get('mes')

    if not mes:
        return JsonResponse({'erro': 'Parâmetro "mes" é obrigatório.'}, status=400)

    service = AtividadeService()
    dados = service.horas_por_dev_e_projeto_por_mes(mes)
    return JsonResponse({'resultado': dados}, safe=False)
