"""Serviços para o dashboard de projetos."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO
from typing import Any, Dict, Optional

from django.db import transaction
from django.db.models import Avg, Count, F, Max, Min, Sum
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from apps.relatorios.models import Projeto as ProjetoOLTP
from olap_models.models import DimProjeto, FatoRegistroHoras


class DashboardProjetoError(Exception):
    """Erro base para operações do dashboard de projetos."""


class OrcamentoInvalidoError(DashboardProjetoError):
    """Falha ao validar o orçamento previsto informado."""


class ProjetoNaoEncontradoError(DashboardProjetoError):
    """Projeto não encontrado no banco OLTP."""


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
        ]

        documento.build(elementos)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes
