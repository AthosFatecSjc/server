from django.shortcuts import render
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.views.decorators.http import require_GET
import datetime
from .services import AtividadeService

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

    context = AtividadeService.gerar_dados_relatorio_atividade(ano, mes)

    response = '<div id="horas_projeto" class="conteudo">'
    response += render_to_string("atividade/partials/_tabela_e_cards.html", context, request=request)
    response += render_to_string("atividade/partials/_grafico_pizza.html", context, request=request)
    response += '</div>'
    response += '<div id="horas_por_dev" class="conteudo" style="margin-top: 15px">'
    # response += render_to_string("atividade/partials/_tabela_e_cards.html", context, request=request)
    response += render_to_string("atividade/partials/_grafico_pizza.html", context, request=request)
    response += '</div>'

    
    return HttpResponse(response)