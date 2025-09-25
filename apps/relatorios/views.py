from django.shortcuts import render
from django.views.decorators.http import require_http_methods

@require_http_methods(["GET"]) 
def index(request):
    relatorios = [
        {
            'nome': 'Gestão à Vista - Operacional', 
            'url': 'produtividade/', 
            'descricao': 'Relatório de Produtividade Diária/Mensal em formato calendário',
            'categoria': 'Produtividade'
        },
        {
            'nome': 'Controle de Horas - Projeto / Equipe', 
            'url': 'atividade/', 
            'descricao': 'Atividades por projeto com tabela e gráfico de distribuição',
            'categoria': 'Projetos'
        },
        {
            'nome': 'Controle de Horas SOS', 
            'url': 'comparacao/', 
            'descricao': 'Comparação de horas realizadas vs previstas com gráfico de barras',
            'categoria': 'Comparativo'
        }
    ]
    return render(request, 'relatorios/index.html', {'relatorios': relatorios})