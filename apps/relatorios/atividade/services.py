from collections import defaultdict
from datetime import datetime
from django.db.models import Sum
from ..models import ControleHorasEquipe


class AtividadeService:
    """
    Service para gerar relatórios de horas trabalhadas.
    """

    def horas_por_dev_e_projeto_por_mes(self, mes: str):
        """
        Lista as horas de cada dev por projeto e o total por dev para um mês específico.
        :param mes: String no formato 'YYYY-MM'
        :return: Dicionário com duas listas: 'por_projeto' e 'total_por_dev'
        """
        try:
            mes_date = datetime.strptime(mes, '%Y-%m')
        except ValueError:
            raise ValueError("Formato de mês inválido. Use o formato 'YYYY-MM'.")

        # Horas por projeto
        dados = (
            ControleHorasEquipe.objects
            .filter(mes__year=mes_date.year, mes__month=mes_date.month)
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

    def soma_horas_por_dev_por_mes(self, mes: str):
        """
        Soma as horas agrupadas por desenvolvedor em um mês.
        :param mes: String no formato 'YYYY-MM'
        :return: Lista de dicionários com 'funcionario', 'total_horas'
        """
        try:
            mes_date = datetime.strptime(mes, '%Y-%m')
        except ValueError:
            raise ValueError("Formato de mês inválido. Use o formato 'YYYY-MM'.")

        dados = (
            ControleHorasEquipe.objects
            .filter(mes__year=mes_date.year, mes__month=mes_date.month)
            .values('funcionario_id__nome')
            .annotate(total_horas=Sum('horas'))
            .order_by('funcionario_id__nome')
        )

        return list(dados)
