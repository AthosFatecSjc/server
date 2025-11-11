"""Serviços para geração de relatórios de comparação."""

import io
from datetime import datetime

from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from apps.relatorios.models import Issue, PlanejamentoProjeto, Projeto


class ComparacaoService:
    """Serviços para geração de relatórios de comparação."""

    @staticmethod
    def _processar_queryset_horas(queryset, campos, *, divisor: float | None = None):
        resultado = {}
        for item in queryset:
            dev = item[campos["dev"]]
            mes = item[campos["mes"]]
            horas = item[campos["horas"]] or 0
            valor = float(horas)
            if divisor:
                valor /= divisor
            resultado.setdefault(dev, {})[mes] = valor
        return resultado

    @staticmethod
    def soma_horas_por_dev_mes(ano: int, nome_projeto: str = None) -> dict:
        """
        Soma as horas do mês de cada dev naquele projeto

        Args:
            ano (int): Ano para geração do relatório.
            nome_projeto (str): Nome do projeto.

        Returns:
            soma_horas_por_dev_mes (dict): Soma de horas por mês do dev no projet/ ano.
        """

        queryset = Issue.objects.filter(
            criado_em__year=ano, criado_em__isnull=False
        ).exclude(funcionario__isnull=True)

        if nome_projeto:
            queryset = queryset.filter(projeto__nome=nome_projeto)

        queryset = (
            queryset.values("funcionario__nome", "criado_em__month")
            .annotate(total_segundos=Sum(Coalesce("tempo_gasto_seconds", 0)))
            .order_by("funcionario__nome", "criado_em__month")
        )

        return ComparacaoService._processar_queryset_horas(
            queryset,
            {
                "dev": "funcionario__nome",
                "mes": "criado_em__month",
                "horas": "total_segundos",
            },
            divisor=3600,
        )

    @staticmethod
    def soma_horas_previstas_por_dev_mes(ano: int, nome_projeto: str | None = None):
        """
        Soma as horas estimadas das issues por desenvolvedor e mês.
        Usa a estimativa registrada na issue (tempo_estimado_seconds).
        """
        queryset = Issue.objects.filter(
            criado_em__year=ano, criado_em__isnull=False
        ).exclude(funcionario__isnull=True)

        if nome_projeto:
            queryset = queryset.filter(projeto__nome=nome_projeto)

        queryset = (
            queryset.values("funcionario__nome", "criado_em__month")
            .annotate(total_segundos=Sum(Coalesce("tempo_estimado_seconds", 0)))
            .order_by("funcionario__nome", "criado_em__month")
        )

        return ComparacaoService._processar_queryset_horas(
            queryset,
            {
                "dev": "funcionario__nome",
                "mes": "criado_em__month",
                "horas": "total_segundos",
            },
            divisor=3600,
        )

    @staticmethod
    def _calcular_soma_valores(dicionario):
        return (
            sum(sum(meses.values()) for meses in dicionario.values())
            if dicionario
            else 0.0
        )

    @staticmethod
    def totais_anuais_e_diferenca(ano, nome_projeto=None):
        """Calcula totais anuais e diferença entre previsto e realizado."""
        realizados = ComparacaoService.soma_horas_por_dev_mes(ano, nome_projeto)
        previstos = ComparacaoService.soma_horas_previstas_por_dev_mes(
            ano, nome_projeto
        )
        devs = set(list(realizados.keys()) + list(previstos.keys()))

        return {
            dev: {
                "total_previsto": float(
                    ComparacaoService._calcular_soma_valores(
                        {dev: previstos.get(dev, {})}
                    )
                ),
                "total_realizado": float(
                    ComparacaoService._calcular_soma_valores(
                        {dev: realizados.get(dev, {})}
                    )
                ),
                "diferenca": float(
                    ComparacaoService._calcular_soma_valores(
                        {dev: previstos.get(dev, {})}
                    )
                    - ComparacaoService._calcular_soma_valores(
                        {dev: realizados.get(dev, {})}
                    )
                ),
            }
            for dev in devs
        }

    @staticmethod
    def get_nome_projetos() -> list[str]:
        """Retorna a lista de nomes de projetos ordenados."""
        return list(Projeto.objects.values_list("nome", flat=True).order_by("nome"))

    @staticmethod
    def _criar_estilo_padrao(nome, parent, **kwargs):
        return ParagraphStyle(nome, parent=parent, **kwargs)

    @staticmethod
    def _criar_container_tabela(elemento, largura_total):

        container = Table([[elemento]], colWidths=[largura_total])
        container.setStyle(
            TableStyle(
                [
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        return container

    @staticmethod
    def exportar_relatorio_pdf(
        ano: int, projeto_nome: str, horas_planejadas: float
    ) -> HttpResponse:
        """Exporta o relatório de comparação em PDF."""
        current_data = ComparacaoService._preparar_dados_para_relatorio(
            ano, projeto_nome
        )
        buffer = ComparacaoService._gerar_pdf(
            current_data, horas_planejadas, projeto_nome, ano
        )

        response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
        filename = f"""relatorio_horas_{
            projeto_nome.replace(
                ' ', '_')}_{ano}.pdf"""
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    @staticmethod
    def _preparar_dados_para_relatorio(ano, nome_projeto=None):
        realizados = ComparacaoService.soma_horas_por_dev_mes(ano, nome_projeto)
        previstos = ComparacaoService.soma_horas_previstas_por_dev_mes(
            ano, nome_projeto
        )
        resumo = ComparacaoService.totais_anuais_e_diferenca(ano, nome_projeto)

        return {
            "ano": ano,
            "por_dev": {
                dev: {
                    "mensal": {
                        m: {
                            "previsto": float(previstos.get(dev, {}).get(m, 0.0)),
                            "realizado": float(realizados.get(dev, {}).get(m, 0.0)),
                        }
                        for m in range(1, 13)
                    },
                    "totais": resumo.get(
                        dev,
                        {
                            "total_previsto": 0.0,
                            "total_realizado": 0.0,
                            "diferenca": 0.0,
                        },
                    ),
                }
                for dev in sorted(set(list(realizados.keys()) + list(previstos.keys())))
            },
        }

    @staticmethod
    def _gerar_pdf(
        current_data: dict, total_planned_hours: float, project_name: str, year: int
    ) -> io.BytesIO:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36,
            pagesize=A4,
        )
        elements = []
        styles = getSampleStyleSheet()

        title_style = ComparacaoService._criar_estilo_padrao(
            "CustomTitle",
            styles["Heading1"],
            fontSize=16,
            spaceAfter=20,
            alignment=1,
            textColor=colors.HexColor("#0057B8"),
        )
        elements.append(
            Paragraph(f"Relatório de Horas - {project_name} ({year})", title_style)
        )

        elements.extend(
            ComparacaoService._criar_cards_resumo(current_data, total_planned_hours)
        )
        elements.append(Spacer(1, 25))

        tabela_elements = ComparacaoService._criar_tabela_comparacao(current_data)
        if tabela_elements:
            elements.append(
                Paragraph("Detalhamento por Colaborador", styles["Heading2"])
            )
            elements.append(Spacer(1, 10))
            elements.extend(tabela_elements)
            elements.append(Spacer(1, 25))

        elements.append(PageBreak())

        elements.extend(
            ComparacaoService._criar_secao_graficos(
                current_data, total_planned_hours, styles
            )
        )

        date_style = ComparacaoService._criar_estilo_padrao(
            "DateStyle",
            styles["Normal"],
            fontSize=8,
            textColor=colors.gray,
            alignment=2,
        )
        elements.append(Spacer(1, 15))
        elements.append(
            Paragraph(
                f"""Gerado em: {
                    datetime.now().strftime('%d/%m/%Y %H:%M')}""",
                date_style,
            )
        )

        doc.build(elements)
        buffer.seek(0)
        return buffer

    @staticmethod
    def _criar_cards_resumo(current_data: dict, total_planned_hours: float) -> list:

        total_realized, collaborators_count = ComparacaoService._obter_metricas_resumo(
            current_data
        )
        performance_percentage = (
            (total_realized / total_planned_hours * 100)
            if total_planned_hours > 0
            else 0
        )
        deficit = total_planned_hours - total_realized

        cards_config = [
            (
                "Performance Geral",
                f"{performance_percentage:.1f}%",
                "Meta de eficiência atingida",
                colors.HexColor("#0057B8"),
                None,
            ),
            (
                "Total Realizado",
                f"{total_realized:.2f}h",
                "Horas trabalhadas no período",
                colors.HexColor("#00C49F"),
                f"{collaborators_count} colaboradores",
            ),
            (
                "Meta Planejada",
                f"{total_planned_hours:.2f}h",
                "Horas planejadas para o período",
                colors.HexColor("#EA580C"),
                f"Déficit: {deficit:.2f}h",
            ),
        ]

        cards = [
            ComparacaoService._criar_card_individual(*config) for config in cards_config
        ]
        card_table = Table([cards], colWidths=[(A4[0] - 72) / 3] * 3)
        card_table.setStyle(
            TableStyle(
                [
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("PADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )

        return [card_table]

    @staticmethod
    def _obter_metricas_resumo(current_data):
        if not current_data.get("por_dev"):
            return 0, 0
        return (
            sum(
                dev["totais"]["total_realizado"]
                for dev in current_data["por_dev"].values()
            ),
            len(current_data["por_dev"]),
        )

    @staticmethod
    def _criar_card_individual(
        titulo: str,
        valor: str,
        descricao: str,
        cor: colors.Color,
        info_extra: str = None,
    ) -> Table:

        card_data = [[titulo], [valor], [descricao]]
        if info_extra:
            card_data.append([info_extra])

        card_table = Table(card_data)
        estilo_base = [
            ("BACKGROUND", (0, 0), (-1, 0), cor),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 10),
            ("FONTSIZE", (0, 1), (-1, 1), 14),
            ("FONTSIZE", (0, 2), (-1, -1), 8),
            ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 10),
            ("BOTTOMPADDING", (0, 1), (-1, 1), 6),
            ("BOTTOMPADDING", (0, 2), (-1, -1), 4),
            ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F8FAFC")),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#E2E8F0")),
        ]

        if info_extra:
            estilo_base.extend(
                [
                    ("FONTNAME", (0, 3), (-1, 3), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 3), (-1, 3), 8),
                    ("TEXTCOLOR", (0, 3), (-1, 3), cor),
                    ("BACKGROUND", (0, 3), (-1, 3), colors.HexColor("#F0FDF4")),
                ]
            )

        card_table.setStyle(TableStyle(estilo_base))
        return card_table

    @staticmethod
    def _criar_tabela_comparacao(current_data: dict) -> list:
        if not current_data.get("por_dev"):
            return []

        meses = [
            "JAN",
            "FEV",
            "MAR",
            "ABR",
            "MAI",
            "JUN",
            "JUL",
            "AGO",
            "SET",
            "OUT",
            "NOV",
            "DEZ",
        ]
        header = ["Colaborador"] + meses

        table_data = [header]
        for dev_name, dev_data in current_data["por_dev"].items():
            row = [dev_name] + [
                (
                    f"{dev_data['mensal'][m]['realizado']:.1f}h"
                    if dev_data["mensal"][m]["realizado"] > 0
                    else "-"
                )
                for m in range(1, 13)
            ]
            table_data.append(row)

        totais_mensais = [
            sum(
                dev_data["mensal"][m]["realizado"]
                for dev_data in current_data["por_dev"].values()
            )
            for m in range(1, 13)
        ]
        table_data.append(
            ["TOTAL GERAL"]
            + [f"{total:.1f}h" if total > 0 else "-" for total in totais_mensais]
        )

        available_width = A4[0] - 72
        col_widths = [available_width * 0.2] + [(available_width * 0.8) / 12] * 12

        table = Table(table_data, colWidths=col_widths, repeatRows=1)
        table.setStyle(ComparacaoService._obter_estilo_tabela())
        return [table]

    @staticmethod
    def _obter_estilo_tabela():
        return TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0057B8")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 8),
                ("FONTSIZE", (0, 1), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                ("BACKGROUND", (0, 1), (-1, -2), colors.white),
                ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#F3F4F6")),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -2),
                    [colors.white, colors.HexColor("#F8FAFC")],
                ),
            ]
        )

    @staticmethod
    def _criar_secao_graficos(
        current_data: dict, total_planned_hours: float, styles
    ) -> list:
        if not current_data.get("por_dev"):
            return []

        elements = [Spacer(1, 20)]

        title_style = ComparacaoService._criar_estilo_padrao(
            "ChartsTitle",
            styles["Heading2"],
            fontSize=14,
            spaceAfter=20,
            textColor=colors.HexColor("#1F2937"),
            alignment=1,
        )
        elements.append(Paragraph("Análise Gráfica", title_style))

        pie_chart = ComparacaoService._criar_grafico_pizza(current_data)
        if pie_chart:
            elements.extend(
                ComparacaoService._criar_subsecao_grafico(
                    "Distribuição de Horas por Colaborador", pie_chart, styles
                )
            )

        bar_chart = ComparacaoService._criar_grafico_barras(
            current_data, total_planned_hours
        )
        if bar_chart:
            elements.extend(
                ComparacaoService._criar_subsecao_grafico(
                    "Comparação Total de Horas", bar_chart, styles
                )
            )

        elements.append(Spacer(1, 20))
        return elements

    @staticmethod
    def _criar_subsecao_grafico(titulo: str, grafico, styles):
        elements = []
        titulo_style = ComparacaoService._criar_estilo_padrao(
            "GraphSubtitle",
            styles["Heading3"],
            fontSize=12,
            spaceAfter=8,
            alignment=1,
            textColor=colors.HexColor("#1F2937"),
        )
        elements.append(Paragraph(titulo, titulo_style))
        elements.append(ComparacaoService._criar_container_tabela(grafico, A4[0] - 72))
        elements.append(Spacer(1, 25))
        return elements

    @staticmethod
    def _criar_grafico_pizza(current_data: dict):
        try:
            collaborators_data = [
                (dev_name, dev_data["totais"]["total_realizado"])
                for dev_name, dev_data in current_data["por_dev"].items()
                if dev_data["totais"]["total_realizado"] > 0
            ]

            if not collaborators_data:
                return None

            collaborators_data.sort(key=lambda x: x[1], reverse=True)

            labels = [data[0] for data in collaborators_data]
            data_values = [data[1] for data in collaborators_data]

            total_horas = sum(data_values)

            formatted_labels = []
            for label in labels:
                parts = label.split()
                if len(parts) >= 2:
                    formatted_label = f"{parts[0]} {parts[1][0]}."
                    if len(parts) > 2:
                        formatted_label += f" {parts[2][0]}."
                else:
                    formatted_label = label[:10]
                formatted_labels.append(formatted_label)

            drawing = Drawing(450, 320)
            pie = Pie()
            pie.x = 80
            pie.y = 40
            pie.width = 160
            pie.height = 160
            pie.data = data_values
            pie.labels = formatted_labels
            pie.sideLabels = True
            pie.simpleLabels = False

            colors_list = [
                colors.HexColor("#0057B8"),
                colors.HexColor("#00C49F"),
                colors.HexColor("#FFBB28"),
                colors.HexColor("#FF8042"),
                colors.HexColor("#AF19FF"),
                colors.HexColor("#8884d8"),
                colors.HexColor("#FF6384"),
                colors.HexColor("#36A2EB"),
                colors.HexColor("#4BC0C0"),
                colors.HexColor("#FFCE56"),
                colors.HexColor("#FF6B6B"),
            ]

            for i in range(len(data_values)):
                pie.slices[i].fillColor = colors_list[i % len(colors_list)]
                pie.slices[i].strokeColor = colors.white
                pie.slices[i].strokeWidth = 1

            drawing.add(pie)

            legend_x = 320
            legend_y = 280

            drawing.add(
                String(
                    legend_x,
                    legend_y,
                    "Colaboradores:",
                    fontName="Helvetica-Bold",
                    fontSize=8,
                    fillColor=colors.black,
                    textAnchor="start",
                )
            )

            for i, (label, valor) in enumerate(zip(labels, data_values)):
                porcentagem = (valor / total_horas) * 100 if total_horas > 0 else 0

                legend_text = f"{label} ({porcentagem:.1f}%)"

                drawing.add(
                    String(
                        legend_x,
                        legend_y - (i * 18) - 20,
                        legend_text,
                        fontName="Helvetica",
                        fontSize=6,
                        fillColor=colors_list[i % len(colors_list)],
                        textAnchor="start",
                    )
                )

            drawing.add(
                String(
                    225,
                    15,
                    f"Total: {total_horas:.1f}h",
                    fontName="Helvetica-Bold",
                    fontSize=9,
                    fillColor=colors.black,
                    textAnchor="middle",
                )
            )

            return drawing

        except Exception as e:
            print(f"Erro ao criar gráfico de pizza: {e}")
            return None

    @staticmethod
    def _criar_grafico_barras(current_data: dict, total_planned_hours: float):
        try:
            total_realized = sum(
                dev["totais"]["total_realizado"]
                for dev in current_data["por_dev"].values()
            )

            total_planned = total_planned_hours

            drawing = Drawing(400, 220)
            chart = VerticalBarChart()

            chart.x, chart.y, chart.width, chart.height = 80, 40, 240, 130

            chart.data = [[total_realized], [total_planned]]
            chart.categoryAxis.categoryNames = [""]

            max_value = max(total_realized, total_planned)
            chart.valueAxis.valueMin = 0
            chart.valueAxis.valueMax = max_value * 1.2

            chart.bars[0].fillColor = colors.HexColor("#0057B8")
            chart.bars[1].fillColor = colors.HexColor("#EA580C")

            chart.barWidth = 45
            chart.barSpacing = 15
            chart.groupSpacing = 80

            chart.valueAxis.labels.fontName = "Helvetica"
            chart.valueAxis.labels.fontSize = 8
            chart.categoryAxis.visible = False

            drawing.add(chart)

            legenda_y = chart.y - 20
            texto_y = legenda_y - 15

            drawing.add(
                String(
                    chart.x + 35,
                    texto_y,
                    f"{total_realized:.0f}h",
                    fontName="Helvetica-Bold",
                    fontSize=9,
                    fillColor=colors.HexColor("#0057B8"),
                )
            )

            drawing.add(
                String(
                    chart.x + 135,
                    texto_y,
                    f"{total_planned:.0f}h",
                    fontName="Helvetica-Bold",
                    fontSize=9,
                    fillColor=colors.HexColor("#EA580C"),
                )
            )

            drawing.add(
                String(
                    chart.x + 20,
                    legenda_y,
                    "Realizadas",
                    fontName="Helvetica-Bold",
                    fontSize=8,
                    fillColor=colors.HexColor("#0057B8"),
                )
            )
            drawing.add(
                String(
                    chart.x + 160,
                    legenda_y,
                    "Previstas",
                    fontName="Helvetica-Bold",
                    fontSize=8,
                    fillColor=colors.HexColor("#EA580C"),
                )
            )

            drawing.add(
                Rect(
                    chart.x + 8,
                    legenda_y - 3,
                    8,
                    8,
                    fillColor=colors.HexColor("#0057B8"),
                    strokeColor=colors.black,
                    strokeWidth=0.5,
                )
            )
            drawing.add(
                Rect(
                    chart.x + 148,
                    legenda_y - 3,
                    8,
                    8,
                    fillColor=colors.HexColor("#EA580C"),
                    strokeColor=colors.black,
                    strokeWidth=0.5,
                )
            )

            return drawing

        except Exception as e:
            print(f"Erro ao criar gráfico de barras: {e}")
            return None

    @staticmethod
    def _get_projeto(nome_projeto: str) -> Projeto | None:
        """Recupera uma instância de Projeto a partir do nome informado."""
        if not nome_projeto:
            return None
        return Projeto.objects.filter(nome=nome_projeto).first()

    @staticmethod
    def get_horas_previstas_projeto(ano: int, nome_projeto: str) -> float:
        """
        Lê registro de horas previstas para o projeto especificado.
        Os valores agora são persistidos em PlanejamentoProjeto.
        """
        projeto = ComparacaoService._get_projeto(nome_projeto)
        if not projeto:
            return 0.0

        registro = PlanejamentoProjeto.objects.filter(projeto=projeto, ano=ano).first()
        return float(registro.horas_previstas) if registro else 0.0

    @staticmethod
    def set_horas_previstas_projeto(
        nome_projeto: str, ano: int, horas_previstas: float
    ) -> HttpResponse | Exception:
        """
        Inclui registro de horas previstas para o projeto especificado

        Args:
            nome_projeto (str): Nome do projeto.
            ano (int): Ano para geração do relatório.
            horas_previstas (float): Quantidade de horas previstas para o ano em questão.

        Returns:
            Status_da_escrita (HttpResponse | Exception): Falha ou sucesso ao escreve no banco.
        """

        try:
            projeto = ComparacaoService._get_projeto(nome_projeto)
            if not projeto:
                raise ValueError("Projeto não encontrado para salvar horas previstas.")

            PlanejamentoProjeto.objects.update_or_create(
                projeto=projeto,
                ano=ano,
                defaults={"horas_previstas": horas_previstas},
            )
            return HttpResponse()

        except Exception as e:
            print(f"Erro ao atualizar meta: {e}")
            return e
