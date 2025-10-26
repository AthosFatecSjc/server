"""Views para a aplicação de relatórios de atividade."""

import datetime

from django.http import HttpResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.views.decorators.http import require_GET, require_safe

from .services import AtividadeService


@require_safe
def index(request):
    """Renderiza a página inicial do relatório de atividades."""
    hoje = datetime.date.today()
    anos_disponiveis = range(hoje.year - 5, hoje.year + 2)

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

    context = {
        "ano_atual": hoje.year,
        "mes_atual": hoje.month,
        "anos_disponiveis": anos_disponiveis,
        "meses": MESES_PORTUGUES,
        "cabecalho": {"titulo": "", "subtitulo": ""},
    }

    return render(request, "atividade/index.html", context)


@require_GET
def relatorio_tabela_e_cards(request):
    """Renderiza o relatório de atividades em formato de tabela e cards."""
    hoje = datetime.date.today()

    try:
        ano = int(request.GET.get("ano", hoje.year))
        mes = int(request.GET.get("mes", hoje.month))
    except (ValueError, TypeError):
        ano, mes = hoje.year, hoje.month

    mes_nome = AtividadeService.MESES_PORTUGUES.get(mes, "")

    context = {
        "cabecalho": {"titulo": "", "subtitulo": ""},
        "dados": AtividadeService.gerar_dados_relatorio_atividade(ano, mes),
        "ano": ano,
        "mes_nome": mes_nome,
    }

    response = '<div id="horas_projeto" class="conteudo">'
    response += get_tabela_horas_projeto(context, request)
    response += get_tabela_horas_por_dev(context, request)
    response += "</div>"
    response += '<div id="horas_por_dev" class="conteudo" style="margin-top: 15px">'
    response += get_grafico_horas_projeto(context, request)
    response += get_grafico_horas_por_dev(context, request)
    response += "</div>"

    return HttpResponse(response)


def get_tabela_horas_projeto(context, request):
    """Renderiza a tabela de horas por projeto."""
    context.update(
        {
            "cabecalho": {
                "titulo": "Horas por Desenvolvedor e Projeto",
                "subtitulo": f'Distribuição de horas trabalhadas - {context.get("mes_nome")}/{context.get("ano")}',
            }
        }
    )
    return render_to_string(
        "atividade/partials/_tabela_e_cards.html", context, request=request
    )


def get_grafico_horas_projeto(context, request):
    """Renderiza o gráfico de horas por projeto."""
    context.update(
        {
            "cabecalho": {
                "titulo": "Distribuição de Horas por Projeto",
                "subtitulo": f"""Percentual de horas dedicadas a cada projeto em {
                    context.get("mes_nome")}/{
                    context.get("ano")}""",
            }
        }
    )

    context["dados"]["dados_grafico_pizza"] = [
        {"label": registro["projeto_nome"], "data": registro["total_horas"]}
        for registro in context["dados"]["dados_cards"]
    ]

    return render_to_string(
        "atividade/partials/_grafico_pizza.html", context, request=request
    )


def get_tabela_horas_por_dev(context, request):
    """Renderiza a tabela de horas por desenvolvedor."""
    context.update(
        {
            "cabecalho": {
                "titulo": "Total de Horas por Desenvolvedor",
                "subtitulo": f'{context.get("mes_nome")}/{context.get("ano")}',
            }
        }
    )
    return render_to_string(
        "atividade/partials/_tabela_horas_dev.html", context, request=request
    )


def get_grafico_horas_por_dev(context, request):
    """Renderiza o gráfico de horas por desenvolvedor."""
    context.update(
        {
            "cabecalho": {
                "titulo": "Distribuição de Horas por Desenvolvedor",
                "subtitulo": f'{context.get("mes_nome")}/{context.get("ano")}',
            }
        }
    )

    context["dados"]["dados_grafico_pizza"] = [
        {"label": registro["colaborador_nome"], "data": registro["total_colaborador"]}
        for registro in context["dados"]["dados_tabela"]
    ]

    return render_to_string(
        "atividade/partials/_grafico_pizza.html", context, request=request
    )


@require_GET
def exportar_pdf(request):
    """Exporta o relatório de atividades em PDF."""
    hoje = datetime.date.today()

    try:
        ano = int(request.GET.get("ano", hoje.year))
        mes = int(request.GET.get("mes", hoje.month))
    except (ValueError, TypeError):
        ano, mes = hoje.year, hoje.month

    dados = AtividadeService.gerar_dados_relatorio_atividade(ano, mes)
    pdf = AtividadeService.exportar_atividade_pdf(mes, ano, dados)

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

    filename = f"atividades_{MESES_PORTUGUES.get(mes)}_{ano}.pdf"

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.write(pdf)

    return response
