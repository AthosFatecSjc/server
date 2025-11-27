"""Serviços para geração do relatório de produtividade diária/mensal."""

from __future__ import annotations

import calendar
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from typing import Iterable

from django.db import connections, transaction
from django.db.models import Sum
from django.db.models.functions import ExtractDay
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, legal
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from apps.relatorios.models import (
    Funcionario,
    Issue,
    MetaProdutividade,
    RegistroProdutividade,
)
from olap_models.models import DimTempo, FatoRegistroHoras

OLTP_ALIAS = "default"
OLAP_ALIAS = "olap"
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

CODIGO_ESPECIAL_VALORES = {
    "FE": -1,
    "AT": -2,
    "FO": -3,
    "FA": -4,
    "LI": -5,
    "CO": -6,
}
CODIGOS_REVERSOS = {valor: codigo for codigo, valor in CODIGO_ESPECIAL_VALORES.items()}
HORAS_DIA_CONTRATO = {
    "CLT": Decimal("8"),
    "ESTAGIARIO": Decimal("6"),
}


# ---------------------------------------------------------------------------
# Consultas base
# ---------------------------------------------------------------------------
def listar_meses_disponiveis() -> list[dict]:
    """Retorna os meses disponíveis no controle (manual ou OLAP)."""
    meses = (
        Issue.objects.using(OLTP_ALIAS)
        .filter(criado_em__isnull=False)
        .values_list("criado_em__year", "criado_em__month")
        .distinct()
        .order_by("-criado_em__year", "-criado_em__month")
    )
    resultado = [
        {
            "mes": mes,
            "ano": ano,
            "mes_nome": MESES_PORTUGUES.get(mes, f"Mês {mes}"),
        }
        for ano, mes in meses
    ]

    if not resultado:
        hoje = datetime.now()
        resultado = [
            {
                "mes": hoje.month,
                "ano": hoje.year,
                "mes_nome": MESES_PORTUGUES.get(hoje.month, f"Mês {hoje.month}"),
            }
        ]

    return resultado


def listar_equipes_disponiveis() -> list[str]:
    return sorted(
        Funcionario.objects.using(OLTP_ALIAS)
        .exclude(time__isnull=True)
        .exclude(time="")
        .values_list("time", flat=True)
        .distinct()
    )


def calcular_spends_por_dev_com_legendas(
    mes: int, ano: int, equipe: str | None = None
) -> dict:
    dias = _listar_dias_mes(mes, ano)
    resultados = _calcular_spends_por_dev(mes, ano, dias, equipe)
    return {"dias": dias, "resultados": resultados}


def _listar_dias_mes(mes: int, ano: int) -> list[int]:
    qs = (
        DimTempo.objects.using(OLAP_ALIAS)
        .filter(mes=mes, ano=ano, hora=0)
        .order_by("dia")
        .values_list("dia", flat=True)
    )
    dias = list(qs)
    if dias:
        return dias
    _, total_dias = calendar.monthrange(ano, mes)
    return list(range(1, total_dias + 1))


def _calcular_spends_por_dev(
    mes: int, ano: int, dias: Iterable[int], equipe: str | None
) -> list[dict]:
    funcionarios = _buscar_funcionarios(equipe)
    if not funcionarios:
        return []

    registros, horas_issue, horas_fato = _buscar_fontes_horas(funcionarios, mes, ano)

    resultados_brutos = []

    for func in funcionarios:
        dias_por_func, horas_normais = _montar_grade_funcionario(
            func, dias, registros, horas_issue, horas_fato
        )
        meta_valor = obter_meta_funcionario(func, mes, ano)
        meta = Decimal(str(meta_valor))
        percentual = _percentual(horas_normais, meta)

        resultados_brutos.append(
            {
                "funcionario": func.nome,
                "funcionario_id": func.id,
                "dias": dias_por_func,
                "real": round(float(horas_normais), 1),
                "meta": float(meta),
                "percentual": percentual,
            }
        )
    resultados = _consolidar_resultados_por_nome(resultados_brutos, dias)
    soma_diaria_total = {dia: Decimal("0") for dia in dias}
    total_real = Decimal("0")
    total_meta = Decimal("0")

    for resultado in resultados:
        total_real += Decimal(str(resultado["real"]))
        total_meta += Decimal(str(resultado["meta"]))
        for dia, valor in resultado["dias"].items():
            if isinstance(valor, (int, float, Decimal)) and valor > 0:
                soma_diaria_total[dia] += Decimal(str(valor))

    resultados.append(
        {
            "funcionario": "REALIZADO",
            "funcionario_id": None,
            "dias": {
                dia: round(float(valor), 1) if valor > 0 else 0.0
                for dia, valor in soma_diaria_total.items()
            },
            "real": round(float(total_real), 1),
            "meta": round(float(total_meta), 1),
            "percentual": _percentual(total_real, total_meta),
        }
    )
    return resultados


