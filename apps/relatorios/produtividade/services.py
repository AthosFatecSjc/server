from django.db.models import Sum
from apps.relatorios.models import TempoGastoEquipe, Funcionario
from io import BytesIO
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from django.http import HttpResponse
from datetime import datetime

def calcular_spends_por_dev(mes, ano):
    funcionarios = Funcionario.objects.all()
    resultados = []

    total_real = 0.0
    total_meta = 0.0
    soma_diaria_total = {d: 0.0 for d in range(1, 32)}

    for func in funcionarios:
        registros = TempoGastoEquipe.objects.filter(
            funcionario=func,
            mes__month=mes,
            mes__year=ano
        ).values('dia_mes').annotate(total_horas=Sum('tempo_gasto'))

        dias_por_func = {}
        for r in registros:
            dia = r['dia_mes']
            horas_dia = float(r['total_horas'])
            dias_por_func[dia] = round(horas_dia, 1)
            soma_diaria_total[dia] += horas_dia

        for d in range(1, 32):
            if d not in dias_por_func:
                dias_por_func[d] = 0.0

        horas_real = sum(dias_por_func.values())
        meta = 154.0
        percentual = (horas_real / meta * 100) if meta > 0 else 0

        resultados.append({
            "funcionario": func.nome,
            "dias": dias_por_func,
            "real": round(horas_real, 1),
            "meta": meta,
            "percentual": round(percentual, 1)
        })

        total_real += horas_real
        total_meta += meta

    percentual_total = (total_real / total_meta * 100) if total_meta > 0 else 0
    
    soma_diaria_total_arredondada = {dia: round(valor, 1) for dia, valor in soma_diaria_total.items()}
    
    resultados.append({
        "funcionario": "REALIZADO",
        "dias": soma_diaria_total_arredondada,
        "real": round(total_real, 1),
        "meta": total_meta,
        "percentual": round(percentual_total, 1)
    })

    return resultados

def exportar_produtividade_pdf(mes, ano, resultados):
    MESES_PORTUGUES = {
        1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril',
        5: 'Maio', 6: 'Junho', 7: 'Julho', 8: 'Agosto',
        9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'
    }
    
    from reportlab.lib.pagesizes import legal
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(legal),
                           leftMargin=0.2*inch,
                           rightMargin=0.2*inch,
                           topMargin=0.3*inch,
                           bottomMargin=0.3*inch)
    elements = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=14,
        spaceAfter=20,
        alignment=1
    )
    
    title_text = f"Relatório de Produtividade - {MESES_PORTUGUES.get(mes)}/{ano}"
    elements.append(Paragraph(title_text, title_style))
    elements.append(Spacer(1, 0.1*inch))
    
    dias = list(range(1, 32))
    table_data = []
    
    header = ["Desenvolvedor"]
    header.extend([str(dia) for dia in dias])
    header.extend(["Total", "Meta", "%"])
    table_data.append(header)
    
    for resultado in resultados:
        row = [resultado["funcionario"]]
        
        for dia in dias:
            dia_data = resultado["dias"].get(dia, 0)
            
            if isinstance(dia_data, dict):
                cell_value = dia_data.get("value", "-")
            else:
                if dia_data == 0 or dia_data == 0.0:
                    cell_value = "-"
                else:
                    cell_value = f"{dia_data:.1f}".replace('.0', '') if dia_data % 1 == 0 else f"{dia_data:.1f}"
            
            row.append(cell_value)
        
        row.append(f"{resultado['real']}h")
        row.append(f"{resultado['meta']}h")
        row.append(f"{resultado['percentual']}%")
        table_data.append(row)
    
    num_cols = len(table_data[0])
    page_width = landscape(legal)[0] - 0.4*inch
    dev_col_width = 1.2 * inch
    day_col_width = (page_width - dev_col_width - 1.5*inch) / 31
    total_cols_width = 0.5 * inch
    
    col_widths = [dev_col_width]
    col_widths.extend([day_col_width for _ in dias])
    col_widths.extend([total_cols_width, total_cols_width, total_cols_width])
    
    table = Table(table_data, colWidths=col_widths, repeatRows=1)
    
    table_style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 7),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        
        ('ALIGN', (0, 1), (-1, -1), 'CENTER'),
        ('FONTSIZE', (0, 1), (-1, -1), 6),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ])
    
    if resultados and resultados[-1]["funcionario"] == "REALIZADO":
        realizado_row = len(table_data) - 1
        table_style.add('BACKGROUND', (0, realizado_row), (31, realizado_row), colors.HexColor('#e9d5ff'))
        table_style.add('FONTNAME', (0, realizado_row), (-1, realizado_row), 'Helvetica-Bold')
    
    table.setStyle(table_style)
    elements.append(table)
    
    elements.append(Spacer(1, 0.1*inch))
    legend_style = ParagraphStyle(
        'LegendStyle',
        parent=styles['Normal'],
        fontSize=7,
        spaceAfter=3
    )
    
    gen_date = Paragraph(f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}", 
                         ParagraphStyle('DateStyle', parent=styles['Normal'], fontSize=6))
    elements.append(gen_date)
    
    doc.build(elements)
    
    pdf = buffer.getvalue()
    buffer.close()
    
    return pdf 
