import json

from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from .services import (
    DashboardProjetoError,
    DashboardProjetoPdfService,
    DashboardProjetoService,
    OrcamentoInvalidoError,
    ProjetoNaoEncontradoError,
)


@require_http_methods(["GET"])
def index(request):
    """View principal do dashboard de saúde do projeto."""
    projeto_param = request.GET.get("projeto_id")

    try:
        projeto_id = int(projeto_param) if projeto_param is not None else None
    except (TypeError, ValueError):
        projeto_id = None

    header_context = {
        "title": "Dashboard de Saúde do Projeto",
        "subtitle": "Análise financeira e operacional do projeto",
        "breadcrumb": "Saúde do Projeto",
    }

    contexto = DashboardProjetoService.montar_contexto_dashboard(projeto_id)

    context = {
        "header_context": header_context,
        "projetos_dimensao": contexto.projetos_dimensao,
        "dados_grafico": contexto.dados_grafico,
        "projeto_selecionado_id": contexto.projeto_selecionado_id,
        "projeto_selecionado_nome": contexto.projeto_selecionado_nome,
    }

    return render(request, "projeto/index.html", context)


@csrf_protect
@require_http_methods(["POST"])
def atualizar_orcamento_previsto(request, projeto_id: int):
    """Atualiza o orçamento previsto de um projeto no banco OLTP."""
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"message": "JSON inválido."}, status=400)

    try:
        resultado = DashboardProjetoService.atualizar_orcamento_previsto(
            projeto_id, payload.get("valor")
        )
    except ProjetoNaoEncontradoError as exc:
        return JsonResponse({"message": str(exc)}, status=404)
    except OrcamentoInvalidoError as exc:
        return JsonResponse({"message": str(exc)}, status=400)
    except DashboardProjetoError as exc:
        return JsonResponse({"message": str(exc)}, status=400)

    return JsonResponse(resultado)


@csrf_protect
@require_http_methods(["POST"])
def exportar_relatorio_pdf(request):
    """Gera o PDF do dashboard de custos."""
    error_message = None
    status_code = 400

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        error_message = "JSON inválido."

    if error_message is None:
        projeto_id = payload.get("projeto_id")
        if projeto_id is None:
            error_message = "O campo 'projeto_id' é obrigatório."
        else:
            try:
                projeto_id_int = int(projeto_id)
            except (TypeError, ValueError):
                error_message = "ID do projeto inválido."

    if error_message is None:
        try:
            dados_pdf = DashboardProjetoService.obter_dados_pdf(projeto_id_int)
            conteudo_pdf = DashboardProjetoPdfService.gerar_pdf(dados_pdf)
        except ProjetoNaoEncontradoError as exc:
            error_message = str(exc)
            status_code = 404
        except DashboardProjetoError as exc:
            error_message = str(exc)
        except Exception:
            error_message = "Não foi possível gerar o PDF solicitado."
            status_code = 500

    if error_message is not None:
        return JsonResponse({"message": error_message}, status=status_code)

    nome_projeto_slug = slugify(dados_pdf.get("nome_projeto") or "projeto")
    data_suffix = timezone.now().strftime("%Y%m%d")
    filename = f"dashboard-custos-{nome_projeto_slug}-{data_suffix}.pdf"

    response = HttpResponse(conteudo_pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
