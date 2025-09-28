import io
import json
from datetime import datetime
from django.db.models import Sum
from django.http import HttpResponse
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.graphics.shapes import Drawing, String, Rect
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.charts.barcharts import VerticalBarChart

from apps.relatorios.models import ControleHorasEquipe, TempoGastoEquipe, TempoControleValores, Projeto

class ComparacaoService:

    @staticmethod
    def _soma_horas_por_dev_mes_base(queryset, dev_field, mes_field, horas_field):
        resultado = {}
        for item in queryset:
            dev = item[dev_field]
            mes = item[mes_field]
            horas = item[horas_field] or 0
            resultado.setdefault(dev, {})[mes] = float(horas)
        return resultado

    @staticmethod
    def soma_horas_por_dev_mes(ano):
        queryset = (
            ControleHorasEquipe.objects
            .filter(mes__year=ano)
            .values("funcionario__nome", "mes__month")
            .annotate(total_horas=Sum("horas"))
            .order_by("funcionario__nome", "mes__month")
        )
        return ComparacaoService._soma_horas_por_dev_mes_base(
            queryset, "funcionario__nome", "mes__month", "total_horas"
        )

    @staticmethod
    def soma_horas_previstas_por_dev_mes(ano, *, source='tempo_controle_valores', field_name=None):
        if source == 'tempo_controle_valores':
            qs = (
                TempoControleValores.objects
                .filter(controle_tempo_equipe__mes__year=ano)
                .values(
                    "controle_tempo_equipe__funcionario__nome",
                    "controle_tempo_equipe__mes__month"
                )
                .annotate(total_previstas=Sum(field_name or "total_meta"))
                .order_by("controle_tempo_equipe__funcionario__nome", "controle_tempo_equipe__mes__month")
            )
            return ComparacaoService._soma_horas_por_dev_mes_base(
                qs, 
                "controle_tempo_equipe__funcionario__nome", 
                "controle_tempo_equipe__mes__month", 
                "total_previstas"
            )

        if source == 'tempo_gasto':
            qs = (
                TempoGastoEquipe.objects
                .filter(mes__year=ano)
                .values("funcionario__nome", "mes__month")
                .annotate(total_previstas=Sum(field_name or "tempo_gasto"))
                .order_by("funcionario__nome", "mes__month")
            )
            return ComparacaoService._soma_horas_por_dev_mes_base(
                qs, "funcionario__nome", "mes__month", "total_previstas"
            )

        raise RuntimeError("Fonte inválida para soma_horas_previstas_por_dev_mes. Use 'tempo_controle_valores' ou 'tempo_gasto'.")

    @staticmethod
    def _calcular_total_por_dev(dados_por_dev):
        return sum(sum(meses.values()) for meses in dados_por_dev.values()) if dados_por_dev else 0.0

    @staticmethod
    def totais_anuais_e_diferenca(ano):
        realizados = ComparacaoService.soma_horas_por_dev_mes(ano)
        previstos = ComparacaoService.soma_horas_previstas_por_dev_mes(ano)
        devs = set(list(realizados.keys()) + list(previstos.keys()))
        
        resumo = {}
        for dev in devs:
            total_real = ComparacaoService._calcular_total_por_dev({dev: realizados.get(dev, {})})
            total_prev = ComparacaoService._calcular_total_por_dev({dev: previstos.get(dev, {})})
            resumo[dev] = {
                'total_previsto': float(total_prev),
                'total_realizado': float(total_real),
                'diferenca': float(total_prev - total_real),
            }
        return resumo

    @staticmethod
    def get_nome_projetos() -> list[str]:
        qs = (
            Projeto.objects
            .values("nome")
            .order_by("nome")
        )
        return [item['nome'] for item in qs]

    @staticmethod
    def _preparar_dados_para_relatorio(ano):
        realizados = ComparacaoService.soma_horas_por_dev_mes(ano)
        previstos = ComparacaoService.soma_horas_previstas_por_dev_mes(ano)
        resumo = ComparacaoService.totais_anuais_e_diferenca(ano)

        por_dev = {}
        for dev in sorted(set(list(realizados.keys()) + list(previstos.keys()))):
            meses = {}
            for m in range(1, 13):
                meses[m] = {
                    "previsto": float(previstos.get(dev, {}).get(m, 0.0)),
                    "realizado": float(realizados.get(dev, {}).get(m, 0.0)),
                }
            por_dev[dev] = {
                "mensal": meses,
                "totais": resumo.get(
                    dev,
                    {"total_previsto": 0.0, "total_realizado": 0.0, "diferenca": 0.0},
                ),
            }

        return {"ano": ano, "por_dev": por_dev}

    @staticmethod
    def exportar_relatorio_pdf(ano: int, projeto_nome: str, horas_planejadas: float) -> HttpResponse:
        current_data = ComparacaoService._preparar_dados_para_relatorio(ano)
        
        buffer = ComparacaoService._gerar_pdf(current_data, horas_planejadas, projeto_nome, ano)
        
        response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
        filename = f"relatorio_horas_{projeto_nome.replace(' ', '_')}_{ano}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response

    @staticmethod
    def _criar_estilo_titulo(styles):
        return ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            spaceAfter=20,
            alignment=1,
            textColor=colors.HexColor('#0057B8')
        )

    @staticmethod
    def _criar_estilo_data(styles):
        return ParagraphStyle(
            'DateStyle',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.gray,
            alignment=2
        )

    @staticmethod
    def _gerar_pdf(current_data: dict, total_planned_hours: float, project_name: str, year: int) -> io.BytesIO:
        buffer = io.BytesIO()
        
        doc = SimpleDocTemplate(
            buffer,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36,
            pagesize=A4
        )
        
        elements = []
        styles = getSampleStyleSheet()
        
        title_style = ComparacaoService._criar_estilo_titulo(styles)
        title = Paragraph(f"Relatório de Horas - {project_name} ({year})", title_style)
        elements.append(title)
        
        elements.extend(ComparacaoService._criar_cards_resumo(current_data, total_planned_hours))
        elements.append(Spacer(1, 25))
        
        tabela_elements = ComparacaoService._criar_tabela_comparacao(current_data, styles)
        
        if tabela_elements:
            elements.append(Paragraph("Detalhamento por Colaborador", styles['Heading2']))
            elements.append(Spacer(1, 10))
            elements.extend(tabela_elements)
            elements.append(Spacer(1, 25))
        
        elements.append(PageBreak())
        elements.extend(ComparacaoService._criar_graficos(current_data, styles))
        
        date_style = ComparacaoService._criar_estilo_data(styles)
        elements.append(Spacer(1, 15))
        elements.append(Paragraph(f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}", date_style))
        
        doc.build(elements)
        buffer.seek(0)
        return buffer

    @staticmethod
    def _calcular_totais_resumo(current_data):
        if not current_data.get('por_dev'):
            return 0, 0
        
        collaborators_count = len(current_data['por_dev'])
        total_realized = sum(dev['totais']['total_realizado'] for dev in current_data['por_dev'].values())
        return total_realized, collaborators_count

    @staticmethod
    def _criar_cards_resumo(current_data: dict, total_planned_hours: float) -> list:
        from reportlab.platypus import Table, TableStyle
        
        total_realized, collaborators_count = ComparacaoService._calcular_totais_resumo(current_data)
        
        performance_percentage = (total_realized / total_planned_hours * 100) if total_planned_hours > 0 else 0
        deficit = total_planned_hours - total_realized
        
        card1 = ComparacaoService._criar_card_individual(
            "Performance Geral", 
            f'{performance_percentage:.1f}%', 
            "Meta de eficiência atingida",
            colors.HexColor('#0057B8')
        )
        
        card2 = ComparacaoService._criar_card_individual(
            "Total Realizado", 
            f'{total_realized:.2f}h', 
            "Horas trabalhadas no período",
            colors.HexColor('#00C49F'),
            f'{collaborators_count} colaboradores'
        )
        
        card3 = ComparacaoService._criar_card_individual(
            "Meta Planejada", 
            f'{total_planned_hours:.2f}h', 
            "Horas planejadas para o período",
            colors.HexColor('#EA580C'),
            f'Déficit: {deficit:.2f}h'
        )
        
        card_table_data = [[card1, card2, card3]]
        
        width = A4[0] - 72
        card_width = width / 3
        
        card_table = Table(card_table_data, colWidths=[card_width] * 3)
        card_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('PADDING', (0, 0), (-1, -1), 5),
        ]))
        
        return [card_table]

    @staticmethod
    def _criar_card_individual(titulo: str, valor: str, descricao: str, cor: colors.Color, info_extra: str = None) -> Table:
        from reportlab.platypus import Table, TableStyle
        
        card_data = [
            [titulo],
            [valor],
            [descricao]
        ]
        
        if info_extra:
            card_data.append([info_extra])
        
        card_table = Table(card_data)
        
        table_style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), cor),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTSIZE', (0, 1), (-1, 1), 14),
            ('FONTSIZE', (0, 2), (-1, -1), 8),
            ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 1), (-1, 1), 6),
            ('BOTTOMPADDING', (0, 2), (-1, -1), 4),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F8FAFC')),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#E2E8F0')),
        ])
        
        if info_extra:
            table_style.add('FONTNAME', (0, 3), (-1, 3), 'Helvetica-Bold')
            table_style.add('FONTSIZE', (0, 3), (-1, 3), 8)
            table_style.add('TEXTCOLOR', (0, 3), (-1, 3), cor)
            table_style.add('BACKGROUND', (0, 3), (-1, 3), colors.HexColor('#F0FDF4'))
        
        card_table.setStyle(table_style)
        return card_table

    @staticmethod
    def _criar_tabela_comparacao(current_data: dict, styles) -> list:
        elements = []
        
        if not current_data.get('por_dev'):
            return elements
        
        meses = ['JAN', 'FEV', 'MAR', 'ABR', 'MAI', 'JUN', 'JUL', 'AGO', 'SET', 'OUT', 'NOV', 'DEZ']
        header = ['Colaborador'] + meses
        
        table_data = [header]
        
        for dev_name, dev_data in current_data['por_dev'].items():
            row = [dev_name]
            for month in range(1, 13):
                realized = dev_data['mensal'][month]['realizado']
                row.append(f'{realized:.1f}h' if realized > 0 else '-')
            table_data.append(row)
        
        total_row = ['TOTAL GERAL']
        for month in range(1, 13):
            month_total = sum(dev_data['mensal'][month]['realizado'] 
                            for dev_data in current_data['por_dev'].values())
            total_row.append(f'{month_total:.1f}h' if month_total > 0 else '-')
        table_data.append(total_row)
        
        from reportlab.platypus import Table
        
        available_width = A4[0] - 72
        first_col_width = available_width * 0.2
        month_col_width = (available_width - first_col_width) / 12
        
        col_widths = [first_col_width] + [month_col_width] * 12
        
        table = Table(table_data, colWidths=col_widths, repeatRows=1)
        
        table_style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0057B8')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('FONTSIZE', (0, 1), (-1, -1), 7),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('BACKGROUND', (0, 1), (-1, -2), colors.white),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#F3F4F6')),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#F8FAFC')]),
        ])
        
        table.setStyle(table_style)
        elements.append(table)
        
        return elements

    @staticmethod
    def _criar_estilo_titulo_grafico(styles, font_size=12):
        return ParagraphStyle(
            'ChartsTitle',
            parent=styles['Heading3'],
            fontSize=font_size,
            spaceAfter=8,
            alignment=1,
            textColor=colors.HexColor('#1F2937')
        )

    @staticmethod
    def _criar_graficos(current_data: dict, styles) -> list:
        from reportlab.platypus import Spacer, Table, TableStyle
        elements = []
        
        if not current_data.get('por_dev'):
            return elements
        
        elements.append(Spacer(1, 20))
        title_style = ComparacaoService._criar_estilo_titulo_grafico(styles, 14)
        title = Paragraph("Análise Gráfica", title_style)
        elements.append(title)
        
        pie_chart = ComparacaoService._criar_grafico_pizza(current_data)
        if pie_chart:
            titulo_pizza_style = ComparacaoService._criar_estilo_titulo_grafico(styles, 12)
            titulo_pizza = Paragraph("Distribuição de Horas por Colaborador", titulo_pizza_style)
            elements.append(titulo_pizza)
            
            pie_container = Table([[pie_chart]], colWidths=[A4[0] - 72])
            pie_container.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            elements.append(pie_container)
            elements.append(Spacer(1, 25))
        
        bar_chart = ComparacaoService._criar_grafico_barras(current_data)
        if bar_chart:
            titulo_barras_style = ComparacaoService._criar_estilo_titulo_grafico(styles, 12)
            titulo_barras = Paragraph("Comparação Total de Horas", titulo_barras_style)
            elements.append(titulo_barras)
            
            bar_container = Table([[bar_chart]], colWidths=[A4[0] - 72])
            bar_container.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            elements.append(bar_container)
        
        elements.append(Spacer(1, 20))
        return elements

    @staticmethod
    def _criar_grafico_pizza(current_data: dict):
        try:
            collaborators_data = []
            for dev_name, dev_data in current_data['por_dev'].items():
                total_realized = dev_data['totais']['total_realizado']
                if total_realized > 0:
                    collaborators_data.append((dev_name, total_realized))
            
            if not collaborators_data:
                return None
            
            collaborators_data.sort(key=lambda x: x[1], reverse=True)
            labels = [data[0] for data in collaborators_data]
            data_values = [data[1] for data in collaborators_data]
            
            drawing = Drawing(400, 280)
            pie = Pie()
            
            pie.x = 100
            pie.y = 40
            pie.width = 200
            pie.height = 200
            
            pie.data = data_values
            pie.labels = labels
            pie.sideLabels = True
            pie.simpleLabels = False
            
            for i in range(len(labels)):
                if len(labels[i]) > 12:
                    pie.labels[i] = labels[i][:10] + ".."
            
            colors_list = [
                colors.HexColor('#0057B8'), colors.HexColor('#00C49F'), 
                colors.HexColor('#FFBB28'), colors.HexColor('#FF8042'),
                colors.HexColor('#AF19FF'), colors.HexColor('#8884d8'),
                colors.HexColor('#FF6384'), colors.HexColor('#36A2EB'),
                colors.HexColor('#4BC0C0'), colors.HexColor('#FFCE56')
            ]
            
            for i in range(len(data_values)):
                pie.slices[i].fillColor = colors_list[i % len(colors_list)]
                pie.slices[i].strokeColor = colors.white
                pie.slices[i].strokeWidth = 1
            
            drawing.add(pie)
            return drawing
            
        except Exception as e:
            print(f"Erro ao criar gráfico de pizza: {e}")
            return None

    @staticmethod
    def _criar_grafico_barras(current_data: dict):
        try:
            total_realized = sum(dev['totais']['total_realizado'] for dev in current_data['por_dev'].values())
            total_planned = sum(dev['totais']['total_previsto'] for dev in current_data['por_dev'].values())
            
            drawing = Drawing(400, 220)
            
            chart = VerticalBarChart()
            chart.x = 80
            chart.y = 40
            chart.width = 240
            chart.height = 130
            
            chart.data = [[total_realized], [total_planned]]
            chart.categoryAxis.categoryNames = ['']
            chart.valueAxis.valueMin = 0
            max_value = max(total_realized, total_planned)
            chart.valueAxis.valueMax = max_value * 1.4
            
            chart.bars[0].fillColor = colors.HexColor('#0057B8')
            chart.bars[1].fillColor = colors.HexColor('#EA580C')
            
            chart.barWidth = 45
            chart.barSpacing = 15
            chart.groupSpacing = 80
            
            chart.valueAxis.labels.fontName = 'Helvetica'
            chart.valueAxis.labels.fontSize = 8
            chart.categoryAxis.visible = False
            
            label_realizado_y = chart.y + total_realized + 12
            label_previsto_y = chart.y + total_planned + 12
            
            label_realizado = String(chart.x + 35, label_realizado_y, 
                                   f'{total_realized:.1f}h', 
                                   fontName='Helvetica-Bold', fontSize=9, 
                                   fillColor=colors.HexColor('#0057B8'))
            
            label_previsto = String(chart.x + 135, label_previsto_y, 
                                  f'{total_planned:.1f}h', 
                                  fontName='Helvetica-Bold', fontSize=9, 
                                  fillColor=colors.HexColor('#EA580C'))
            
            legenda_y = chart.y - 20
            
            legenda_realizado_x = chart.x + 20
            legenda_realizado = String(legenda_realizado_x, legenda_y, 
                                     'Realizadas', 
                                     fontName='Helvetica-Bold', fontSize=8, 
                                     fillColor=colors.HexColor('#0057B8'))
            
            legenda_previsto_x = chart.x + 160
            legenda_previsto = String(legenda_previsto_x, legenda_y, 
                                    'Previstas', 
                                    fontName='Helvetica-Bold', fontSize=8, 
                                    fillColor=colors.HexColor('#EA580C'))
            
            indicador_realizado = Rect(legenda_realizado_x - 12, legenda_y - 3, 8, 8, 
                                     fillColor=colors.HexColor('#0057B8'),
                                     strokeColor=colors.black, strokeWidth=0.5)
            
            indicador_previsto = Rect(legenda_previsto_x - 12, legenda_y - 3, 8, 8, 
                                    fillColor=colors.HexColor('#EA580C'),
                                    strokeColor=colors.black, strokeWidth=0.5)
            
            drawing.add(chart)
            drawing.add(label_realizado)
            drawing.add(label_previsto)
            drawing.add(legenda_realizado)
            drawing.add(legenda_previsto)
            drawing.add(indicador_realizado)
            drawing.add(indicador_previsto)
            
            return drawing
            
        except Exception as e:
            print(f"Erro ao criar gráfico de barras: {e}")
            return None