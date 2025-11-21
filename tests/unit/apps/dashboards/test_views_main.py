from unittest.mock import MagicMock, patch

from django.test import RequestFactory, SimpleTestCase
from django.urls import resolve, reverse

from apps.dashboards import urls as dashboards_urls
from apps.dashboards import views
from apps.usuarios.models import PerfilAcessoChoices


class DashboardsUrlsTests(SimpleTestCase):
    def test_urlpatterns(self):
        self.assertTrue(dashboards_urls.urlpatterns)
        resolver = resolve("/dashboards/")
        self.assertEqual(resolver.url_name, "dashboards_index")


class DashboardsIndexViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @patch("apps.dashboards.views.render")
    def test_index_retorna_contexto_para_gerente(self, mock_render):
        mock_render.return_value = MagicMock(status_code=200)
        request = self.factory.get(reverse("dashboards_index"))
        request.user = MagicMock(
            is_authenticated=True, perfil_acesso=PerfilAcessoChoices.GERENTE
        )

        response = views.index(request)

        mock_render.assert_called_once()
        _, _, context = mock_render.call_args[0]
        self.assertIn("dashboards", context)
        self.assertEqual(len(context["dashboards"]), 3)
        self.assertEqual(response.status_code, 200)

    @patch("apps.dashboards.views.render")
    def test_index_exibe_dashboards_para_lider(self, mock_render):
        mock_render.return_value = MagicMock(status_code=200)
        request = self.factory.get(reverse("dashboards_index"))
        request.user = MagicMock(
            is_authenticated=True, perfil_acesso=PerfilAcessoChoices.LIDER
        )

        response = views.index(request)

        mock_render.assert_called_once()
        _, _, context = mock_render.call_args[0]
        self.assertEqual(len(context["dashboards"]), 2)
        self.assertEqual(response.status_code, 200)

    @patch("apps.dashboards.views.render")
    def test_index_exibe_apenas_saude_para_membro(self, mock_render):
        mock_render.return_value = MagicMock(status_code=200)
        request = self.factory.get(reverse("dashboards_index"))
        request.user = MagicMock(
            is_authenticated=True, perfil_acesso=PerfilAcessoChoices.MEMBRO
        )

        response = views.index(request)

        mock_render.assert_called_once()
        _, _, context = mock_render.call_args[0]
        self.assertEqual(len(context["dashboards"]), 1)
        self.assertEqual(response.status_code, 200)
