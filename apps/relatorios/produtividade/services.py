"""Serviços para geração de relatórios de produtividade."""

from datetime import datetime
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, legal
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from apps.relatorios.models import Funcionario, MetaTempoControle, TempoGastoEquipe


def calcular_spends_por_dev(mes, ano):
    """Calcula os gastos de tempo por desenvolvedor para um mês e ano específicos."""
    funcionarios = Funcionario.objects.all()
    resultados = []

    total_real = 0.0
    total_meta = 0.0
    soma_diaria_total = {d: 0.0 for d in range(1, 32)}

    for func in funcionarios:
        registros = TempoGastoEquipe.objects.filter(
            funcionario=func, mes__month=mes, mes__year=ano
        )

        meta = obter_meta_funcionario(func.id, mes, ano)

        dias_por_func = {}
        horas_normais = 0.0

        for d in range(1, 32):
            registro_dia = registros.filter(dia_mes=d).first()

            if registro_dia:
                tempo_gasto = float(registro_dia.tempo_gasto)

                if tempo_gasto < 0:
                    codigo_int = int(tempo_gasto)
                    codigo_map = {
                        -1: {"type": "leave", "value": "FE"},
                        -2: {"type": "leave", "value": "AT"},
                        -3: {"type": "leave", "value": "FO"},
                        -4: {"type": "leave", "value": "FA"},
                        -5: {"type": "leave", "value": "LI"},
                        -6: {"type": "leave", "value": "CO"},
                    }
                    dias_por_func[d] = codigo_map.get(
                        codigo_int, {"type": "leave", "value": "-"}
                    )
                elif tempo_gasto > 0:
                    dias_por_func[d] = round(tempo_gasto, 1)
                    horas_normais += tempo_gasto
                    soma_diaria_total[d] += tempo_gasto
                else:
                    dias_por_func[d] = 0.0
            else:
                dias_por_func[d] = 0.0

        percentual = (horas_normais / meta * 100) if meta > 0 else 0

        resultados.append(
            {
                "funcionario": func.nome,
                "funcionario_id": func.id,
                "dias": dias_por_func,
                "real": round(horas_normais, 1),
                "meta": meta,
                "percentual": round(percentual, 1),
            }
        )

        total_real += horas_normais
        total_meta += meta

    percentual_total = (total_real / total_meta * 100) if total_meta > 0 else 0

    soma_diaria_formatada = {}
    for d in range(1, 32):
        valor = soma_diaria_total.get(d, 0.0)
        soma_diaria_formatada[d] = round(valor, 1) if valor > 0 else 0.0

    resultados.append(
        {
            "funcionario": "REALIZADO",
            "dias": soma_diaria_formatada,
            "real": round(total_real, 1),
            "meta": total_meta,
            "percentual": round(percentual_total, 1),
        }
    )

    return resultados


def atualizar_codigo_especial(funcionario_id, mes, ano, dia, codigo):
    """Atualiza o código especial (FE, AT, FO, FA, LI, CO) para um funcionário em um dia específico."""
    try:
        data_mes = datetime(ano, mes, 1)
        funcionario = Funcionario.objects.get(id=funcionario_id)

        print(
            f"""Atualizando código especial: funcionario_id={funcionario_id},
                mes={mes}, ano={ano}, dia={dia}, codigo={codigo}"""
        )

        codigo_map = {"FE": -1, "AT": -2, "FO": -3, "FA": -4, "LI": -5, "CO": -6}

        TempoGastoEquipe.objects.filter(
            funcionario=funcionario, mes=data_mes, dia_mes=dia
        ).delete()

        if codigo and codigo != "NONE":
            if codigo in codigo_map:
                valor_especial = codigo_map[codigo]
                print(f"Salvando código {codigo} como valor {valor_especial}")
            else:
                print(f"Código inválido: {codigo}. Usando FE como padrão.")
                valor_especial = -1

            try:
                dia_data = datetime(ano, mes, dia)
                dias_semana = [
                    "Segunda",
                    "Terça",
                    "Quarta",
                    "Quinta",
                    "Sexta",
                    "Sábado",
                    "Domingo",
                ]
                dia_semana = dias_semana[dia_data.weekday()]
            except BaseException:
                dia_semana = "Segunda"

            TempoGastoEquipe.objects.create(
                funcionario=funcionario,
                mes=data_mes,
                dia_mes=dia,
                dia_semana=dia_semana,
                tempo_gasto=valor_especial,
                meta=None,
            )
            print(f"Registro criado com sucesso para dia {dia}, código {codigo}")
        else:
            print(f"Removendo registro para dia {dia} (código NONE)")

        return True
    except Exception as e:
        print(f"Erro ao atualizar código especial: {e}")
        return False


