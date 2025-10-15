"""Views for the produtividade report."""

import json
from datetime import datetime

from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from apps.relatorios.models import TempoGastoEquipe
from apps.relatorios.produtividade.services import (
    atualizar_meta_funcionario,
    atualizar_multiplos_dias,
    calcular_spends_por_dev_com_legendas,
    exportar_produtividade_pdf,
)
from apps.utils.constants import MESES_PORTUGUES


@require_GET
def index(request):
    mes_param = request.GET.get("mes")
    ano_param = request.GET.get("ano")

    if mes_param and ano_param:
        mes = int(mes_param)
        ano = int(ano_param)
    else:
        hoje = datetime.now()
        mes = hoje.month
        ano = hoje.year

    meses_disponiveis_query = (
        TempoGastoEquipe.objects.extra(
            select={
                "ano": "EXTRACT(YEAR FROM mes)",
                "mes_num": "EXTRACT(MONTH FROM mes)",
            }
        )
        .values("ano", "mes_num")
        .distinct()
    )

    meses_disponiveis = [
        {
            "mes": int(item["mes_num"]),
            "ano": int(item["ano"]),
            "mes_nome": MESES_PORTUGUES.get(
                int(item["mes_num"]), f"Mês {item['mes_num']}"
            ),
        }
        for item in meses_disponiveis_query
    ]

    meses_disponiveis.sort(key=lambda x: (x["ano"], x["mes"]), reverse=True)

    resultados = calcular_spends_por_dev_com_legendas(mes, ano)
    dias = list(range(1, 32))

    return render(
        request,
        "produtividade/index.html",
        {
            "resultados": resultados,
            "mes": mes,
            "ano": ano,
            "dias": dias,
            "meses_disponiveis": meses_disponiveis,
            "mes_nome": MESES_PORTUGUES.get(mes, f"Mês {mes}"),
        },
    )


@require_GET
def exportar_pdf(request):
    mes_param = request.GET.get("mes")
    ano_param = request.GET.get("ano")

    if mes_param and ano_param:
        mes = int(mes_param)
        ano = int(ano_param)
    else:
        hoje = datetime.now()
        mes = hoje.month
        ano = hoje.year

    resultados = calcular_spends_por_dev_com_legendas(mes, ano)
    pdf = exportar_produtividade_pdf(mes, ano, resultados)

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

        success = atualizar_multiplos_dias(funcionario_id, mes, ano, dias, codigo)

        return JsonResponse({"success": success})
    except Exception as e:
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
