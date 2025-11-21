import json

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from apps.usuarios.decorators import perfil_gerente_required

from .services import DesenvolvedoresService


@perfil_gerente_required
@require_http_methods(["GET"])
def index(request):
    header_context = {
        "title": "Gerenciamento de Desenvolvedores",
        "subtitle": "Configure valores por hora e visualize estatísticas",
        "breadcrumb": "Gerenciamento",
    }

    try:
        desenvolvedores = DesenvolvedoresService.get_desenvolvedores_olap()
        estatisticas = DesenvolvedoresService.calcular_estatisticas(desenvolvedores)

        print(f"DEBUG View: {len(desenvolvedores)} desenvolvedores carregados")

    except Exception as e:
        print(f"ERRO na view: {e}")
        desenvolvedores = []
        estatisticas = {
            "total_desenvolvedores": 0,
            "valor_medio": 0,
            "menor_valor": 0,
            "maior_valor": 0,
            "soma_total_valor_hora": 0,
        }

    context = {
        "header_context": header_context,
        "desenvolvedores": desenvolvedores,
        "estatisticas": estatisticas,
    }

    return render(request, "desenvolvedores/index.html", context)


@perfil_gerente_required
@require_http_methods(["GET"])
def get_dados_desenvolvedores(request):
    """API para buscar dados atualizados (AJAX)"""
    try:
        desenvolvedores = DesenvolvedoresService.get_desenvolvedores_olap()
        estatisticas = DesenvolvedoresService.calcular_estatisticas(desenvolvedores)

        return JsonResponse(
            {
                "success": True,
                "desenvolvedores": desenvolvedores,
                "estatisticas": estatisticas,
            }
        )
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@perfil_gerente_required
@require_http_methods(["POST"])
def atualizar_valor_hora(request):
    """API para atualizar valor/hora no OLTP"""
    try:
        data = json.loads(request.body)
        desenvolvedor_id = data.get("desenvolvedor_id")
        desenvolvedor_nome = data.get("desenvolvedor_nome")
        novo_valor_hora = data.get("valor_hora")
        contrato = data.get("contrato")

        print(f"DEBUG API Update: {desenvolvedor_nome} -> R$ {novo_valor_hora}")

        if not all([desenvolvedor_id, desenvolvedor_nome, novo_valor_hora, contrato]):
            return JsonResponse(
                {"success": False, "error": "Dados incompletos"}, status=400
            )

        try:
            novo_valor_hora = float(novo_valor_hora)
        except ValueError:
            return JsonResponse(
                {"success": False, "error": "Valor/hora inválido"}, status=400
            )

        sucesso = DesenvolvedoresService.atualizar_valor_hora_oltp(
            desenvolvedor_id, desenvolvedor_nome, novo_valor_hora, contrato
        )

        if sucesso:
            return JsonResponse(
                {
                    "success": True,
                    "message": f"Valor/hora de {desenvolvedor_nome} atualizado para R$ {novo_valor_hora:.2f}",
                }
            )
        return JsonResponse(
            {"success": False, "error": "Erro ao atualizar valor/hora"}, status=500
        )

    except Exception as e:
        print(f"DEBUG API Update: Erro - {e}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)