def _consolidar_resultados_por_nome(resultados: list[dict], dias: Iterable[int]):
    """Agrupa linhas duplicadas pelo mesmo nome de funcionário."""
    agrupado: dict[str, dict] = {}

    for res in resultados:
        nome = res.get("funcionario") or ""
        if not nome:
            continue

        destino = agrupado.setdefault(
            nome,
            {
                "funcionario": nome,
                "funcionario_id": res.get("funcionario_id"),
                "dias": dict.fromkeys(dias, 0.0),
                "real": 0.0,
                "meta": 0.0,
                "percentual": 0.0,
            },
        )

        for dia, valor in res.get("dias", {}).items():
            destino["dias"][dia] = _mesclar_valor_dia(destino["dias"].get(dia), valor)

        destino["meta"] = max(destino["meta"], res.get("meta", 0.0))

    for destino in agrupado.values():
        horas_totais = Decimal("0")
        for valor in destino["dias"].values():
            if isinstance(valor, (int, float, Decimal)) and valor > 0:
                horas_totais += Decimal(str(valor))
        destino["real"] = round(float(horas_totais), 1)
        destino["percentual"] = _percentual(
            Decimal(str(destino["real"])), Decimal(str(destino["meta"]))
        )

    return sorted(agrupado.values(), key=lambda item: item["funcionario"].lower())


def _mesclar_valor_dia(atual, novo):
    """Combina valores de um mesmo dia para o mesmo funcionário, somando horas."""
    if atual is None:
        return novo
    if novo is None:
        return atual

    atual_num = _as_decimal(atual)
    novo_num = _as_decimal(novo)

    if atual_num is not None and novo_num is not None:
        return round(float(atual_num + novo_num), 1)

    if isinstance(atual, dict):
        if isinstance(novo, dict):
            return atual
        if novo_num is not None:
            return novo if novo_num > 0 else atual
        return atual

    if isinstance(novo, dict) and atual_num is not None:
        return atual if atual_num > 0 else novo

    return novo


def _as_decimal(value):
    if isinstance(value, (int, float, Decimal)):
        return Decimal(str(value))
    return None


def _buscar_funcionarios(equipe: str | None) -> list[Funcionario]:
    funcionarios_qs = Funcionario.objects.using(OLTP_ALIAS).order_by("nome")
    if equipe:
        funcionarios_qs = funcionarios_qs.filter(time=equipe)
    return list(funcionarios_qs)


def _buscar_fontes_horas(funcionarios: list[Funcionario], mes: int, ano: int):
    funcionario_ids = [f.id for f in funcionarios]
    return (
        _buscar_registros_diarios(mes, ano, funcionario_ids),
        _buscar_horas_issue(mes, ano, funcionario_ids),
        _buscar_horas_fato(mes, ano, funcionario_ids),
    )


