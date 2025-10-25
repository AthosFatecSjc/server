"""Serviços para o dashboard de projetos."""

from decimal import Decimal
from typing import Any

from django.db.models import F, Sum

from olap_models.models import DimProjeto, FatoRegistroHoras


class CustoPorDesenvolvedorService:
    """Service para calcular dados de custo por desenvolvedor."""

    @staticmethod
    def obter_custo_por_desenvolvedor(projeto_id: int = None) -> list[dict[str, Any]]:
        """
        Obtém dados de custo por desenvolvedor do banco OLAP.
        
        Args:
            projeto_id: ID do projeto para filtrar (opcional).
            
        Returns:
            Lista de dicionários com nome e custo total.
        """
        try:
            queryset = FatoRegistroHoras.objects.using('olap').select_related(
                'funcionario', 'projeto'
            )
            
            if projeto_id:
                queryset = queryset.filter(projeto_id=projeto_id)
            
            dados = queryset.values(
                nome=F('funcionario__nome')
            ).annotate(
                custo=Sum('custo')
            ).order_by('-custo')
            
            return [
                {
                    'nome': item['nome'],
                    'custo': item['custo'] or Decimal('0.00')
                }
                for item in dados
            ]
        except Exception:
            return []

    @staticmethod
    def formatar_para_grafico(dados: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Formata dados para o componente de gráfico.
        
        Args:
            dados: Lista de dicionários com nome e custo.
            
        Returns:
            Dicionário com labels, values e max_value.
        """
        if not dados:
            return {
                'labels': [],
                'values': [],
                'max_value': 0
            }
        
        labels = [item['nome'] for item in dados]
        values = [float(item['custo']) for item in dados]
        max_value = max(values) * 1.1 if values else 0
        
        return {
            'labels': labels,
            'values': values,
            'max_value': max_value
        }
