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
        :return: Lista de dicionários com 'funcionario', 'projeto', 'total_horas'
        """
        try:
            mes_date = datetime.strptime(mes, '%Y-%m')
        except ValueError:
            raise ValueError("Formato de mês inválido. Use o formato 'YYYY-MM'.")

        # Horas por projeto
        dados = (
            ControleHorasEquipe.objects
            .filter(mes__year=mes_date.year, mes__month=mes_date.month)
            .values('funcionario__nome', 'projeto__nome')
            .annotate(total_horas=Sum('horas'))
            .order_by('funcionario__nome', 'projeto__nome')
        )

        totais = defaultdict(float)
        resultado = []

        for item in dados:
            funcionario = item['funcionario__nome']
            total_horas = float(item['total_horas'])
            totais[funcionario] += total_horas

            resultado.append({
                'funcionario': funcionario,
                'projeto': item['projeto__nome'],
                'total_horas': total_horas
            })

        # Adiciona linhas de total por dev
        for funcionario, total in totais.items():
            resultado.append({
                'funcionario': funcionario,
                'projeto': 'TOTAL',
                'total_horas': total
            })

        return resultado

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
            .values('funcionario__nome')
            .annotate(total_horas=Sum('horas'))
            .order_by('funcionario__nome')
        )

        return list(dados)
