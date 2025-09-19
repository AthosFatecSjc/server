from collections import defaultdict
from django.db.models import Sum, Count
from apps.relatorios.models import ControleHorasEquipe

def gerar_dados_relatorio_atividade(ano, mes):
    queryset = ControleHorasEquipe.objects.filter(
        mes__year=ano,
        mes__month=mes
    ).select_related('funcionario', 'projeto').order_by('funcionario__nome')

    dados_por_colaborador = defaultdict(lambda: defaultdict(float))
    for registro in queryset:
        nome_colaborador = registro.funcionario.nome
        nome_projeto = registro.projeto.nome
        dados_por_colaborador[nome_colaborador][nome_projeto] += float(registro.horas)

    projetos_nomes = sorted(set(queryset.values_list('projeto__nome', flat=True)))
    
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
    
    resumo_projetos = queryset.values('projeto__nome').annotate(
        total_horas=Sum('horas'),
        devs_no_projeto=Count('funcionario', distinct=True)
    ).order_by('-total_horas')

    resumo_projetos_dict = {item['projeto__nome']: item for item in resumo_projetos}

    totais_por_projeto = [
        resumo_projetos_dict.get(p_nome, {}).get('total_horas', 0) for p_nome in projetos_nomes
    ]

    dados_cards = []
    for item in resumo_projetos:
        total_horas = float(item['total_horas'])
        dados_cards.append({
            'projeto_nome': item['projeto__nome'],
            'total_horas': total_horas,
            'percentual': round((total_horas / float(total_geral_horas)) * 100, 1) if total_geral_horas > 0 else 0,
            'desenvolvedores': item['devs_no_projeto'],
        })

    context = {
        'dados_tabela': dados_tabela,
        'dados_cards': dados_cards,
        'projetos_nomes': projetos_nomes,
        'totais_por_projeto': totais_por_projeto,
        'total_geral': total_geral_horas
    }
    
    return context