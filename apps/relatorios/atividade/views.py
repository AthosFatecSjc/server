from django.shortcuts import render
from django.views.decorators.http import require_GET
import datetime
from .services import gerar_dados_relatorio_atividade

def index(request):
    hoje = datetime.date.today()
    anos_disponiveis = range(hoje.year - 5, hoje.year + 2)
    
    context = {
        'ano_atual': hoje.year,
        'mes_atual': hoje.month,
        'anos_disponiveis': anos_disponiveis,
    }
    return render(request, 'atividade/index.html', context)

@require_GET
def relatorio_tabela_e_cards(request):
    hoje = datetime.date.today()
    
    try:
        ano = int(request.GET.get('ano', hoje.year))
        mes = int(request.GET.get('mes', hoje.month))
    except (ValueError, TypeError):
        ano, mes = hoje.year, hoje.month

    context = gerar_dados_relatorio_atividade(ano, mes)
    
    return render(request, 'atividade/partials/_tabela_e_cards.html', context)