def _montar_grade_funcionario(
    funcionario: Funcionario,
    dias: Iterable[int],
    registros: dict,
    horas_issue: dict,
    horas_fato: dict,
) -> tuple[dict, Decimal]:
    dias_por_func = {}
    horas_normais = Decimal("0")

    for dia in dias:
        key = (funcionario.id, dia)
        valor = None
        if key in registros:
            valor = registros[key]
            dias_por_func[dia] = _formatar_valor_celula(valor)
            if valor > 0:
                horas_normais += valor
        elif key in horas_issue:
            valor = horas_issue[key]
            dias_por_func[dia] = round(float(valor), 1)
            horas_normais += valor
        elif key in horas_fato:
            valor = horas_fato[key]
            dias_por_func[dia] = round(float(valor), 1)
            horas_normais += valor
        else:
            dias_por_func[dia] = 0.0

    return dias_por_func, horas_normais


def _buscar_registros_diarios(mes: int, ano: int, funcionarios: list[int]):
    qs = (
        RegistroProdutividade.objects.using(OLTP_ALIAS)
        .filter(dia__year=ano, dia__month=mes, funcionario_id__in=funcionarios)
        .values_list("funcionario_id", "dia__day", "valor")
    )
    return {(func, dia): Decimal(valor) for func, dia, valor in qs}


def _buscar_horas_issue(mes: int, ano: int, funcionarios: list[int]):
    if not funcionarios:
        return {}
    qs = (
        Issue.objects.using(OLTP_ALIAS)
        .filter(
            funcionario_id__in=funcionarios,
            criado_em__year=ano,
            criado_em__month=mes,
            criado_em__isnull=False,
        )
        .annotate(dia=ExtractDay("criado_em"))
        .values("funcionario_id", "dia")
        .annotate(total=Sum("tempo_gasto_seconds"))
    )
    horas = {}
    for item in qs:
        total_seconds = Decimal(str(item["total"] or 0))
        horas[item["funcionario_id"], item["dia"]] = total_seconds / Decimal("3600")
    return horas


def _buscar_horas_fato(mes: int, ano: int, funcionarios: list[int]):
    if not funcionarios:
        return {}
    qs = (
        FatoRegistroHoras.objects.using(OLAP_ALIAS)
        .filter(funcionario_id__in=funcionarios, data__mes=mes, data__ano=ano)
        .values("funcionario_id", "data__dia")
        .annotate(horas=Sum("horas_trabalhadas"))
    )
    return {
        (item["funcionario_id"], item["data__dia"]): Decimal(str(item["horas"]))
        for item in qs
        if item["horas"]
    }


# ---------------------------------------------------------------------------
# Atualizações de legendas/metas
# ---------------------------------------------------------------------------
def atualizar_multiplos_dias(
    funcionario_id: int, mes: int, ano: int, dias: Iterable[int], codigo: str
) -> tuple[bool, str | None]:
    try:
        with transaction.atomic(using=OLTP_ALIAS):
            for dia in dias:
                sucesso, erro = _atualizar_codigo_especial(
                    funcionario_id, mes, ano, dia, codigo
                )
                if not sucesso:
                    raise ValueError(erro or "Não foi possível atualizar o dia.")
        return True, None
    except Exception as exc:  # pragma: no cover - tratado via view
        return False, str(exc)


def _atualizar_codigo_especial(
    funcionario_id: int, mes: int, ano: int, dia: int, codigo: str
) -> tuple[bool, str | None]:
    dia_completo = date(ano, mes, dia)

    if _possui_horas_fato(funcionario_id, dia_completo):
        return False, "Dia já possui horas lançadas no histórico."

    registro = (
        RegistroProdutividade.objects.using(OLTP_ALIAS)
        .filter(funcionario_id=funcionario_id, dia=dia_completo)
        .first()
    )

    if registro and registro.valor > 0:
        return False, "Dia já possui horas lançadas."

    if codigo == "NONE":
        if registro:
            registro.delete()
        return True, None

    valor = CODIGO_ESPECIAL_VALORES.get(codigo)
    if valor is None:
        return False, "Código de ausência inválido."

    if registro:
        registro.valor = Decimal(valor)
        registro.save(using=OLTP_ALIAS)
    else:
        RegistroProdutividade.objects.using(OLTP_ALIAS).create(
            funcionario_id=funcionario_id,
            dia=dia_completo,
            valor=Decimal(valor),
        )
    return True, None


