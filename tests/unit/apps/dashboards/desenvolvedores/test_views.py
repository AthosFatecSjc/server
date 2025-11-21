import json
from unittest.mock import patch

from django.http import HttpRequest
from django.test import RequestFactory, SimpleTestCase
from django.urls import resolve, reverse

from apps.dashboards.desenvolvedores import urls as desenvolvedores_urls
from apps.dashboards.desenvolvedores import views
from apps.usuarios.models import PerfilAcessoChoices


class DesenvolvedoresUrlsTests(SimpleTestCase):
    def test_urlpatterns_expostos(self):
        self.assertIsNotNone(desenvolvedores_urls.urlpatterns)
        resolver = resolve("/dashboards/desenvolvedores/")
        self.assertEqual(resolver.url_name, "desenvolvedores_index")


class DesenvolvedoresViewsTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = type(
            "User",
            (),
            {
                "is_authenticated": True,
                "perfil_acesso": PerfilAcessoChoices.GERENTE,
            },
        )()

    def _with_user(self, request):
        request.user = self.user
        return request

    @patch(
        "apps.dashboards.desenvolvedores.views.DesenvolvedoresService.calcular_estatisticas"
    )
    @patch(
        "apps.dashboards.desenvolvedores.views.DesenvolvedoresService.get_desenvolvedores_olap"
    )
    @patch("apps.dashboards.desenvolvedores.views.render")
    def test_index_sucesso(self, mock_render, mock_get_dev, mock_calc):
        mock_render.return_value = HttpRequest()
        mock_get_dev.return_value = [{"nome": "Alice"}]
        mock_calc.return_value = {"total_desenvolvedores": 1}

        request = self._with_user(self.factory.get("/desenvolvedores/"))
        views.index(request)

        mock_get_dev.assert_called_once()
        mock_calc.assert_called_once()
        mock_render.assert_called_once()

    @patch(
        "apps.dashboards.desenvolvedores.views.DesenvolvedoresService.calcular_estatisticas"
    )
    @patch(
        "apps.dashboards.desenvolvedores.views.DesenvolvedoresService.get_desenvolvedores_olap"
    )
    @patch("apps.dashboards.desenvolvedores.views.render")
    def test_index_trata_excecao(self, mock_render, mock_get_dev, mock_calc):
        mock_render.return_value = HttpRequest()
        mock_get_dev.side_effect = RuntimeError("falha")

        request = self._with_user(self.factory.get("/desenvolvedores/"))
        views.index(request)

        mock_calc.assert_not_called()
        mock_render.assert_called_once()
        _, _, context = mock_render.call_args[0]
        self.assertEqual(context["estatisticas"]["total_desenvolvedores"], 0)

    @patch(
        "apps.dashboards.desenvolvedores.views.DesenvolvedoresService.calcular_estatisticas"
    )
    @patch(
        "apps.dashboards.desenvolvedores.views.DesenvolvedoresService.get_desenvolvedores_olap"
    )
    def test_get_dados_desenvolvedores_ok(self, mock_get_dev, mock_calc):
        mock_get_dev.return_value = []
        mock_calc.return_value = {"total_desenvolvedores": 0}

        request = self._with_user(self.factory.get("/desenvolvedores/dados/"))
        response = views.get_dados_desenvolvedores(request)

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            response.content,
            {
                "success": True,
                "desenvolvedores": [],
                "estatisticas": {"total_desenvolvedores": 0},
            },
        )

    @patch(
        "apps.dashboards.desenvolvedores.views.DesenvolvedoresService.get_desenvolvedores_olap"
    )
    def test_get_dados_desenvolvedores_erro(self, mock_get_dev):
        mock_get_dev.side_effect = RuntimeError("falha")
        request = self._with_user(self.factory.get("/desenvolvedores/dados/"))

        response = views.get_dados_desenvolvedores(request)

        self.assertEqual(response.status_code, 500)
        self.assertJSONEqual(response.content, {"success": False, "error": "falha"})

    @patch(
        "apps.dashboards.desenvolvedores.views.DesenvolvedoresService.atualizar_valor_hora_oltp"
    )
    def test_atualizar_valor_hora_sucesso(self, mock_atualizar):
        mock_atualizar.return_value = True
        payload = {
            "desenvolvedor_id": 1,
            "desenvolvedor_nome": "Alice",
            "valor_hora": 100,
            "contrato": "CLT",
        }
        request = self._with_user(
            self.factory.post(
                reverse("atualizar_valor_hora"),
                data=json.dumps(payload),
                content_type="application/json",
            )
        )

        response = views.atualizar_valor_hora(request)

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn("atualizado para R$ 100.00", data["message"])
        mock_atualizar.assert_called_once_with(1, "Alice", 100.0, "CLT")

    def test_atualizar_valor_hora_dados_incompletos(self):
        request = self._with_user(
            self.factory.post(
                reverse("atualizar_valor_hora"),
                data=json.dumps({"desenvolvedor_id": 1}),
                content_type="application/json",
            )
        )

        response = views.atualizar_valor_hora(request)

        self.assertEqual(response.status_code, 400)
        self.assertJSONEqual(
            response.content, {"success": False, "error": "Dados incompletos"}
        )

    def test_atualizar_valor_hora_valor_invalido(self):
        payload = {
            "desenvolvedor_id": 1,
            "desenvolvedor_nome": "Alice",
            "valor_hora": "abc",
            "contrato": "CLT",
        }
        request = self._with_user(
            self.factory.post(
                reverse("atualizar_valor_hora"),
                data=json.dumps(payload),
                content_type="application/json",
            )
        )

        response = views.atualizar_valor_hora(request)

        self.assertEqual(response.status_code, 400)
        self.assertJSONEqual(
            response.content, {"success": False, "error": "Valor/hora inválido"}
        )

    @patch(
        "apps.dashboards.desenvolvedores.views.DesenvolvedoresService.atualizar_valor_hora_oltp"
    )
    def test_atualizar_valor_hora_falha_service(self, mock_atualizar):
        mock_atualizar.return_value = False
        payload = {
            "desenvolvedor_id": 1,
            "desenvolvedor_nome": "Alice",
            "valor_hora": 50,
            "contrato": "CLT",
        }
        request = self._with_user(
            self.factory.post(
                reverse("atualizar_valor_hora"),
                data=json.dumps(payload),
                content_type="application/json",
            )
        )

        response = views.atualizar_valor_hora(request)

        self.assertEqual(response.status_code, 500)
        self.assertJSONEqual(
            response.content,
            {"success": False, "error": "Erro ao atualizar valor/hora"},
        )

    @patch(
        "apps.dashboards.desenvolvedores.views.DesenvolvedoresService.atualizar_valor_hora_oltp"
    )
    def test_atualizar_valor_hora_trata_excecao(self, mock_atualizar):
        mock_atualizar.side_effect = RuntimeError("boom")
        payload = {
            "desenvolvedor_id": 1,
            "desenvolvedor_nome": "Alice",
            "valor_hora": 50,
            "contrato": "CLT",
        }
        request = self._with_user(
            self.factory.post(
                reverse("atualizar_valor_hora"),
                data=json.dumps(payload),
                content_type="application/json",
            )
        )

        response = views.atualizar_valor_hora(request)

        self.assertEqual(response.status_code, 500)
        self.assertJSONEqual(response.content, {"success": False, "error": "boom"})
