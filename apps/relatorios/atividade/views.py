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

    context = {
        'cabecalho': {'titulo': '', 'subtitulo': ''},
        'dados': AtividadeService.gerar_dados_relatorio_atividade(ano, mes)
    }

    response = '<div id="horas_projeto" class="conteudo">'
    response += get_tabela_horas_projeto(context, request)
    response += get_grafico_horas_projeto(context, request)
    response += '</div>'
    response += '<div id="horas_por_dev" class="conteudo" style="margin-top: 15px">'
    response += get_tabela_horas_por_dev(context, request)
    response += get_grafico_horas_por_dev(context, request)
    response += '</div>'
    
    return HttpResponse(response)

def get_tabela_horas_projeto(context, request):
    context.update({'cabecalho': {'titulo': 'Horas por Desenvolvedor e Projeto', 'subtitulo': 'Visualização de horas trabalhadas'}})
    return render_to_string("atividade/partials/_tabela_e_cards.html", context, request=request)

def get_grafico_horas_projeto(context, request):
    context.update({'cabecalho': {'titulo': 'Distribuição de Horas por Projeto', 'subtitulo': 'Visualização percentual das horas trabalhadas'}})

    context['dados']['dados_grafico_pizza'] = [
            {"label": registro["projeto_nome"], "data": registro["total_horas"]}
            for registro in context['dados']['dados_cards']
        ]

    return render_to_string("atividade/partials/_grafico_pizza.html", context, request=request)

def get_tabela_horas_por_dev(context, request):
    context.update({'cabecalho': {'titulo': 'Horas por Dev', 'subtitulo': 'Visualização de horas trabalhadas por desenvolvedor'}})
    return render_to_string("atividade/partials/_tabela_horas_dev.html", context, request=request)

def get_grafico_horas_por_dev(context, request):
    context.update({'cabecalho': {'titulo': 'Distribuição de Horas por Dev', 'subtitulo': 'Visualização percentual das horas trabalhadas dor desenvolvedor'}})

    context['dados']['dados_grafico_pizza'] = [
            {"label": registro["colaborador_nome"], "data": registro["total_colaborador"]}
            for registro in context['dados']['dados_tabela']
        ]

    return render_to_string("atividade/partials/_grafico_pizza.html", context, request=request)