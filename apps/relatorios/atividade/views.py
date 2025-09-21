from django.shortcuts import render
from django.views.decorators.http import require_GET
import datetime
from .services import AtividadeService

def index(request):
    hoje = datetime.date.today()
    anos_disponiveis = range(hoje.year - 5, hoje.year + 2)

    dados_iniciais = AtividadeService.gerar_dados_relatorio_atividade(hoje.year, hoje.month)
    
    context = {
        'ano_atual': hoje.year,
        'mes_atual': hoje.month,
        'anos_disponiveis': anos_disponiveis,
        'dados_cards': dados_iniciais.get('dados_cards', []),
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

    context = AtividadeService.gerar_dados_relatorio_atividade(ano, mes)
    
    return render(request, 'atividade/partials/_tabela_e_cards.html', context)