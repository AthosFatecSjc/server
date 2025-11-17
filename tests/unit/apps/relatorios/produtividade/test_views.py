import json
from unittest import mock

from django.http import HttpRequest
from django.test import RequestFactory, SimpleTestCase

from apps.relatorios.produtividade import views


class ProdutividadeViewsTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @mock.patch("apps.relatorios.produtividade.views.render")
    @mock.patch(
        "apps.relatorios.produtividade.views.calcular_spends_por_dev_com_legendas"
    )
    @mock.patch("apps.relatorios.produtividade.views.listar_equipes_disponiveis")
    @mock.patch("apps.relatorios.produtividade.views.listar_meses_disponiveis")
    def test_index_renderiza_contexto(
        self, mock_meses, mock_equipes, mock_spends, mock_render
    ):
        mock_render.return_value = HttpRequest()
        mock_meses.return_value = [{"mes": 7, "ano": 2025, "mes_nome": "Julho"}]
        mock_equipes.return_value = ["Equipe Azul"]
        mock_spends.return_value = {"dias": [1], "resultados": []}

        request = self.factory.get("/relatorios/produtividade/")
        views.index(request)

        mock_render.assert_called_once()
        _, _, context = mock_render.call_args[0]
        self.assertEqual(context["mes"], 7)
        self.assertEqual(context["equipes"], ["Equipe Azul"])

    @mock.patch("apps.relatorios.produtividade.views.exportar_produtividade_pdf")
    @mock.patch(
        "apps.relatorios.produtividade.views.calcular_spends_por_dev_com_legendas"
    )
    def test_exportar_pdf(self, mock_spends, mock_pdf):
        mock_spends.return_value = {"resultados": []}
        mock_pdf.return_value = b"pdf"
        request = self.factory.get(
            "/relatorios/produtividade/exportar-pdf/?mes=7&ano=2025"
        )

        response = views.exportar_pdf(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"pdf", response.content)

    @mock.patch("apps.relatorios.produtividade.views.atualizar_multiplos_dias")
    def test_atualizar_legenda_retorna_json(self, mock_service):
        mock_service.return_value = (True, None)
        payload = {
            "funcionario_id": 1,
            "mes": 7,
            "ano": 2025,
            "dias": [1],
            "codigo": "FE",
        }
        request = self.factory.post(
            "/relatorios/produtividade/atualizar-legenda/",
            data=json.dumps(payload),
            content_type="application/json",
        )

        response = views.atualizar_legenda(request)
        self.assertJSONEqual(response.content, {"success": True, "error": None})

    @mock.patch("apps.relatorios.produtividade.views.atualizar_multiplos_dias")
    def test_atualizar_legenda_erro(self, mock_service):
        mock_service.return_value = (False, "falha")
        payload = {
            "funcionario_id": 1,
            "mes": 7,
            "ano": 2025,
            "dias": [1],
            "codigo": "FE",
        }
        request = self.factory.post(
            "/relatorios/produtividade/atualizar-legenda/",
            data=json.dumps(payload),
            content_type="application/json",
        )

        response = views.atualizar_legenda(request)
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {"success": False, "error": "falha"})

    @mock.patch("apps.relatorios.produtividade.views.atualizar_meta_funcionario")
    def test_atualizar_meta(self, mock_meta):
        mock_meta.return_value = True
        payload = {"funcionario_id": 1, "mes": 7, "ano": 2025, "meta": 150}
        request = self.factory.post(
            "/relatorios/produtividade/atualizar-meta/",
            data=json.dumps(payload),
            content_type="application/json",
        )
        response = views.atualizar_meta(request)
        self.assertJSONEqual(response.content, {"success": True})

    @mock.patch("apps.relatorios.produtividade.views.atualizar_meta_funcionario")
    def test_atualizar_meta_erro(self, mock_meta):
        mock_meta.side_effect = RuntimeError("erro")
        payload = {"funcionario_id": 1, "mes": 7, "ano": 2025, "meta": 150}
        request = self.factory.post(
            "/relatorios/produtividade/atualizar-meta/",
            data=json.dumps(payload),
            content_type="application/json",
        )
        response = views.atualizar_meta(request)
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {"success": False, "error": "erro"})
