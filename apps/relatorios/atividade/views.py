from django.shortcuts import render

def index(request):
    projetos = [
        "SOS Mnt", "SOS Ges", "SOS Ed", "Ball Analyt", "Ball LNO", "Ball PFS",
        "Ball Dados", "Bayer Mak", "Incra", "Climatem", "Comercial", "Reunião"
    ]

    dados_relatorio_detalhado = [
        {"colaborador_nome": "Aline Dominique", "horas_por_projeto": {"SOS Mnt": 78.5, "Reunião": 3.25}, "total_colaborador": 81.75},
        {"colaborador_nome": "Felipe Faria", "horas_por_projeto": {"SOS Ges": 76.33, "Ball Dados": 2.75, "Incra": 7, "Comercial": 66.67}, "total_colaborador": 175},
        {"colaborador_nome": "Eric Lourenço", "horas_por_projeto": {"SOS Ed": 126.58}, "total_colaborador": 126.58},
        {"colaborador_nome": "Alison Americo", "horas_por_projeto": {"Ball Analyt": 147.15, "Comercial": 20.78}, "total_colaborador": 167.93},
        {"colaborador_nome": "Francisco Bustamante", "horas_por_projeto": {"Ball LNO": 158.92, "Bayer Mak": 3}, "total_colaborador": 148},
        {"colaborador_nome": "Helena Benevenuto", "horas_por_projeto": {"Ball PFS": 168}, "total_colaborador": 168.67},
    ]
    
    dados_resumo_dev = []
    for linha in dados_relatorio_detalhado:
        dados_resumo_dev.append({
            'nome': linha['colaborador_nome'],
            'total': linha['total_colaborador']
        })

    context = {
        'projetos': projetos,
        'dados_relatorio': dados_relatorio_detalhado,
        'dados_resumo_dev': dados_resumo_dev,
        'mes': 8,
        'ano': 2025
    }
    
    return render(request, 'atividade/index.html', context)