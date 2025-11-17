"""Views for the produtividade report."""

import json
from datetime import datetime

from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from apps.relatorios.produtividade.services import (
    MESES_PORTUGUES,
    atualizar_meta_funcionario,
    atualizar_multiplos_dias,
    calcular_spends_por_dev_com_legendas,
    exportar_produtividade_pdf,
    listar_equipes_disponiveis,
    listar_meses_disponiveis,
)


@require_GET
def index(request):
    mes_param = request.GET.get("mes")
    ano_param = request.GET.get("ano")
    mes_ano_param = request.GET.get("mes_ano")
    equipe = request.GET.get("equipe") or None

    if mes_ano_param and "-" in mes_ano_param:
        try:
            mes_param, ano_param = mes_ano_param.split("-", 1)
        except ValueError:
            mes_param = ano_param = None

    meses_disponiveis = listar_meses_disponiveis()
    if mes_param and ano_param:
        try:
            mes = int(mes_param)
            ano = int(ano_param)
        except (TypeError, ValueError):
            mes = meses_disponiveis[0]["mes"]
            ano = meses_disponiveis[0]["ano"]
    else:
        mes = meses_disponiveis[0]["mes"]
        ano = meses_disponiveis[0]["ano"]

    dados = calcular_spends_por_dev_com_legendas(mes, ano, equipe)
    equipes = listar_equipes_disponiveis()
    header_context = {
        "breadcrumb": "Relatórios",
        "title": "Gestão à Vista - Operacional",
        "subtitle": "Calendário diário de produtividade, metas e ausências",
        "show_export": True,
    }

    return render(
        request,
        "produtividade/index.html",
        {
            "resultados": dados["resultados"],
            "mes": mes,
            "ano": ano,
            "dias": dados["dias"],
            "meses_disponiveis": meses_disponiveis,
            "equipes": equipes,
            "equipe_selecionada": equipe,
            "mes_nome": MESES_PORTUGUES.get(mes, f"Mês {mes}"),
            "header_context": header_context,
        },
    )


@require_GET
def exportar_pdf(request):
    mes_param = request.GET.get("mes")
    ano_param = request.GET.get("ano")
    equipe = request.GET.get("equipe") or None

    if mes_param and ano_param:
        mes = int(mes_param)
        ano = int(ano_param)
    else:
        hoje = datetime.now()
        mes = hoje.month
        ano = hoje.year

    dados = calcular_spends_por_dev_com_legendas(mes, ano, equipe)
    pdf = exportar_produtividade_pdf(mes, ano, dados["resultados"])

    filename = f"produtividade_{MESES_PORTUGUES.get(mes)}_{ano}.pdf"

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.write(pdf)

    return response


@require_POST
def atualizar_legenda(request):
    try:
        data = json.loads(request.body)
        funcionario_id = data.get("funcionario_id")
        mes = data.get("mes")
        ano = data.get("ano")
        dias = data.get("dias", [])
        codigo = data.get("codigo")

        print(
            f"Recebendo requisição: funcionario_id={funcionario_id}, mes={mes}, ano={ano}, dias={dias}, codigo={codigo}"
        )

        success, error = atualizar_multiplos_dias(
            funcionario_id, mes, ano, dias, codigo
        )

        return JsonResponse({"success": success, "error": error})
    except Exception as e:
        print(f"Erro na view atualizar_legenda: {e}")
        return JsonResponse({"success": False, "error": str(e)})


@require_POST
def atualizar_meta(request):
    try:
        data = json.loads(request.body)
        funcionario_id = data.get("funcionario_id")
        mes = data.get("mes")
        ano = data.get("ano")
        meta = data.get("meta")

        success = atualizar_meta_funcionario(funcionario_id, mes, ano, meta)

        return JsonResponse({"success": success})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})
