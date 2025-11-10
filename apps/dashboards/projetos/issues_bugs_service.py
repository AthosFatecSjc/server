"""Serviço para dashboard de Issues e Bugs."""

from decimal import Decimal
from typing import Any, Dict, List, Optional

from django.db.models import Count, F, Q, Sum

from olap_models.models import DimIssue, FatoRegistroHoras


class IssuesBugsService:
    """Regras de negócio para o dashboard de issues e bugs."""

    ISSUE_TYPES_TAREFA = ["Tarefa", "Subtarefa"]
    ISSUE_TYPE_BUG = "Bug"

    @classmethod
    def obter_dados_dashboard(
        cls, projeto_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Obtém dados consolidados de issues e bugs para o dashboard.

        Args:
            projeto_id: ID do projeto para filtrar (opcional).

        Returns:
            Dicionário com dados de issues, bugs e totais.
        """
        dados_issues = cls._obter_dados_por_tipo(
            projeto_id, cls.ISSUE_TYPES_TAREFA, tipo_label="issue"
        )
        dados_bugs = cls._obter_dados_por_tipo(
            projeto_id, [cls.ISSUE_TYPE_BUG], tipo_label="bug"
        )

        totais = cls._calcular_totais(dados_issues, dados_bugs)

        return {
            "issues": dados_issues,
            "bugs": dados_bugs,
            "totais": totais,
        }

    @classmethod
    def _obter_dados_por_tipo(
        cls, projeto_id: Optional[int], tipos_issue: List[str], tipo_label: str
    ) -> List[Dict[str, Any]]:
        """
        Busca dados de registro de horas filtrados por tipo de issue.

        Args:
            projeto_id: ID do projeto (opcional).
            tipos_issue: Lista de tipos de issue do Jira.
            tipo_label: Label para identificação ('issue' ou 'bug').

        Returns:
            Lista de dicionários com dados dos itens.
        """
        queryset = FatoRegistroHoras.objects.using("olap").select_related(
            "issue", "funcionario", "projeto"
        )

        if projeto_id:
            queryset = queryset.filter(projeto_id=projeto_id)

        queryset = queryset.filter(
            issue__isnull=False, issue__issue_type__in=tipos_issue
        )

        dados_agrupados = (
            queryset.values(
                "issue__issue_id",
                "issue__issue_type",
                "funcionario__nome",
                "issue__issue_title",
            )
            .annotate(
                total_horas=Sum("horas_trabalhadas"),
                custo_total=Sum("custo"),
            )
            .order_by("issue__issue_id")
        )

        resultado = []
        for item in dados_agrupados:
            issue_id = item.get("issue__issue_id") or "SEM-ID"
            status = cls._inferir_status_padronizado(item)

            resultado.append(
                {
                    "id": issue_id,
                    "tipo": tipo_label,
                    "developer": item.get("funcionario__nome") or "Sem desenvolvedor",
                    "status": status,
                    "horas": float(item.get("total_horas") or 0),
                    "custo": float(item.get("custo_total") or 0),
                }
            )

        return resultado

    @staticmethod
    def _inferir_status_padronizado(item: Dict[str, Any]) -> str:
        """
        Infere o status padronizado de uma issue baseado nos dados disponíveis.

        Args:
            item: Dicionário com dados da issue.

        Returns:
            Status padronizado.
        """
        horas = item.get("total_horas") or 0

        if horas == 0:
            return "Não iniciado"
        if horas > 0:
            return "Em progresso"

        return "Não iniciado"

    @classmethod
    def _calcular_totais(
        cls, dados_issues: List[Dict[str, Any]], dados_bugs: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Calcula totalizações gerais de issues e bugs.

        Args:
            dados_issues: Lista de issues.
            dados_bugs: Lista de bugs.

        Returns:
            Dicionário com totais consolidados.
        """
        total_issues = len(dados_issues)
        total_bugs = len(dados_bugs)

        issues_abertas = sum(
            1 for item in dados_issues if item["status"] != "Concluído"
        )
        bugs_ativos = sum(1 for item in dados_bugs if item["status"] != "Concluído")

        valor_total_issues = sum(item["custo"] for item in dados_issues)
        valor_total_bugs = sum(item["custo"] for item in dados_bugs)
        valor_total_geral = valor_total_issues + valor_total_bugs

        return {
            "total_issues": total_issues,
            "issues_abertas": issues_abertas,
            "total_bugs": total_bugs,
            "bugs_ativos": bugs_ativos,
            "valor_total": float(valor_total_geral),
        }
