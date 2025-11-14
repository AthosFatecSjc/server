from unittest.mock import MagicMock, patch

from django.test import RequestFactory, SimpleTestCase
from django.urls import resolve, reverse

from apps.dashboards import urls as dashboards_urls
from apps.dashboards import views


class DashboardsUrlsTests(SimpleTestCase):
    def test_urlpatterns(self):
        self.assertTrue(dashboards_urls.urlpatterns)
        resolver = resolve("/dashboards/")
        self.assertEqual(resolver.url_name, "dashboards_index")


class DashboardsIndexViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @patch("apps.dashboards.views.render")
    def test_index_retorna_contexto(self, mock_render):
        mock_render.return_value = MagicMock(status_code=200)
        request = self.factory.get(reverse("dashboards_index"))

        response = views.index(request)

        mock_render.assert_called_once()
        _, _, context = mock_render.call_args[0]
        self.assertIn("dashboards", context)
        self.assertEqual(len(context["dashboards"]), 3)
        self.assertEqual(response.status_code, 200)