def _possui_horas_fato(funcionario_id: int, dia: date) -> bool:
    horas = (
        FatoRegistroHoras.objects.using(OLAP_ALIAS)
        .filter(
            funcionario_id=funcionario_id,
            data__ano=dia.year,
            data__mes=dia.month,
            data__dia=dia.day,
        )
        .aggregate(total=Sum("horas_trabalhadas"))
    )["total"]
    return bool(horas and horas > 0)


def atualizar_meta_funcionario(funcionario_id: int, mes: int, ano: int, meta: float):
    MetaProdutividade.objects.using(OLTP_ALIAS).update_or_create(
        funcionario_id=funcionario_id,
        mes=mes,
        ano=ano,
        defaults={"meta_horas": Decimal(str(meta))},
    )
    return True


def obter_meta_funcionario(funcionario: Funcionario, mes: int, ano: int) -> float:
    meta = (
        MetaProdutividade.objects.using(OLTP_ALIAS)
        .filter(funcionario=funcionario, mes=mes, ano=ano)
        .first()
    )
    if meta and meta.meta_horas:
        return float(meta.meta_horas)
    return float(_meta_padrao(funcionario, mes, ano))


def _meta_padrao(funcionario: Funcionario, mes: int, ano: int) -> Decimal:
    tipo_contrato = getattr(funcionario, "contrato", None) or "CLT"
    horas_dia = HORAS_DIA_CONTRATO.get(tipo_contrato.upper(), Decimal("8"))
    dias_uteis = _dias_uteis_no_mes(mes, ano)
    return horas_dia * Decimal(dias_uteis)


def _dias_uteis_no_mes(mes: int, ano: int) -> int:
    total_dias = calendar.monthrange(ano, mes)[1]
    return sum(
        1 for dia in range(1, total_dias + 1) if date(ano, mes, dia).weekday() < 5
    )


# ---------------------------------------------------------------------------
# Utilidades de exibição / PDF
# ---------------------------------------------------------------------------
def _formatar_valor_celula(valor: Decimal | None):
    if valor is None:
        return 0.0
    if valor < 0:
        codigo = CODIGOS_REVERSOS.get(int(valor))
        return {"type": "leave", "value": codigo or "-"}
    if valor == 0:
        return 0.0
    return round(float(valor), 1)


def _percentual(real: Decimal, meta: Decimal) -> float:
    if meta <= 0:
        return 0.0
    return round(float(real / meta * 100), 1)


def exportar_produtividade_pdf(mes: int, ano: int, resultados: list[dict]):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(legal),
        leftMargin=0.2 * inch,
        rightMargin=0.2 * inch,
        topMargin=0.3 * inch,
        bottomMargin=0.3 * inch,
    )

    elements = [_criar_titulo_pdf(mes, ano), Spacer(1, 0.1 * inch)]
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


def _criar_titulo_pdf(mes: int, ano: int):
    styles = getSampleStyleSheet()
    titulo = (
        f"Relatório de Produtividade - {MESES_PORTUGUES.get(mes, 'Mês Inválido')}/{ano}"
    )
    return Paragraph(
        titulo,
        ParagraphStyle(
            "CustomTitle",
            parent=styles["Heading1"],
            fontSize=14,
            spaceAfter=20,
            alignment=1,
        ),
    )


def _montar_tabela_pdf(resultados):
    dias = list(range(1, 32))
    table_data = [["Desenvolvedor"] + [str(d) for d in dias] + ["Total", "Meta", "%"]]

    for resultado in resultados:
        row = [resultado["funcionario"]]
        for dia in dias:
            valor = resultado["dias"].get(dia, 0)
            if isinstance(valor, dict):
                row.append(valor.get("value", "-"))
            elif valor:
                row.append(valor)
            else:
                row.append("-")
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
