from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from django.http import HttpResponse
from django.test import RequestFactory, TestCase

from apps.dashboards.equipes import views
from apps.usuarios.models import PerfilAcessoChoices


class DashboardEquipesViewTests(TestCase):
    def setUp(self):
        self.rf = RequestFactory()

    def _fake_user(self, perfil):
        return SimpleNamespace(
            is_authenticated=True,
            perfil_acesso=perfil,
            get_username=lambda: "u",
        )

    @patch(
        "apps.dashboards.equipes.views.DashboardEquipesService.processar_filtros",
        return_value=(None, "", "", None),
    )
    @patch(
        "apps.dashboards.equipes.views.DashboardEquipesService.aplicar_filtros_horas"
    )
    @patch(
        "apps.dashboards.equipes.views.DashboardEquipesService.gerar_dados_grafico_horas",
        return_value=[{"data": "01/01", "Alice": 1}],
    )
    @patch(
        "apps.dashboards.equipes.views.DashboardEquipesService.get_desenvolvedores_dropdown",
        return_value=[{"name": "Alice", "color": "#0057B8", "selected": True}],
    )
    @patch(
        "apps.dashboards.equipes.views.DashboardEquipesService.contar_desenvolvedores_selecionados",
        return_value=1,
    )
    @patch(
        "apps.dashboards.equipes.views.DashboardEquipesService.get_projetos",
        return_value=[],
    )
    @patch(
        "apps.dashboards.equipes.views.DashboardEquipesService.get_header_context",
        return_value={"title": "t", "subtitle": "s", "breadcrumb": "b"},
    )
    def test_dashboard_equipes_permite_lider(
        self,
        _ctx,
        _proj,
        count_devs,
        dropdown,
        grafico,
        aplicar,
        _filtros,
    ):
        aplicar.return_value = ([], datetime(2024, 1, 1), datetime(2024, 1, 31))

        request = self.rf.get("/dashboards/equipes/")
        request.user = self._fake_user(PerfilAcessoChoices.LIDER)

        response: HttpResponse = views.dashboard_equipes(request)

        self.assertEqual(response.status_code, 200)
        count_devs.assert_called_once()
        grafico.assert_called_once()
        dropdown.assert_called_once()

    def test_dashboard_equipes_bloqueia_membro(self):
        request = self.rf.get("/dashboards/equipes/")
        request.user = self._fake_user(PerfilAcessoChoices.MEMBRO)

        response: HttpResponse = views.dashboard_equipes(request)

        self.assertEqual(response.status_code, 403)
