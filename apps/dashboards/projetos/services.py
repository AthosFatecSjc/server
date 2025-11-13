"""Serviços para o dashboard de projetos."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO
from typing import Any, Dict, Optional

from django.db import transaction
from django.db.models import Avg, Count, F, Max, Min, Sum
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from apps.relatorios.models import Issue
from apps.relatorios.models import Projeto as ProjetoOLTP
from olap_models.models import DimProjeto, FatoRegistroHoras


class DashboardProjetoError(Exception):
    """Erro base para operações do dashboard de projetos."""


class OrcamentoInvalidoError(DashboardProjetoError):
    """Falha ao validar o orçamento previsto informado."""


class ProjetoNaoEncontradoError(DashboardProjetoError):
    """Projeto não encontrado no banco OLTP."""


DEFAULT_STATUS_LABEL = "Sem status"


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
            queryset = FatoRegistroHoras.objects.using("olap").select_related(
                "funcionario", "projeto"
            )

            if projeto_id:
                queryset = queryset.filter(projeto_id=projeto_id)

            dados = (
                queryset.values(nome=F("funcionario__nome"))
                .annotate(custo=Sum("custo"))
                .order_by("-custo")
            )

            return [
                {"nome": item["nome"], "custo": item["custo"] or Decimal("0.00")}
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
            return {"labels": [], "values": [], "max_value": 0}

        labels = [item["nome"] for item in dados]
        values = [float(item["custo"]) for item in dados]
        max_value = max(values) * 1.1 if values else 0

        return {"labels": labels, "values": values, "max_value": max_value}


class IssuesBugsDashboardService:
    """Agrupa métricas operacionais das issues e bugs de um projeto."""

    STATUS_COLOR_MAP = {
        "não iniciado": "#94A3B8",
        "em progresso": "#F59E0B",
        "mr": "#3B82F6",
        "concluído": "#10B981",
    }
    COLOR_PALETTE = [
        "#6366F1",
        "#EC4899",
        "#F97316",
        "#0EA5E9",
        "#FACC15",
        "#22D3EE",
        "#8B5CF6",
        "#14B8A6",
    ]

    @classmethod
    def obter_dados_para_projetos(
        cls, projeto_ids: list[int] | tuple[int, ...] | set[int]
    ) -> dict[int, dict[str, Any]]:
        """Carrega os dados necessários para o dashboard de issues/bugs."""
        if not projeto_ids:
            return {}

        ids: list[int] = sorted({int(pid) for pid in projeto_ids if pid})
        if not ids:
            return {}

        agrupados: dict[int, list[dict[str, Any]]] = {pid: [] for pid in ids}

        queryset = (
            Issue.objects.filter(projeto_id__in=ids)
            .select_related("funcionario", "tipo_issue")
            .order_by("jira_key")
        )

        for issue in queryset:
            agrupados.setdefault(issue.projeto_id, []).append(
                cls._serializar_issue(issue)
            )

        resultado: dict[int, dict[str, Any]] = {}
        for projeto_id in ids:
            itens = agrupados.get(projeto_id) or []
            resultado[projeto_id] = cls._construir_dashboard(itens)

        return resultado

    @classmethod
    def estrutura_vazia(cls) -> dict[str, Any]:
        """Estrutura padrão para evitar condicionais no template."""
        return {
            "cards": {
                "total_issues": 0,
                "issues_abertas": 0,
                "total_bugs": 0,
                "bugs_ativos": 0,
                "valor_total": 0.0,
            },
            "chart": cls._chart_vazio(),
            "chart_por_tipo": {
                "issues": cls._chart_vazio(),
                "bugs": cls._chart_vazio(),
            },
            "itens": [],
        }

    @staticmethod
    def _chart_vazio() -> dict[str, list[Any]]:
        return {"labels": [], "values": [], "colors": []}

    @classmethod
    def _serializar_issue(cls, issue: Issue) -> dict[str, Any]:
        tipo_nome = (issue.tipo_issue.nome if issue.tipo_issue else "").strip().lower()
        tipo = "bug" if "bug" in tipo_nome else "issue"

        segundos = issue.tempo_gasto_seconds or issue.tempo_estimado_seconds or 0
        horas = round(segundos / 3600, 2) if segundos else 0.0

        valor_hora = (
            float(issue.funcionario.valor_hora)
            if issue.funcionario and issue.funcionario.valor_hora is not None
            else 0.0
        )
        custo = round(horas * valor_hora, 2)
        status = cls._classificar_status(
            status_original=issue.status,
            tem_funcionario=issue.funcionario is not None,
            horas=horas,
        )

        return {
            "id": issue.jira_key or f"ISSUE-{issue.id}",
            "tipo": tipo,
            "developer": (
                issue.funcionario.nome if issue.funcionario else "Não atribuído"
            ),
            "status": status,
            "horas": horas,
            "custo": custo,
        }

    @classmethod
    def _construir_dashboard(cls, itens: list[dict[str, Any]]) -> dict[str, Any]:
        if not itens:
            return cls.estrutura_vazia()

        itens_visiveis = cls._filtrar_itens_visiveis(itens)
        cards = cls._calcular_cards(itens)
        chart = (
            cls._calcular_chart(itens_visiveis)
            if itens_visiveis
            else cls._chart_vazio()
        )
        chart_por_tipo = {
            "issues": cls._calcular_chart(
                [item for item in itens_visiveis if item["tipo"] == "issue"]
            ),
            "bugs": cls._calcular_chart(
                [item for item in itens_visiveis if item["tipo"] == "bug"]
            ),
        }
        return {
            "cards": cards,
            "chart": chart,
            "chart_por_tipo": chart_por_tipo,
            "itens": itens_visiveis,
        }

    @classmethod
    def _calcular_cards(cls, itens: list[dict[str, Any]]) -> dict[str, Any]:
        total_issues = sum(1 for item in itens if item["tipo"] == "issue")
        total_bugs = sum(1 for item in itens if item["tipo"] == "bug")

        issues_abertas = sum(
            1
            for item in itens
            if item["tipo"] == "issue" and not cls._esta_concluido(item["status"])
        )
        bugs_ativos = sum(
            1
            for item in itens
            if item["tipo"] == "bug" and not cls._esta_concluido(item["status"])
        )

        valor_total = round(sum(float(item.get("custo") or 0.0) for item in itens), 2)

        return {
            "total_issues": total_issues,
            "issues_abertas": issues_abertas,
            "total_bugs": total_bugs,
            "bugs_ativos": bugs_ativos,
            "valor_total": valor_total,
        }

    @classmethod
    def _calcular_chart(cls, itens: list[dict[str, Any]]) -> dict[str, list[Any]]:
        contagem: dict[str, int] = {}
        for item in itens:
            status = cls._normalizar_status(item.get("status"))
            contagem[status] = contagem.get(status, 0) + 1

        labels = list(contagem.keys())
        values = [contagem[label] for label in labels]
        colors: list[str] = []

        for idx, label in enumerate(labels):
            color = cls.STATUS_COLOR_MAP.get(label.lower())
            if not color:
                color = cls.COLOR_PALETTE[idx % len(cls.COLOR_PALETTE)]
            colors.append(color)

        return {"labels": labels, "values": values, "colors": colors}

    @classmethod
    def _filtrar_itens_visiveis(
        cls, itens: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        if not itens:
            return []

        visiveis: list[dict[str, Any]] = []
        for item in itens:
            if cls._deve_ocultar_item(item):
                continue
            visiveis.append(item)
        return visiveis

    @classmethod
    def _deve_ocultar_item(cls, item: dict[str, Any]) -> bool:
        developer = item.get("developer")
        horas = cls._parse_float(item.get("horas"))

        if not cls._is_nao_atribuido(developer):
            return False
        return horas <= 0.0

    @staticmethod
    def _parse_float(value: Any) -> float:
        if value is None:
            return 0.0
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _is_nao_atribuido(developer: Optional[str]) -> bool:
        if developer is None:
            return True
        texto = unicodedata.normalize("NFKD", str(developer).strip().lower())
        ascii_text = "".join(ch for ch in texto if not unicodedata.combining(ch))
        return ascii_text == "nao atribuido"

    @staticmethod
    def _normalizar_status(status: Optional[str]) -> str:
        return (status or DEFAULT_STATUS_LABEL).strip() or DEFAULT_STATUS_LABEL

    @classmethod
    def _classificar_status(
        cls, status_original: Optional[str], tem_funcionario: bool, horas: float
    ) -> str:
        if cls._is_mr_status(status_original):
            return "MR"
        if cls._esta_concluido(status_original):
            return "Concluído"
        if not tem_funcionario and horas <= 0:
            return "Não iniciado"
        return "Em progresso"

    @staticmethod
    def _is_mr_status(status: Optional[str]) -> bool:
        if not status:
            return False
        normalized = status.strip().lower()
        if not normalized:
            return False
        return normalized in {
            "mr",
            "merge request",
            "merge-review",
        } or normalized.startswith("mr ")

    @staticmethod
    def _esta_concluido(status: Optional[str]) -> bool:
        if not status:
            return False
        return status.strip().lower() in {
            "concluído",
            "concluido",
            "done",
            "finalizado",
        }


@dataclass
class DashboardProjetoContexto:
    """Estrutura de dados para o contexto do dashboard."""

    projetos_dimensao: list[dict[str, Any]]
    dados_grafico: dict[str, Any]
    projeto_selecionado_id: Optional[int]
    projeto_selecionado_nome: Optional[str]


class DashboardProjetoService:
    """Regras de negócio para o dashboard de projetos."""

    MIN_ORCAMENTO = Decimal("0")

    @classmethod
    def montar_contexto_dashboard(
        cls, projeto_id: Optional[int]
    ) -> DashboardProjetoContexto:
        """Constrói o contexto necessário para renderizar o dashboard."""
        projetos_contexto = cls._montar_contextos_basicos()
        cls._anexar_estatisticas_olap(projetos_contexto)
        cls._anexar_estatisticas_issues(projetos_contexto)

        for contexto in projetos_contexto.values():
            contexto["custo_por_dev"] = cls._obter_custo_por_dev_serializado(
                contexto["id"]
            )

        projetos_ordenados = [
            cls._normalizar_contexto_para_template(contexto)
            for contexto in sorted(
                projetos_contexto.values(),
                key=lambda projeto: (
                    (projeto.get("nome_projeto") or "").lower(),
                    projeto["id"],
                ),
            )
        ]

        if not projetos_ordenados:
            dados_grafico = {
                "labels": [],
                "values": [],
                "max_value": 0,
                "has_data": False,
            }
            return DashboardProjetoContexto(
                projetos_dimensao=[],
                dados_grafico=dados_grafico,
                projeto_selecionado_id=None,
                projeto_selecionado_nome=None,
            )

        projeto_selecionado = next(
            (projeto for projeto in projetos_ordenados if projeto["id"] == projeto_id),
            projetos_ordenados[0],
        )

        dados_grafico = cls._montar_dados_grafico(projeto_selecionado["id"])

        return DashboardProjetoContexto(
            projetos_dimensao=projetos_ordenados,
            dados_grafico=dados_grafico,
            projeto_selecionado_id=projeto_selecionado["id"],
            projeto_selecionado_nome=projeto_selecionado.get("nome_projeto"),
        )

    @classmethod
    def _montar_contextos_basicos(cls) -> Dict[int, dict[str, Any]]:
        contextos: Dict[int, dict[str, Any]] = {}

        for projeto in ProjetoOLTP.objects.using("default").all().order_by("nome"):
            contextos[projeto.id] = cls._criar_contexto_base(
                projeto_id=projeto.id,
                nome=projeto.nome,
                data_criacao=projeto.data_criacao,
                orcamento=Decimal(projeto.orcamento_previsto or cls.MIN_ORCAMENTO),
            )

        for projeto_dim in DimProjeto.objects.using("olap").all():
            contexto = contextos.setdefault(
                projeto_dim.id,
                cls._criar_contexto_base(
                    projeto_id=projeto_dim.id,
                    nome=projeto_dim.nome,
                    data_criacao=projeto_dim.data_criacao,
                    orcamento=cls.MIN_ORCAMENTO,
                ),
            )

            if not contexto.get("nome_projeto"):
                contexto["nome_projeto"] = projeto_dim.nome
            if not contexto.get("data_criacao") and projeto_dim.data_criacao:
                contexto["data_criacao"] = projeto_dim.data_criacao

        return contextos

    @classmethod
    def _anexar_estatisticas_olap(cls, contextos: Dict[int, dict[str, Any]]) -> None:
        estatisticas = (
            FatoRegistroHoras.objects.using("olap")
            .values("projeto_id")
            .annotate(
                total_horas=Sum("horas_trabalhadas"),
                total_custo=Sum("custo"),
                total_registros=Count("id"),
                media_horas=Avg("horas_trabalhadas"),
                primeiro_registro=Min("data__data_completa"),
                ultimo_registro=Max("data__data_completa"),
                funcionarios_distintos=Count("funcionario", distinct=True),
            )
        )

        for resumo in estatisticas:
            projeto_key = resumo["projeto_id"]
            contexto = contextos.setdefault(
                projeto_key,
                cls._criar_contexto_base(
                    projeto_id=projeto_key, orcamento=cls.MIN_ORCAMENTO
                ),
            )

            total_horas = Decimal(resumo["total_horas"] or 0)
            total_custo = Decimal(resumo["total_custo"] or 0)
            custo_realizado = Decimal(resumo["total_custo"] or 0)
            media_horas = Decimal(resumo["media_horas"] or 0)

            contexto.update(
                {
                    "total_horas": total_horas,
                    "total_custo": total_custo,
                    "custo_realizado": custo_realizado,
                    "total_registros": resumo["total_registros"] or 0,
                    "media_horas": media_horas,
                    "primeiro_registro": resumo["primeiro_registro"],
                    "ultimo_registro": resumo["ultimo_registro"],
                    "funcionarios_count": resumo["funcionarios_distintos"] or 0,
                }
            )

            orcamento_decimal = contexto.get("orcamento_previsto", cls.MIN_ORCAMENTO)

            saldo_remanescente = orcamento_decimal - custo_realizado
            percentual_utilizado = (
                (custo_realizado / orcamento_decimal) * Decimal("100")
                if orcamento_decimal > 0
                else Decimal("0")
            )

            contexto["saldo_remanescente"] = saldo_remanescente
            contexto["percentual_utilizado"] = percentual_utilizado

    @classmethod
    def _anexar_estatisticas_issues(cls, contextos: Dict[int, dict[str, Any]]) -> None:
        if not contextos:
            return

        dados = IssuesBugsDashboardService.obter_dados_para_projetos(
            list(contextos.keys())
        )

        for projeto_id, contexto in contextos.items():
            contexto["issues_bugs"] = dados.get(
                projeto_id, IssuesBugsDashboardService.estrutura_vazia()
            )

    @classmethod
    def _criar_contexto_base(
        cls,
        projeto_id: int,
        nome: Optional[str] = None,
        data_criacao=None,
        orcamento: Optional[Decimal] = None,
    ) -> dict[str, Any]:
        orcamento_decimal = orcamento if orcamento is not None else cls.MIN_ORCAMENTO
        return {
            "id": projeto_id,
            "nome_projeto": nome,
            "data_criacao": data_criacao,
            "total_horas": Decimal("0"),
            "total_custo": Decimal("0"),
            "custo_realizado": Decimal("0"),
            "custo_por_dev": [],
            "total_registros": 0,
            "media_horas": Decimal("0"),
            "primeiro_registro": None,
            "ultimo_registro": None,
            "funcionarios_count": 0,
            "orcamento_previsto": orcamento_decimal,
            "saldo_remanescente": orcamento_decimal,
            "percentual_utilizado": Decimal("0"),
            "issues_bugs": IssuesBugsDashboardService.estrutura_vazia(),
        }

    @classmethod
    def _normalizar_contexto_para_template(
        cls, contexto: dict[str, Any]
    ) -> dict[str, Any]:
        return {
            "id": contexto["id"],
            "nome_projeto": contexto.get("nome_projeto"),
            "data_criacao": contexto.get("data_criacao"),
            "total_horas": cls._to_float(contexto.get("total_horas")),
            "total_custo": cls._to_float(contexto.get("total_custo")),
            "custo_realizado": cls._to_float(contexto.get("custo_realizado")),
            "custo_por_dev": contexto.get("custo_por_dev", []),
            "total_registros": contexto.get("total_registros", 0),
            "media_horas": cls._to_float(contexto.get("media_horas")),
            "primeiro_registro": contexto.get("primeiro_registro"),
            "ultimo_registro": contexto.get("ultimo_registro"),
            "funcionarios_count": contexto.get("funcionarios_count", 0),
            "orcamento_previsto": cls._to_float(contexto.get("orcamento_previsto")),
            "saldo_remanescente": cls._to_float(contexto.get("saldo_remanescente")),
            "percentual_utilizado": cls._to_float(contexto.get("percentual_utilizado")),
            "issues_bugs": contexto.get("issues_bugs")
            or IssuesBugsDashboardService.estrutura_vazia(),
        }

    @staticmethod
    def _obter_custo_por_dev_serializado(projeto_id: int) -> list[dict[str, Any]]:
        if not projeto_id:
            return []

        dados = (
            FatoRegistroHoras.objects.using("olap")
            .filter(projeto_id=projeto_id)
            .values(
                "funcionario__id",
                "funcionario__nome",
                "funcionario__valor_hora",
            )
            .annotate(total_horas_dev=Sum("horas_trabalhadas"), custo_dev=Sum("custo"))
            .order_by("-custo_dev")
        )

        resultado: list[dict[str, Any]] = []
        for item in dados:
            resultado.append(
                {
                    "funcionario_id": item["funcionario__id"],
                    "funcionario_nome": item["funcionario__nome"],
                    "valor_hora": float(item["funcionario__valor_hora"] or 0),
                    "total_horas": float(item["total_horas_dev"] or 0),
                    "custo_total": float(item["custo_dev"] or 0),
                }
            )

        return resultado

    @staticmethod
    def _to_float(value: Any) -> float:
        if value is None:
            return 0.0
        if isinstance(value, Decimal):
            return float(value)
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @classmethod
    def atualizar_orcamento_previsto(
        cls, projeto_id: int, valor: Any
    ) -> Dict[str, float]:
        """Atualiza o orçamento previsto de um projeto no banco OLTP."""
        valor_decimal = cls._parse_valor_orcamento(valor)

        try:
            with transaction.atomic():
                projeto = ProjetoOLTP.objects.select_for_update().get(pk=projeto_id)
                projeto.orcamento_previsto = valor_decimal
                projeto.save(update_fields=["orcamento_previsto"])
        except ProjetoOLTP.DoesNotExist as exc:
            raise ProjetoNaoEncontradoError("Projeto não encontrado.") from exc
        except Exception as exc:  # pragma: no cover - falhas genéricas
            raise DashboardProjetoError(
                "Não foi possível atualizar o orçamento previsto."
            ) from exc

        return cls._calcular_metricas_financeiras(projeto_id, valor_decimal)

    @classmethod
    def obter_dados_pdf(cls, projeto_id: int) -> Dict[str, Any]:
        """Prepara os dados consolidados para geração do PDF."""
        contexto = cls.montar_contexto_dashboard(projeto_id)

        if not contexto.projetos_dimensao:
            raise DashboardProjetoError("Nenhum projeto disponível para exportação.")

        projeto = next(
            (
                item
                for item in contexto.projetos_dimensao
                if item["id"] == contexto.projeto_selecionado_id
            ),
            None,
        )

        if projeto is None:
            raise ProjetoNaoEncontradoError("Projeto não encontrado.")

        return {
            "nome_projeto": projeto.get("nome_projeto") or "Projeto sem nome",
            "orcamento_previsto": float(projeto.get("orcamento_previsto") or 0.0),
            "custo_realizado": float(projeto.get("custo_realizado") or 0.0),
            "saldo_remanescente": float(projeto.get("saldo_remanescente") or 0.0),
            "percentual_utilizado": float(projeto.get("percentual_utilizado") or 0.0),
            "custo_por_dev": projeto.get("custo_por_dev", []),
            "data_geracao": datetime.now(),
            "issues_bugs": projeto.get("issues_bugs")
            or IssuesBugsDashboardService.estrutura_vazia(),
        }

    @classmethod
    def _montar_dados_grafico(cls, projeto_id: Optional[int]) -> dict[str, Any]:
        custo_service = CustoPorDesenvolvedorService()
        dados_custo = custo_service.obter_custo_por_desenvolvedor(projeto_id)
        dados_grafico = custo_service.formatar_para_grafico(dados_custo)

        return {
            "labels": dados_grafico["labels"],
            "values": dados_grafico["values"],
            "max_value": dados_grafico["max_value"],
            "has_data": len(dados_grafico["labels"]) > 0,
        }

    @classmethod
    def _parse_valor_orcamento(cls, valor: Any) -> Decimal:
        if valor is None or valor == "":
            raise OrcamentoInvalidoError("O campo 'valor' é obrigatório.")

        try:
            valor_decimal = Decimal(str(valor))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise OrcamentoInvalidoError("Valor informado é inválido.") from exc

        if valor_decimal <= 0:
            raise OrcamentoInvalidoError(
                "O orçamento previsto deve ser maior que zero."
            )

        return valor_decimal

    @classmethod
    def _calcular_metricas_financeiras(
        cls, projeto_id: int, orcamento_previsto: Decimal
    ) -> Dict[str, float]:
        estatisticas = (
            FatoRegistroHoras.objects.using("olap")
            .filter(projeto_id=projeto_id)
            .aggregate(total_custo=Sum("custo"))
        )

        custo_realizado_decimal = Decimal(estatisticas["total_custo"] or 0)
        saldo_remanescente = orcamento_previsto - custo_realizado_decimal
        percentual_utilizado = (
            (custo_realizado_decimal / orcamento_previsto) * Decimal("100")
            if orcamento_previsto > 0
            else Decimal("0")
        )

        return {
            "orcamento_previsto": float(orcamento_previsto),
            "custo_realizado": float(custo_realizado_decimal),
            "saldo_remanescente": float(saldo_remanescente),
            "percentual_utilizado": float(percentual_utilizado),
        }


class DashboardProjetoPdfService:
    """Gera o PDF do dashboard de custos."""

    @staticmethod
    def _format_currency(value: float) -> str:
        valor = float(value or 0.0)
        formatted = f"R$ {valor:,.2f}"
        return formatted.replace(",", "X").replace(".", ",").replace("X", ".")

    @staticmethod
    def _truncate_text(value: Optional[str], max_chars: int = 32) -> str:
        texto = (value or "").strip()
        if len(texto) <= max_chars:
            return texto
        return texto[: max_chars - 1] + "…"

    @staticmethod
    def _build_cards_table(dados: Dict[str, Any]) -> Table:
        cards_data = [
            [
                "Orçamento Previsto",
                DashboardProjetoPdfService._format_currency(
                    dados["orcamento_previsto"]
                ),
            ],
            [
                "Custo Realizado",
                DashboardProjetoPdfService._format_currency(dados["custo_realizado"]),
            ],
            [
                "Saldo Remanescente",
                DashboardProjetoPdfService._format_currency(
                    dados["saldo_remanescente"]
                ),
            ],
            [
                "% do Orçamento Utilizado",
                f"{dados['percentual_utilizado']:.1f}%",
            ],
        ]

        table = Table(cards_data, colWidths=[95 * mm, 70 * mm])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3F4F6")),
                    ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#111827")),
                    ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#E5E7EB")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        return table

    @staticmethod
    def _build_dev_table(dados: Dict[str, Any]) -> Table:
        header = ["Desenvolvedor", "Horas Trabalhadas", "Valor/Hora", "Custo Total"]
        linhas = [
            [
                item.get("funcionario_nome") or "Sem nome",
                f"{float(item.get('total_horas') or 0.0):.2f}h",
                DashboardProjetoPdfService._format_currency(
                    float(item.get("valor_hora") or 0.0)
                ),
                DashboardProjetoPdfService._format_currency(
                    float(item.get("custo_total") or 0.0)
                ),
            ]
            for item in dados.get("custo_por_dev") or []
        ]

        if not linhas:
            linhas.append(["Nenhum registro encontrado", "-", "-", "-"])

        tabela = Table(
            [header] + linhas, colWidths=[70 * mm, 35 * mm, 35 * mm, 40 * mm]
        )
        tabela.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111827")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 10),
                    ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                    ("ALIGN", (0, 0), (0, -1), "LEFT"),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E5E7EB")),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [colors.white, colors.HexColor("#F9FAFB")],
                    ),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        return tabela

    @staticmethod
    def _build_issues_cards_table(issues_data: Dict[str, Any]) -> Table:
        cards = issues_data.get("cards") or {}
        total_issues = int(cards.get("total_issues", 0))
        issues_abertas = int(cards.get("issues_abertas", 0))
        total_bugs = int(cards.get("total_bugs", 0))
        bugs_ativos = int(cards.get("bugs_ativos", 0))
        valor_total = DashboardProjetoPdfService._format_currency(
            float(cards.get("valor_total", 0.0))
        )

        rows = [
            [
                "Total de Issues",
                f"{total_issues:,}".replace(",", "."),
                f"{issues_abertas} abertas",
            ],
            [
                "Total de Bugs",
                f"{total_bugs:,}".replace(",", "."),
                f"{bugs_ativos} ativos",
            ],
            ["Valor Total (Issues + Bugs)", valor_total, "Todos os itens"],
        ]

        tabela = Table(rows, colWidths=[70 * mm, 30 * mm, 60 * mm])
        tabela.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3F4F6")),
                    ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#111827")),
                    ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                    ("ALIGN", (2, 0), (2, -1), "LEFT"),
                    ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#E5E7EB")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        return tabela

    @staticmethod
    @staticmethod
    def _build_issues_pie_charts(
        issues_data: Dict[str, Any], base_style: ParagraphStyle
    ):
        charts = issues_data.get("chart_por_tipo") or {}
        issues_chart = DashboardProjetoPdfService._build_single_pie_table(
            "Issues por Status", charts.get("issues"), base_style
        )
        bugs_chart = DashboardProjetoPdfService._build_single_pie_table(
            "Bugs por Status", charts.get("bugs"), base_style
        )

        table = Table([[issues_chart, bugs_chart]], colWidths=[80 * mm, 80 * mm])
        table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )
        return table

    @staticmethod
    def _build_single_pie_table(
        title: str, chart: Optional[dict[str, Any]], base_style: ParagraphStyle
    ) -> Table:
        pie_title_style = ParagraphStyle(
            "PieTitle",
            parent=base_style,
            fontSize=11,
            alignment=1,
            textColor=colors.HexColor("#1F2937"),
            spaceAfter=6,
        )

        if not chart or not chart.get("values"):
            body = Paragraph("Sem dados disponíveis.", base_style)
        else:
            labels, values, colors_seq = (
                DashboardProjetoPdfService._normalize_chart_data(chart)
            )
            total = sum(values) or 1
            drawing, _ = DashboardProjetoPdfService._create_pie_drawing(
                values, colors_seq
            )
            legend_table = DashboardProjetoPdfService._create_pie_legend(
                labels, values, colors_seq, total
            )
            body = Table([[drawing], [legend_table]])

        table = Table(
            [[Paragraph(title, pie_title_style)], [body]], colWidths=[80 * mm]
        )
        table.setStyle(
            TableStyle(
                [
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        return table

    @staticmethod
    def _normalize_chart_data(
        chart: dict[str, Any]
    ) -> tuple[list[str], list[float], list[colors.Color]]:
        labels = chart.get("labels") or []
        values = chart.get("values") or []
        colors_chart = chart.get("colors") or []
        palette = IssuesBugsDashboardService.COLOR_PALETTE
        color_objects: list[colors.Color] = []
        for idx, _value in enumerate(values):
            if idx < len(colors_chart):
                color_objects.append(colors.HexColor(colors_chart[idx]))
            else:
                color_objects.append(colors.HexColor(palette[idx % len(palette)]))
        return labels, values, color_objects

    @staticmethod
    def _create_pie_drawing(
        values: list[float], color_objects: list[colors.Color]
    ) -> tuple[Drawing, Pie]:
        drawing = Drawing(180, 180)
        pie = Pie()
        pie.width = 140
        pie.height = 140
        pie.x = 20
        pie.y = 20
        pie.data = values
        pie.labels = []
        pie.simpleLabels = False
        pie.slices.strokeWidth = 0.5
        pie.slices.strokeColor = colors.white

        for idx, _value in enumerate(values):
            pie.labels.append("")
            if idx < len(color_objects):
                pie.slices[idx].fillColor = color_objects[idx]

        drawing.add(pie)
        return drawing, pie

    @staticmethod
    def _create_pie_legend(
        labels: list[str],
        values: list[float],
        color_objects: list[colors.Color],
        total: float,
    ) -> Table:
        legend_label_style = ParagraphStyle("LegendLabel", fontSize=8, leading=10)
        legend_value_style = ParagraphStyle("LegendValue", fontSize=8, leading=10)
        legend_rows = []

        for idx, value in enumerate(values):
            label_text = labels[idx] if idx < len(labels) else f"Status {idx + 1}"
            color_box = Table(
                [[""]],
                colWidths=[6],
                rowHeights=[6],
                style=TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), color_objects[idx]),
                        ("BOX", (0, 0), (-1, -1), 0.25, colors.white),
                    ]
                ),
            )
            legend_rows.append(
                [
                    color_box,
                    Paragraph(
                        f'<font color="#111827"><b>{label_text}</b></font>',
                        legend_label_style,
                    ),
                    Paragraph(
                        f"{value} ({(value / total) * 100:.1f}%)",
                        legend_value_style,
                    ),
                ]
            )

        legend_table = Table(legend_rows, colWidths=[10, 55, 55])
        legend_table.setStyle(
            TableStyle(
                [
                    ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#374151")),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("LEFTPADDING", (0, 0), (-1, -1), 2),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                    ("TOPPADDING", (0, 0), (-1, -1), 1),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        return legend_table

    @staticmethod
    def _build_issues_table(issues_data: Dict[str, Any]) -> Table:
        header = ["Item", "Tipo", "Responsável", "Status", "Horas", "Custo"]
        itens = issues_data.get("itens") or []
        itens_ordenados = sorted(
            itens, key=lambda item: (float(item.get("custo") or 0.0)), reverse=True
        )
        linhas = []

        cell_style = ParagraphStyle(
            "IssuesCell",
            fontSize=9,
            leading=11,
            textColor=colors.HexColor("#111827"),
            wordWrap="LTR",
        )

        for item in itens_ordenados[:25]:
            linhas.append(
                [
                    Paragraph(item.get("id") or "-", cell_style),
                    Paragraph(
                        "Issue" if item.get("tipo") == "issue" else "Bug", cell_style
                    ),
                    Paragraph(
                        DashboardProjetoPdfService._truncate_text(
                            item.get("developer") or "Não atribuído", 32
                        ),
                        cell_style,
                    ),
                    Paragraph(
                        DashboardProjetoPdfService._truncate_text(
                            item.get("status") or DEFAULT_STATUS_LABEL, 22
                        ),
                        cell_style,
                    ),
                    f"{float(item.get('horas') or 0.0):.2f}h",
                    DashboardProjetoPdfService._format_currency(
                        float(item.get("custo") or 0.0)
                    ),
                ]
            )

        if not linhas:
            linhas.append(["Sem registros", "-", "-", "-", "-", "-"])

        tabela = Table(
            [header] + linhas,
            colWidths=[35 * mm, 20 * mm, 55 * mm, 30 * mm, 22 * mm, 30 * mm],
        )
        tabela.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111827")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 10),
                    ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                    ("ALIGN", (4, 1), (-1, -1), "RIGHT"),
                    ("ALIGN", (0, 1), (3, -1), "LEFT"),
                    ("VALIGN", (0, 1), (-1, -1), "MIDDLE"),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E5E7EB")),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [colors.white, colors.HexColor("#F9FAFB")],
                    ),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        return tabela

    @classmethod
    def gerar_pdf(cls, dados: Dict[str, Any]) -> bytes:
        buffer = BytesIO()
        documento = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=25 * mm,
            rightMargin=25 * mm,
            topMargin=20 * mm,
            bottomMargin=20 * mm,
        )

        styles = getSampleStyleSheet()
        titulo_style = ParagraphStyle(
            "Titulo",
            parent=styles["Title"],
            fontSize=18,
            textColor=colors.HexColor("#111827"),
            alignment=0,
            spaceAfter=12,
        )
        subtitulo_style = ParagraphStyle(
            "Subtitulo",
            parent=styles["Normal"],
            fontSize=11,
            textColor=colors.HexColor("#4B5563"),
            spaceAfter=12,
        )
        section_title_style = ParagraphStyle(
            "SectionTitle",
            parent=styles["Heading3"],
            fontSize=13,
            textColor=colors.HexColor("#1F2937"),
            spaceBefore=14,
            spaceAfter=8,
        )

        nome_projeto = dados.get("nome_projeto") or "Projeto sem nome"
        data_geracao = dados.get("data_geracao") or datetime.now()
        issues_data = (
            dados.get("issues_bugs") or IssuesBugsDashboardService.estrutura_vazia()
        )

        elementos = [
            Paragraph("Relatório – Dashboard de Custos", titulo_style),
            Paragraph(
                f"Projeto: <b>{nome_projeto}</b><br/>Gerado em: {data_geracao.strftime('%d/%m/%Y %H:%M')}",
                subtitulo_style,
            ),
            Paragraph("Visão Geral", section_title_style),
            cls._build_cards_table(dados),
            Spacer(1, 12),
            Paragraph("Custos por Desenvolvedor", section_title_style),
            cls._build_dev_table(dados),
            PageBreak(),
            Paragraph("Dashboard de Issues & Bugs", section_title_style),
            cls._build_issues_cards_table(issues_data),
            Spacer(1, 12),
            Paragraph("Distribuição por Status", section_title_style),
            cls._build_issues_pie_charts(issues_data, styles["Normal"]),
            Spacer(1, 12),
            Paragraph("Itens Detalhados", section_title_style),
            cls._build_issues_table(issues_data),
        ]

        documento.build(elementos)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes
