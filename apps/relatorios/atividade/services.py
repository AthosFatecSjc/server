from collections import defaultdict
from django.db.models import Sum, Count
from apps.relatorios.models import ControleHorasEquipe
from datetime import datetime


class AtividadeService:
    """
    Service para gerar relatórios de horas trabalhadas.
    """

    @staticmethod
    def horas_por_dev_e_projeto_por_mes(ano: int, mes: int) -> dict[list, list]:
        """
        Lista as horas de cada dev por projeto e o total por dev para um mês específico.

        Parameters:
            ano (int): Ano para geração do relatório
            mes (int): Mes para geração do relatório
        
        Returns:
            dict: Dicionário com duas listas: 'por_projeto' e 'total_por_dev'
        """

        # Horas por projeto
        dados = (
            ControleHorasEquipe.objects
            .filter(mes__year=ano, mes__month=mes)
            .values('funcionario_id__nome', 'projeto_id__nome')
            .annotate(total_horas=Sum('horas'))
            .order_by('funcionario_id__nome', 'projeto_id__nome')
        )

        totais = defaultdict(float)
        por_projeto = []

        for item in dados:
            funcionario = item['funcionario_id__nome']
            projeto = item['projeto_id__nome']
            total_horas = float(item['total_horas'])
            
            por_projeto.append({
                'funcionario': funcionario,
                'projeto': projeto,
                'total_horas': total_horas
            })
            totais[funcionario] += total_horas

        total_por_dev = [
            {'funcionario': funcionario, 'total_horas': total}
            for funcionario, total in totais.items()
        ]

        return {
            'por_projeto': por_projeto,
            'total_por_dev': total_por_dev
        }

    @staticmethod
    def soma_horas_por_dev_por_mes(ano: int, mes: int) -> list[dict[str, float]]:
        """
        Soma as horas agrupadas por desenvolvedor em um mês.

        Parameters:
            ano (int): Ano para geração do relatório
            mes (int): Mes para geração do relatório
        
        Returns:
            List: Lista de dicionários com 'funcionario', 'total_horas'
        """

        dados = (
            ControleHorasEquipe.objects
            .filter(mes__year=ano, mes__month=mes)
            .values('funcionario_id__nome')
            .annotate(total_horas=Sum('horas'))
            .order_by('funcionario_id__nome')
        )

        return list(dados)

    @staticmethod
    def gerar_dados_relatorio_atividade(ano: int, mes: int) -> dict:
        """
        Essa função gera os dados de relatório de atividade

        Parameters:
            ano (int): Ano para geração do relatório
            mes (int): Mes para geração do relatório

        Returns:
            dict: Dados filtrados para geração da tabela
        """

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
