from django.shortcuts import render

def index(request):
    # --- DADOS MOCKADOS ---
    # No futuro, esta secção será substituída pela lógica de busca na base de dados.

    # 1. Lista de nomes dos projetos (para o cabeçalho da tabela)
    projetos = [
        "SOS Mnt", "SOS Ges", "SOS Ed", "Ball Analyt", "Ball LNO", "Ball PFS",
        "Ball Dados", "Bayer Mak", "Incra", "Climatem", "Comercial", "Reunião"
    ]

    # 2. Dados do relatório (linhas da tabela)
    dados_relatorio = [
        {
            "colaborador_nome": "Aline Dominique",
            "horas_por_projeto": {"SOS Mnt": 78.5, "Reunião": 3.25},
            "total_colaborador": 81.75
        },
        {
            "colaborador_nome": "Felipe Faria",
            "horas_por_projeto": {"SOS Ges": 76.33, "Ball Dados": 2.75, "Incra": 7, "Comercial": 66.67},
            "total_colaborador": 21.75 # A soma na imagem parece estar incorreta, ajustei para exemplo
        },
        {
            "colaborador_nome": "Eric Lourenço",
            "horas_por_projeto": {"SOS Ed": 126.58},
            "total_colaborador": 126.58
        },
        {
            "colaborador_nome": "Alison Americo",
            "horas_por_projeto": {"Ball Analyt": 147.15, "Comercial": 20.78},
            "total_colaborador": 167.93
        },
        {
            "colaborador_nome": "Francisco Bustamante",
            "horas_por_projeto": {"Ball LNO": 158.92, "Bayer Mak": 3},
            "total_colaborador": 148 # A soma na imagem parece estar incorreta, ajustei para exemplo
        },
        {
            "colaborador_nome": "Helena Benevenuto",
            "horas_por_projeto": {"Ball PFS": 168},
            "total_colaborador": 168
        }
        # Adicione mais colaboradores aqui para replicar a tabela completa...
    ]
    
    # --- FIM DOS DADOS MOCKADOS ---

    # O 'context' é o dicionário que envia os dados para o template.
    # A estrutura é a mesma da abordagem com base de dados.
    context = {
        'projetos': projetos,
        'dados_relatorio': dados_relatorio,
        'mes': 8, # Agosto
        'ano': 2025 # Exemplo
    }
    
    return render(request, 'atividade/index.html', context)