def atualizar_meta_funcionario(funcionario_id, mes, ano, meta):
    """Atualiza a meta de horas para um funcionário em um mês específico."""
    try:

        meta_obj, created = MetaTempoControle.objects.get_or_create(
            objetivo_clt=f"META_{funcionario_id}_{ano}_{mes:02d}",
            defaults={"objetivo_estagiario": str(meta)},
        )

        if not created:
            meta_obj.objetivo_estagiario = str(meta)
            meta_obj.save()

        return True
    except Exception as e:
        print(f"Erro ao atualizar meta: {e}")
        return False


def atualizar_multiplos_dias(funcionario_id, mes, ano, dias, codigo):
    """Atualiza múltiplos dias com um código especial para um funcionário."""
    success_count = 0
    for dia in dias:
        if atualizar_codigo_especial(funcionario_id, mes, ano, dia, codigo):
            success_count += 1

    return success_count == len(dias)


def obter_meta_funcionario(funcionario_id, mes, ano):
    try:
        meta_individual = MetaTempoControle.objects.get(
            objetivo_clt=f"META_{funcionario_id}_{ano}_{mes:02d}"
        )
        meta_valor = meta_individual.objetivo_estagiario
        if meta_valor and meta_valor.strip():
            return float(meta_valor)
        return 154.0

    except Exception as e:
        print(f"Erro ao obter meta: {e}")
        return 154.0


def exportar_produtividade_pdf(mes, ano, resultados):
    """Gera um relatório PDF de produtividade mensal."""
    MESES_PORTUGUES = {
        1: "Janeiro",
        2: "Fevereiro",
        3: "Março",
        4: "Abril",
        5: "Maio",
        6: "Junho",
        7: "Julho",
        8: "Agosto",
        9: "Setembro",
        10: "Outubro",
        11: "Novembro",
        12: "Dezembro",
    }
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(legal),
        leftMargin=0.2 * inch,
        rightMargin=0.2 * inch,
        topMargin=0.3 * inch,
        bottomMargin=0.3 * inch,
    )
    elements = []

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Heading1"],
        fontSize=14,
        spaceAfter=20,
        alignment=1,
    )

    title_text = f"Relatório de Produtividade - {MESES_PORTUGUES.get(mes)}/{ano}"
    elements.append(Paragraph(title_text, title_style))
    elements.append(Spacer(1, 0.1 * inch))

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

            if isinstance(dia_data, dict) and dia_data.get("type") == "leave":
                cell_value = dia_data.get("value", "-")
            elif isinstance(dia_data, (int, float)) and dia_data < 0:
                codigo_int = int(dia_data)
                codigo_map = {
                    -1: "FE",
                    -2: "AT",
                    -3: "FO",
                    -4: "FA",
                    -5: "LI",
                    -6: "CO",
                }
                cell_value = codigo_map.get(codigo_int, "-")
            else:
                if abs(dia_data - 0) < 1e-9:
                    cell_value = "-"
                else:
                    cell_value = (
                        f"{dia_data:.1f}".replace(".0", "")
                        if dia_data % 1 == 0
                        else f"{dia_data:.1f}"
                    )

            row.append(cell_value)

        row.append(f"{resultado['real']}h")
        row.append(f"{resultado['meta']}h")
        row.append(f"{resultado['percentual']}%")
        table_data.append(row)

    page_width = landscape(legal)[0] - 0.4 * inch
    dev_col_width = 1.2 * inch
    day_col_width = (page_width - dev_col_width - 1.5 * inch) / 31
    total_cols_width = 0.5 * inch

    col_widths = [dev_col_width]
    col_widths.extend([day_col_width for _ in dias])
    col_widths.extend([total_cols_width, total_cols_width, total_cols_width])

    table = Table(table_data, colWidths=col_widths, repeatRows=1)

    table_style = TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#3b82f6")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 7),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
            ("ALIGN", (0, 1), (-1, -1), "CENTER"),
            ("FONTSIZE", (0, 1), (-1, -1), 6),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ]
    )

    if resultados and resultados[-1]["funcionario"] == "REALIZADO":
        realizado_row = len(table_data) - 1
        table_style.add(
            "BACKGROUND",
            (0, realizado_row),
            (31, realizado_row),
            colors.HexColor("#e9d5ff"),
        )
        table_style.add(
            "FONTNAME", (0, realizado_row), (-1, realizado_row), "Helvetica-Bold"
        )

    table.setStyle(table_style)
    elements.append(table)

    elements.append(Spacer(1, 0.1 * inch))

    gen_date = Paragraph(
        f"Gerado em: {
            datetime.now().strftime('%d/%m/%Y %H:%M')}",
        ParagraphStyle("DateStyle", parent=styles["Normal"], fontSize=6),
    )
    elements.append(gen_date)

    doc.build(elements)

    pdf = buffer.getvalue()
    buffer.close()

    return pdf


def calcular_spends_por_dev_com_legendas(mes, ano):
    """Calcula os gastos de tempo por desenvolvedor para um mês e ano específicos, incluindo legendas."""
    return calcular_spends_por_dev(mes, ano)
