import json

from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from apps.usuarios.decorators import perfil_gerente_required

from .services import (
    DashboardProjetoError,
    DashboardProjetoPdfService,
    DashboardProjetoService,
    OrcamentoInvalidoError,
    ProjetoNaoEncontradoError,
)


def _json_error(message: str, status: int = 400) -> JsonResponse:
    return JsonResponse({"message": message}, status=status)


def _handle_pdf_exception(exc: Exception) -> JsonResponse:
    if isinstance(exc, ProjetoNaoEncontradoError):
        return _json_error(str(exc), status=404)
    if isinstance(exc, DashboardProjetoError):
        return _json_error(str(exc))
    return _json_error("Não foi possível gerar o PDF solicitado.", status=500)


@perfil_gerente_required
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


@perfil_gerente_required
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


@perfil_gerente_required
@csrf_protect
@require_http_methods(["POST"])
def exportar_relatorio_pdf(request):
    """Gera o PDF do dashboard de custos."""
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _json_error("JSON inválido.")

    projeto_id = payload.get("projeto_id")
    if projeto_id is None:
        return _json_error("O campo 'projeto_id' é obrigatório.")

    try:
        projeto_id_int = int(projeto_id)
    except (TypeError, ValueError):
        return _json_error("ID do projeto inválido.")

    try:
        dados_pdf = DashboardProjetoService.obter_dados_pdf(projeto_id_int)
        conteudo_pdf = DashboardProjetoPdfService.gerar_pdf(dados_pdf)
    except Exception as exc:  # pylint: disable=broad-except
        return _handle_pdf_exception(exc)

    nome_projeto_slug = slugify(dados_pdf.get("nome_projeto") or "projeto")
    data_suffix = timezone.now().strftime("%Y%m%d")
    filename = f"dashboard-custos-{nome_projeto_slug}-{data_suffix}.pdf"

    response = HttpResponse(conteudo_pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
