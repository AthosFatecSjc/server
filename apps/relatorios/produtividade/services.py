"""Serviços para geração de relatórios de produtividade."""

from datetime import datetime
from io import BytesIO

from django.core.exceptions import ObjectDoesNotExist
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, legal
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from apps.relatorios.models import Funcionario, MetaTempoControle, TempoGastoEquipe


def _codigo_especial(tempo_gasto):
    """Mapeia valores negativos para códigos especiais (folga, licença etc.)."""
    codigo_map = {
        -1: {"type": "leave", "value": "FE"},
        -2: {"type": "leave", "value": "AT"},
        -3: {"type": "leave", "value": "FO"},
        -4: {"type": "leave", "value": "FA"},
        -5: {"type": "leave", "value": "LI"},
        -6: {"type": "leave", "value": "CO"},
    }
    return codigo_map.get(int(tempo_gasto), {"type": "leave", "value": "-"})


def _processar_dias_funcionario(registros):
    """
    Processa os registros de tempo de um funcionário.
    Retorna: (dias_por_func, horas_normais, soma_diaria_total)
    """
    dias_por_func = dict.fromkeys(range(1, 32), 0.0)
    soma_diaria_total = dict.fromkeys(range(1, 32), 0.0)
    horas_normais = 0.0

    for dia in range(1, 32):
        registro_dia = registros.filter(dia_mes=dia).first()
        if not registro_dia:
            continue

        tempo_gasto = float(registro_dia.tempo_gasto)
        if tempo_gasto < 0:
            dias_por_func[dia] = _codigo_especial(tempo_gasto)
        elif tempo_gasto > 0:
            dias_por_func[dia] = round(tempo_gasto, 1)
            horas_normais += tempo_gasto
            soma_diaria_total[dia] += tempo_gasto

    return dias_por_func, horas_normais, soma_diaria_total


def calcular_spends_por_dev(mes, ano):
    funcionarios = Funcionario.objects.all()
    resultados = []
    soma_diaria_total = dict.fromkeys(range(1, 32), 0.0)
    total_real = total_meta = 0.0

    for func in funcionarios:
        registros = TempoGastoEquipe.objects.filter(
            funcionario=func, mes__month=mes, mes__year=ano
        )
        meta = obter_meta_funcionario(func.id, mes, ano)

        dias_por_func, horas_normais, soma_func = _processar_dias_funcionario(registros)

        for dia, valor in soma_func.items():
            soma_diaria_total[dia] += valor

        percentual = (horas_normais / meta * 100) if meta > 0 else 0.0

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

    percentual_total = (total_real / total_meta * 100) if total_meta > 0 else 0.0
    soma_diaria_formatada = {
        d: round(v, 1) if v > 0 else 0.0 for d, v in soma_diaria_total.items()
    }

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
    try:
        data_mes = datetime(ano, mes, 1)
        funcionario = Funcionario.objects.get(id=funcionario_id)
        codigo_map = {"FE": -1, "AT": -2, "FO": -3, "FA": -4, "LI": -5, "CO": -6}

        TempoGastoEquipe.objects.filter(
            funcionario=funcionario, mes=data_mes, dia_mes=dia
        ).delete()

        if not codigo or codigo == "NONE":
            print(f"Removendo registro para dia {dia} (código NONE)")
            return True

        valor_especial = codigo_map.get(codigo, -1)
        dia_semana = datetime(ano, mes, dia).strftime("%A")

        TempoGastoEquipe.objects.create(
            funcionario=funcionario,
            mes=data_mes,
            dia_mes=dia,
            dia_semana=dia_semana,
            tempo_gasto=valor_especial,
            meta=None,
        )
        print(f"Registro criado com sucesso para dia {dia}, código {codigo}")
        return True

    except Funcionario.DoesNotExist:
        print(f"Funcionário com ID {funcionario_id} não encontrado.")
    except ObjectDoesNotExist:
        print("Registro relacionado não encontrado.")
    except ValueError as e:
        print(f"Erro de valor inválido: {e}")
    return False


