from django.shortcuts import render
from apps.relatorios.models import ControleHorasEquipe, Projeto
from django.db.models import Sum
from collections import defaultdict
import datetime

def index(request):
    hoje = datetime.date.today()
    anos_disponiveis = range(hoje.year - 5, hoje.year + 2)
    
    context = {
        'ano_atual': hoje.year,
        'mes_atual': hoje.month,
        'anos_disponiveis': anos_disponiveis,
    }
    return render(request, 'atividade/index.html', context)

def relatorio_tabela_e_cards(request):
    hoje = datetime.date.today()
    
    try:
        ano = int(request.GET.get('ano', hoje.year))
        mes = int(request.GET.get('mes', hoje.month))
    except (ValueError, TypeError):
        ano, mes = hoje.year, hoje.month

    queryset = ControleHorasEquipe.objects.filter(
        mes__year=ano,
        mes__month=mes
    ).select_related('funcionario', 'projeto').order_by('funcionario__nome')

    dados_por_colaborador = defaultdict(lambda: defaultdict(float))
    for registro in queryset:
        nome_colaborador = registro.funcionario.nome
        nome_projeto = registro.projeto.nome
        dados_por_colaborador[nome_colaborador][nome_projeto] += float(registro.horas)

    projetos_nomes = sorted(list(Projeto.objects.filter(id__in=queryset.values_list('projeto_id', flat=True)).values_list('nome', flat=True)))
    
    dados_tabela = []
    for colaborador, projetos in dados_por_colaborador.items():
        total_colaborador = sum(projetos.values())
        horas_ordenadas = [projetos.get(p_nome, 0) for p_nome in projetos_nomes]
        dados_tabela.append({
            'colaborador_nome': colaborador,
            'horas': horas_ordenadas,
            'total_colaborador': total_colaborador
        })

    total_geral_horas = queryset.aggregate(total=Sum('horas'))['total'] or 0
    
    totais_por_projeto = []
    for projeto_nome in projetos_nomes:
        total = queryset.filter(projeto__nome=projeto_nome).aggregate(total=Sum('horas'))['total'] or 0
        totais_por_projeto.append(total)

    dados_cards_qs = queryset.values('projeto__nome').annotate(
        total_horas=Sum('horas'),
    ).order_by('-total_horas')

    dados_cards = []
    for item in dados_cards_qs:
        total_horas = float(item['total_horas'])
        devs_no_projeto = queryset.filter(projeto__nome=item['projeto__nome']).values('funcionario').distinct().count()
        dados_cards.append({
            'projeto_nome': item['projeto__nome'],
            'total_horas': total_horas,
            'percentual': round((total_horas / float(total_geral_horas)) * 100, 1) if total_geral_horas > 0 else 0,
            'desenvolvedores': devs_no_projeto,
        })

    context = {
        'dados_tabela': dados_tabela,
        'dados_cards': dados_cards,
        'projetos_nomes': projetos_nomes,
        'totais_por_projeto': totais_por_projeto,
        'total_geral': total_geral_horas
    }
    
    return render(request, 'atividade/partials/_tabela_e_cards.html', context)