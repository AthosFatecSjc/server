"""Views for the produtividade report."""
import json
from datetime import datetime

from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from apps.relatorios.models import TempoGastoEquipe
from apps.relatorios.produtividade.services import (atualizar_meta_funcionario,
                                                    atualizar_multiplos_dias,
                                                    calcular_spends_por_dev_com_legendas, exportar_produtividade_pdf)


@require_GET
def index(request):
    mes_param = request.GET.get('mes')
    ano_param = request.GET.get('ano')

    if mes_param and ano_param:
        mes = int(mes_param)
        ano = int(ano_param)
    else:
        hoje = datetime.now()
        mes = hoje.month
        ano = hoje.year

    MESES_PORTUGUES = {
        1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril',
        5: 'Maio', 6: 'Junho', 7: 'Julho', 8: 'Agosto',
        9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'
    }

    meses_disponiveis_query = TempoGastoEquipe.objects.extra(
        select={
            'ano': 'EXTRACT(YEAR FROM mes)',
            'mes_num': 'EXTRACT(MONTH FROM mes)'}).values(
        'ano',
        'mes_num').distinct()

    meses_disponiveis = []
    for item in meses_disponiveis_query:
        mes_num = int(item['mes_num'])
        meses_disponiveis.append({
            'mes': mes_num,
            'ano': int(item['ano']),
            'mes_nome': MESES_PORTUGUES.get(mes_num, f'Mês {mes_num}')
        })

    meses_disponiveis.sort(key=lambda x: (x['ano'], x['mes']), reverse=True)

    resultados = calcular_spends_por_dev_com_legendas(mes, ano)
    dias = list(range(1, 32))

    return render(request, 'produtividade/index.html', {
        'resultados': resultados,
        'mes': mes,
        'ano': ano,
        'dias': dias,
        'meses_disponiveis': meses_disponiveis,
        'mes_nome': MESES_PORTUGUES.get(mes, f'Mês {mes}')
    })


@require_GET
def exportar_pdf(request):
    mes_param = request.GET.get('mes')
    ano_param = request.GET.get('ano')

    if mes_param and ano_param:
        mes = int(mes_param)
        ano = int(ano_param)
    else:
        hoje = datetime.now()
        mes = hoje.month
        ano = hoje.year

    resultados = calcular_spends_por_dev_com_legendas(mes, ano)
    pdf = exportar_produtividade_pdf(mes, ano, resultados)

    MESES_PORTUGUES = {
        1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril',
        5: 'Maio', 6: 'Junho', 7: 'Julho', 8: 'Agosto',
        9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'
    }

    filename = f"produtividade_{MESES_PORTUGUES.get(mes)}_{ano}.pdf"

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response.write(pdf)

    return response


@require_POST
def atualizar_legenda(request):
    try:
        data = json.loads(request.body)
        funcionario_id = data.get('funcionario_id')
        mes = data.get('mes')
        ano = data.get('ano')
        dias = data.get('dias', [])
        codigo = data.get('codigo')

        print(
            f"Recebendo requisição: funcionario_id={funcionario_id}, mes={mes}, ano={ano}, dias={dias}, codigo={codigo}")

        success = atualizar_multiplos_dias(
            funcionario_id, mes, ano, dias, codigo)

        return JsonResponse({'success': success})
    except Exception as e:
        print(f"Erro na view atualizar_legenda: {e}")
        return JsonResponse({'success': False, 'error': str(e)})


@require_POST
def atualizar_meta(request):
    try:
        data = json.loads(request.body)
        funcionario_id = data.get('funcionario_id')
        mes = data.get('mes')
        ano = data.get('ano')
        meta = data.get('meta')

        success = atualizar_meta_funcionario(funcionario_id, mes, ano, meta)

        return JsonResponse({'success': success})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
