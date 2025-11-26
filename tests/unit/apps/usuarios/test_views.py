"""Integration-style unit tests for Usuario views."""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.contrib.messages import get_messages
from django.core.exceptions import ImproperlyConfigured
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from apps.usuarios.models import ContratoChoices, PerfilAcessoChoices
from apps.usuarios.views import UsuarioListView


def _ensure_secret_key():
    try:
        secret = settings.SECRET_KEY
    except ImproperlyConfigured:
        secret = ""
    if not secret:
        settings.SECRET_KEY = "test-secret-key"


_ensure_secret_key()

Usuario = get_user_model()


@override_settings(
    SECRET_KEY="test-secret-key",
    MIDDLEWARE=[
        middleware
        for middleware in settings.MIDDLEWARE
        if "whitenoise.middleware.WhiteNoiseMiddleware" not in middleware
    ],
)
class UsuarioViewsTests(TestCase):
    """Comportamento das views públicas do módulo."""

    @classmethod
    def setUpTestData(cls):
        cls.membro, _ = Usuario.objects.update_or_create(
            username="membro",
            defaults={
                "nome_completo": "Membro Ativo",
                "email": "membro@example.com",
                "contrato": ContratoChoices.CLT,
                "cargo": "Analista",
                "perfil_acesso": PerfilAcessoChoices.MEMBRO,
                "password": make_password("Str0ng@123"),
            },
        )

        cls.lider, _ = Usuario.objects.update_or_create(
            username="lider-view",
            defaults={
                "nome_completo": "Líder Inativo",
                "email": "liderview@example.com",
                "contrato": ContratoChoices.ESTAGIARIO,
                "cargo": "Estagiário",
                "perfil_acesso": PerfilAcessoChoices.LIDER,
                "password": make_password("Str0ng@123"),
                "ativo": False,
            },
        )

        cls.gerente, _ = Usuario.objects.update_or_create(
            username="gerente",
            defaults={
                "nome_completo": "Gerente Master",
                "email": "gerente@example.com",
                "contrato": ContratoChoices.CLT,
                "cargo": "Manager",
                "perfil_acesso": PerfilAcessoChoices.GERENTE,
                "password": make_password("Str0ng@123"),
            },
        )

    def setUp(self):
        self.client.force_login(self.gerente)
        self.factory = RequestFactory()

    def test_list_view_aplica_filtros(self):
        url = reverse("usuarios:lista")
        response = self.client.get(
            url,
            {
                "busca": self.membro.nome_completo,
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

    def test_status_toggle_view_nao_permite_alterar_proprio_status(self):
        url = reverse("usuarios:status", args=[self.gerente.pk])

        response = self.client.post(url, {"acao": "desativar"})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("usuarios:lista"))
        self.gerente.refresh_from_db()
        self.assertTrue(self.gerente.ativo)
        mensagens = [msg.message for msg in get_messages(response.wsgi_request)]
        self.assertIn("status do próprio usuário", " ".join(mensagens))

    def test_create_view_get_renderiza_formulario(self):
        response = self.client.get(reverse("usuarios:criar"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context)

    def test_create_view_post_invalido_exibe_erros(self):
        response = self.client.post(
            reverse("usuarios:criar"),
            {
                "nome_completo": "",
                "username": "",
                "email": "invalido",
                "contrato": "",
                "cargo": "",
                "perfil_acesso": "",
                "ativo": "True",
                "senha": "SenhaInvalida",
                "confirmar_senha": "OutraSenha",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)

    def test_lider_recebe_403_na_gestao(self):
        self.lider.ativo = True
        self.lider.save(update_fields=["ativo"])
        request = self.factory.get(reverse("usuarios:lista"))
        request.user = self.lider
        response = UsuarioListView.as_view()(request)
        self.assertEqual(response.status_code, 403)
        self.assertIn("Acesso não autorizado", response.content.decode())

    def test_update_view_get_renderiza_formulario(self):
        response = self.client.get(reverse("usuarios:editar", args=[self.membro.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context)

    def test_update_view_post_invalido_retorna_template(self):
        response = self.client.post(
            reverse("usuarios:editar", args=[self.membro.pk]),
            {
                "nome_completo": "Novo Nome",
                "username": self.membro.username,
                "email": self.membro.email,
                "contrato": self.membro.contrato,
                "cargo": "",
                "perfil_acesso": self.membro.perfil_acesso,
                "ativo": "True",
                "nova_senha": "NovaSenha@123",
                "confirmar_nova_senha": "OutraSenha@123",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)

    def test_detail_view_renderiza_usuario(self):
        response = self.client.get(reverse("usuarios:detalhe", args=[self.membro.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["usuario"], self.membro)

    def test_status_toggle_view_redireciona_para_next(self):
        next_url = reverse("usuarios:detalhe", args=[self.lider.pk])
        response = self.client.post(
            reverse("usuarios:status", args=[self.lider.pk]),
            {"acao": "ativar", "next": next_url},
        )
        self.assertEqual(response.status_code, 302)
        self.lider.refresh_from_db()
        self.assertTrue(self.lider.ativo)
        self.assertEqual(response.url, next_url)

    def test_status_toggle_view_ignora_next_externo(self):
        response = self.client.post(
            reverse("usuarios:status", args=[self.lider.pk]),
            {"acao": "ativar", "next": "https://malicioso.com/phish"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("usuarios:lista"))

    def test_delete_view_remove_usuario(self):
        usuario = Usuario.objects.create_user(
            username="excluir",
            nome_completo="Excluir Demo",
            email="excluir@example.com",
            contrato=ContratoChoices.CLT,
            cargo="Analista",
            perfil_acesso=PerfilAcessoChoices.MEMBRO,
            password="Str0ng@123",
        )

        response = self.client.post(reverse("usuarios:excluir", args=[usuario.pk]))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("usuarios:lista"))
        self.assertFalse(Usuario.objects.filter(pk=usuario.pk).exists())

    def test_delete_view_respeita_next_valido(self):
        usuario = Usuario.objects.create_user(
            username="excluir-next",
            nome_completo="Excluir Next",
            email="excluir-next@example.com",
            contrato=ContratoChoices.CLT,
            cargo="Analista",
            perfil_acesso=PerfilAcessoChoices.MEMBRO,
            password="Str0ng@123",
        )
        next_url = reverse("usuarios:detalhe", args=[self.membro.pk])

        response = self.client.post(
            reverse("usuarios:excluir", args=[usuario.pk]),
            {"next": next_url},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, next_url)

    def test_delete_view_nao_permite_auto_exclusao(self):
        self.client.force_login(self.gerente)

        response = self.client.post(reverse("usuarios:excluir", args=[self.gerente.pk]))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("usuarios:lista"))
        self.assertTrue(Usuario.objects.filter(pk=self.gerente.pk).exists())
