import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase

from apps.dashboards.projetos import views
from apps.dashboards.projetos.services import (
    DashboardProjetoError,
    OrcamentoInvalidoError,
    ProjetoNaoEncontradoError,
)


class DashboardProjetosViewsTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @patch("apps.dashboards.projetos.views.render")
    @patch(
        "apps.dashboards.projetos.views.DashboardProjetoService.montar_contexto_dashboard"
    )
    def test_index_monta_contexto_com_projeto_id_valido(
        self, mock_montar_contexto, mock_render
    ):
        mock_render.return_value = HttpResponse("ok")
        contexto = SimpleNamespace(
            projetos_dimensao=[{"id": 10, "nome": "Projeto X"}],
            dados_grafico={"labels": [], "values": [], "max_value": 0},
            projeto_selecionado_id=10,
            projeto_selecionado_nome="Projeto X",
        )
        mock_montar_contexto.return_value = contexto

        request = self.factory.get("/dashboard?projeto_id=10")
        response = views.index(request)

        self.assertEqual(response.status_code, 200)
        mock_montar_contexto.assert_called_once_with(10)
        _request, template_name, context = mock_render.call_args[0]
        self.assertEqual(template_name, "projeto/index.html")
        self.assertEqual(context["projetos_dimensao"], contexto.projetos_dimensao)
        self.assertEqual(context["dados_grafico"], contexto.dados_grafico)
        self.assertEqual(
            context["projeto_selecionado_id"], contexto.projeto_selecionado_id
        )
        self.assertEqual(
            context["projeto_selecionado_nome"], contexto.projeto_selecionado_nome
        )
        self.assertIn("header_context", context)

    @patch("apps.dashboards.projetos.views.render")
    @patch(
        "apps.dashboards.projetos.views.DashboardProjetoService.montar_contexto_dashboard"
    )
    def test_index_trata_projeto_id_invalido_como_none(
        self, mock_montar_contexto, mock_render
    ):
        mock_render.return_value = HttpResponse("ok")
        mock_montar_contexto.return_value = SimpleNamespace(
            projetos_dimensao=[],
            dados_grafico={},
            projeto_selecionado_id=None,
            projeto_selecionado_nome=None,
        )

        request = self.factory.get("/dashboard?projeto_id=foobar")
        views.index(request)

        mock_montar_contexto.assert_called_once_with(None)

    @patch(
        "apps.dashboards.projetos.views.DashboardProjetoService.atualizar_orcamento_previsto"
    )
    def test_atualizar_orcamento_previsto_sucesso(self, mock_atualizar):
        mock_atualizar.return_value = {"status": "ok"}
        payload = json.dumps({"valor": 123})
        request = self.factory.post(
            "/projetos/1/orcamento",
            data=payload,
            content_type="application/json",
        )
        request.csrf_processing_done = True

        response = views.atualizar_orcamento_previsto(request, 1)

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {"status": "ok"})
        mock_atualizar.assert_called_once_with(1, 123)

    def test_atualizar_orcamento_previsto_json_invalido(self):
        request = self.factory.post(
            "/projetos/1/orcamento",
            data=b"{invalid-json",
            content_type="application/json",
        )
        request.csrf_processing_done = True

        response = views.atualizar_orcamento_previsto(request, 1)

        self.assertEqual(response.status_code, 400)
        self.assertJSONEqual(response.content, {"message": "JSON inválido."})

    @patch(
        "apps.dashboards.projetos.views.DashboardProjetoService.atualizar_orcamento_previsto"
    )
    def test_atualizar_orcamento_previsto_erros_especificos(self, mock_atualizar):
        mock_atualizar.side_effect = [
            ProjetoNaoEncontradoError("Projeto não encontrado"),
            OrcamentoInvalidoError("Valor inválido"),
            DashboardProjetoError("Erro genérico"),
        ]

        payload = json.dumps({"valor": 100})

        # Projeto não encontrado
        request = self.factory.post(
            "/projetos/1/orcamento",
            data=payload,
            content_type="application/json",
        )
        request.csrf_processing_done = True
        response = views.atualizar_orcamento_previsto(request, 1)
        self.assertEqual(response.status_code, 404)
        self.assertJSONEqual(response.content, {"message": "Projeto não encontrado"})

        # Orcamento inválido
        request = self.factory.post(
            "/projetos/1/orcamento",
            data=payload,
            content_type="application/json",
        )
        request.csrf_processing_done = True
        response = views.atualizar_orcamento_previsto(request, 1)
        self.assertEqual(response.status_code, 400)
        self.assertJSONEqual(response.content, {"message": "Valor inválido"})

        # Erro genérico do dashboard
        request = self.factory.post(
            "/projetos/1/orcamento",
            data=payload,
            content_type="application/json",
        )
        request.csrf_processing_done = True
        response = views.atualizar_orcamento_previsto(request, 1)
        self.assertEqual(response.status_code, 400)
        self.assertJSONEqual(response.content, {"message": "Erro genérico"})

    @patch("apps.dashboards.projetos.views.timezone")
    @patch("apps.dashboards.projetos.views.DashboardProjetoPdfService.gerar_pdf")
    @patch("apps.dashboards.projetos.views.DashboardProjetoService.obter_dados_pdf")
    def test_exportar_relatorio_pdf_sucesso(
        self, mock_obter_pdf, mock_gerar_pdf, mock_timezone
    ):
        mock_obter_pdf.return_value = {"nome_projeto": "Projeto Especial"}
        mock_gerar_pdf.return_value = b"%PDF-1.4"
        mock_timezone.now.return_value = MagicMock(strftime=lambda fmt: "20240102")

        payload = json.dumps({"projeto_id": 5})
        request = self.factory.post(
            "/projetos/exportar",
            data=payload,
            content_type="application/json",
        )
        request.csrf_processing_done = True

        response = views.exportar_relatorio_pdf(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn(
            "dashboard-custos-projeto-especial-20240102.pdf",
            response["Content-Disposition"],
        )
        self.assertEqual(response.content, b"%PDF-1.4")
        mock_obter_pdf.assert_called_once_with(5)
        mock_gerar_pdf.assert_called_once_with({"nome_projeto": "Projeto Especial"})

    def test_exportar_relatorio_pdf_json_invalido(self):
        request = self.factory.post(
            "/projetos/exportar",
            data=b"{invalid-json",
            content_type="application/json",
        )
        request.csrf_processing_done = True

        response = views.exportar_relatorio_pdf(request)
        self.assertEqual(response.status_code, 400)
        self.assertJSONEqual(response.content, {"message": "JSON inválido."})

    def test_exportar_relatorio_pdf_sem_projeto_id(self):
        payload = json.dumps({})
        request = self.factory.post(
            "/projetos/exportar",
            data=payload,
            content_type="application/json",
        )
        request.csrf_processing_done = True

        response = views.exportar_relatorio_pdf(request)
        self.assertEqual(response.status_code, 400)
        self.assertJSONEqual(
            response.content, {"message": "O campo 'projeto_id' é obrigatório."}
        )

    def test_exportar_relatorio_pdf_projeto_id_invalido(self):
        payload = json.dumps({"projeto_id": "abc"})
        request = self.factory.post(
            "/projetos/exportar",
            data=payload,
            content_type="application/json",
        )
        request.csrf_processing_done = True

        response = views.exportar_relatorio_pdf(request)
        self.assertEqual(response.status_code, 400)
        self.assertJSONEqual(response.content, {"message": "ID do projeto inválido."})

    @patch("apps.dashboards.projetos.views.DashboardProjetoService.obter_dados_pdf")
    def test_exportar_relatorio_pdf_trata_excecoes_especificas(self, mock_obter_pdf):
        mock_obter_pdf.side_effect = ProjetoNaoEncontradoError("Projeto não encontrado")
        payload = json.dumps({"projeto_id": 1})
        request = self.factory.post(
            "/projetos/exportar",
            data=payload,
            content_type="application/json",
        )
        request.csrf_processing_done = True

        response = views.exportar_relatorio_pdf(request)
        self.assertEqual(response.status_code, 404)
        self.assertJSONEqual(response.content, {"message": "Projeto não encontrado"})

        mock_obter_pdf.side_effect = DashboardProjetoError("Erro no dashboard")
        request = self.factory.post(
            "/projetos/exportar",
            data=payload,
            content_type="application/json",
        )
        request.csrf_processing_done = True

        response = views.exportar_relatorio_pdf(request)
        self.assertEqual(response.status_code, 400)
        self.assertJSONEqual(response.content, {"message": "Erro no dashboard"})

    @patch("apps.dashboards.projetos.views.DashboardProjetoPdfService.gerar_pdf")
    @patch("apps.dashboards.projetos.views.DashboardProjetoService.obter_dados_pdf")
    def test_exportar_relatorio_pdf_trata_excecao_na_geracao(
        self, mock_obter_pdf, mock_gerar_pdf
    ):
        mock_obter_pdf.return_value = {"nome_projeto": "Projeto Sem PDF"}
        mock_gerar_pdf.side_effect = RuntimeError("Falha inesperada")

        payload = json.dumps({"projeto_id": 3})
        request = self.factory.post(
            "/projetos/exportar",
            data=payload,
            content_type="application/json",
        )
        request.csrf_processing_done = True

        response = views.exportar_relatorio_pdf(request)
        self.assertEqual(response.status_code, 500)
        self.assertJSONEqual(
            response.content,
            {"message": "Não foi possível gerar o PDF solicitado."},
        )