def atualizar_meta_funcionario(funcionario_id, mes, ano, meta):
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
    success_count = sum(
        atualizar_codigo_especial(funcionario_id, mes, ano, dia, codigo) for dia in dias
    )
    return success_count == len(dias)


def obter_meta_funcionario(funcionario_id, mes, ano):
    try:
        meta_individual = MetaTempoControle.objects.get(
            objetivo_clt=f"META_{funcionario_id}_{ano}_{mes:02d}"
        )
        meta_valor = meta_individual.objetivo_estagiario
        return float(meta_valor) if meta_valor and meta_valor.strip() else 154.0
    except Exception as e:
        print(f"Erro ao obter meta: {e}")
        return 154.0


def _criar_titulo_pdf(mes: int, ano: int):
    MESES_PT = {
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
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Heading1"],
        fontSize=14,
        spaceAfter=20,
        alignment=1,
    )
    titulo = f"Relatório de Produtividade - {MESES_PT.get(mes, 'Mês Inválido')}/{ano}"
    return Paragraph(titulo, title_style)


def _formatar_valor_celula(dia_data):
    if isinstance(dia_data, dict) and dia_data.get("type") == "leave":
        return dia_data.get("value", "-")

    if isinstance(dia_data, (int, float)) and dia_data < 0:
        codigo_map = {-1: "FE", -2: "AT", -3: "FO", -4: "FA", -5: "LI", -6: "CO"}
        return codigo_map.get(int(dia_data), "-")

    if abs(dia_data) < 1e-9:
        return "-"

    return f"{dia_data:.1f}".replace(".0", "")


def _montar_tabela_pdf(resultados):
    dias = list(range(1, 32))
    table_data = [["Desenvolvedor"] + [str(d) for d in dias] + ["Total", "Meta", "%"]]

    for resultado in resultados:
        row = [resultado["funcionario"]]
        for dia in dias:
            cell_value = _formatar_valor_celula(resultado["dias"].get(dia, 0))
            row.append(cell_value)
        row += [
            f"{resultado['real']}h",
            f"{resultado['meta']}h",
            f"{resultado['percentual']}%",
        ]
        table_data.append(row)

    return table_data, dias


def _aplicar_estilo_pdf(tabela, resultados, dias):
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

    if resultados and resultados[-1].get("funcionario") == "REALIZADO":
        realizado_row = len(resultados)
        table_style.add(
            "BACKGROUND",
            (0, realizado_row),
            (len(dias), realizado_row),
            colors.HexColor("#e9d5ff"),
        )
        table_style.add(
            "FONTNAME", (0, realizado_row), (-1, realizado_row), "Helvetica-Bold"
        )

    tabela.setStyle(table_style)
    return tabela


def exportar_produtividade_pdf(mes, ano, resultados):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(legal),
        leftMargin=0.2 * inch,
        rightMargin=0.2 * inch,
        topMargin=0.3 * inch,
        bottomMargin=0.3 * inch,
    )

    elements = [
        _criar_titulo_pdf(mes, ano),
        Spacer(1, 0.1 * inch),
    ]

    table_data, dias = _montar_tabela_pdf(resultados)
    page_width = landscape(legal)[0] - 0.4 * inch
    dev_col_width = 1.2 * inch
    day_col_width = (page_width - dev_col_width - 1.5 * inch) / 31
    total_col_width = 0.5 * inch

    col_widths = [dev_col_width] + [day_col_width for _ in dias] + [total_col_width] * 3
    tabela = Table(table_data, colWidths=col_widths, repeatRows=1)
    tabela = _aplicar_estilo_pdf(tabela, resultados, dias)

    elements.extend([tabela, Spacer(1, 0.1 * inch)])

    styles = getSampleStyleSheet()
    data_footer = Paragraph(
        f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        ParagraphStyle("DateStyle", parent=styles["Normal"], fontSize=6),
    )
    elements.append(data_footer)

    doc.build(elements)
    pdf = buffer.getvalue()
    buffer.close()
    return pdf


def calcular_spends_por_dev_com_legendas(mes, ano):
    return calcular_spends_por_dev(mes, ano)
