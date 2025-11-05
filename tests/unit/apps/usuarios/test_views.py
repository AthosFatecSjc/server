"""Integration-style unit tests for Usuario views."""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.usuarios.models import ContratoChoices, PerfilAcessoChoices

Usuario = get_user_model()


@override_settings(
    MIDDLEWARE=[
        middleware
        for middleware in settings.MIDDLEWARE
        if "whitenoise.middleware.WhiteNoiseMiddleware" not in middleware
    ]
)
class UsuarioViewsTests(TestCase):
    """Comportamento das views públicas do módulo."""

    @classmethod
    def setUpTestData(cls):
        cls.membro = Usuario.objects.create_user(
            username="membro",
            nome_completo="Membro Ativo",
            email="membro@example.com",
            contrato=ContratoChoices.CLT,
            cargo="Analista",
            perfil_acesso=PerfilAcessoChoices.MEMBRO,
            password="Str0ng@123",
        )
        cls.lider = Usuario.objects.create_user(
            username="lider-view",
            nome_completo="Líder Inativo",
            email="liderview@example.com",
            contrato=ContratoChoices.ESTAGIARIO,
            cargo="Estagiário",
            perfil_acesso=PerfilAcessoChoices.LIDER,
            password="Str0ng@123",
            ativo=False,
        )

    def test_list_view_aplica_filtros(self):
        url = reverse("usuarios:lista")
        response = self.client.get(
            url,
            {
                "busca": "membro",
                "perfil_acesso": PerfilAcessoChoices.MEMBRO,
                "status": "ativo",
            },
        )
        self.assertEqual(response.status_code, 200)
        usuarios = list(response.context["usuarios"])
        self.assertEqual(usuarios, [self.membro])

    def test_status_toggle_view_desativa_usuario(self):
        url = reverse("usuarios:status", args=[self.membro.pk])
        response = self.client.post(url, {"acao": "desativar"})
        self.assertEqual(response.status_code, 302)
        self.membro.refresh_from_db()
        self.assertFalse(self.membro.ativo)

    def test_status_toggle_view_responde_acao_invalida(self):
        url = reverse("usuarios:status", args=[self.membro.pk])
        response = self.client.post(url, {"acao": "invalida"})
        self.assertEqual(response.status_code, 302)
        self.membro.refresh_from_db()
        self.assertTrue(self.membro.ativo)
