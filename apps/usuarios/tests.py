"""Testes automatizados do módulo de usuários."""

from __future__ import annotations

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.relatorios.models import ContratoChoices, PerfilAcessoChoices

from .forms import UsuarioCreateForm, UsuarioUpdateForm
from .services import alterar_status_usuario, listar_usuarios

Usuario = get_user_model()


class UsuarioModelTests(TestCase):
    """Cenários focados no modelo customizado."""

    def test_salvar_sincroniza_is_active(self):
        usuario = Usuario.objects.create_user(
            username="janedoe",
            nome_completo="Jane Doe",
            email="jane@example.com",
            contrato=ContratoChoices.CLT,
            cargo="Gerente de Projeto",
            perfil_acesso=PerfilAcessoChoices.GERENTE,
            password="Str0ng@123",
        )
        self.assertTrue(usuario.ativo)
        self.assertTrue(usuario.is_active)

        usuario.ativo = False
        usuario.save()
        usuario.refresh_from_db()

        self.assertFalse(usuario.ativo)
        self.assertFalse(usuario.is_active)


class UsuarioFormTests(TestCase):
    """Validações dos formulários de criação e edição."""

    def setUp(self):
        self.usuario_existente = Usuario.objects.create_user(
            username="existing",
            nome_completo="Usuário Existente",
            email="existente@example.com",
            contrato=ContratoChoices.CLT,
            cargo="Líder Técnico",
            perfil_acesso=PerfilAcessoChoices.LIDER,
            password="Str0ng@123",
        )

    def test_create_form_rejeita_email_duplicado(self):
        form = UsuarioCreateForm(
            data={
                "nome_completo": "Outro Usuário",
                "username": "otheruser",
                "email": "EXISTENTE@example.com",
                "contrato": ContratoChoices.ESTAGIARIO,
                "cargo": "Estagiário",
                "perfil_acesso": PerfilAcessoChoices.MEMBRO,
                "ativo": True,
                "senha": "Str0ng@123",
                "confirmar_senha": "Str0ng@123",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("Já existe um usuário com este e-mail.", form.errors["email"])

    def test_update_form_sem_nova_senha_mantem_credencial(self):
        form = UsuarioUpdateForm(
            data={
                "nome_completo": "Usuário Atualizado",
                "username": self.usuario_existente.username,
                "email": self.usuario_existente.email,
                "contrato": self.usuario_existente.contrato,
                "cargo": "Head de Tecnologia",
                "perfil_acesso": PerfilAcessoChoices.GERENTE,
                "ativo": False,
                "nova_senha": "",
                "confirmar_nova_senha": "",
            },
            instance=self.usuario_existente,
        )
        self.assertTrue(form.is_valid())
        usuario_atualizado = form.save()
        self.assertFalse(usuario_atualizado.ativo)
        # Confirma que a senha antiga continua válida.
        self.assertTrue(usuario_atualizado.check_password("Str0ng@123"))


class UsuarioServiceTests(TestCase):
    """Cobertura das regras encapsuladas nos serviços."""

    @classmethod
    def setUpTestData(cls):
        cls.ativo = Usuario.objects.create_user(
            username="ativo",
            nome_completo="Usuário Ativo",
            email="ativo@example.com",
            contrato=ContratoChoices.CLT,
            cargo="Desenvolvedor",
            perfil_acesso=PerfilAcessoChoices.MEMBRO,
            password="Str0ng@123",
        )
        cls.inativo = Usuario.objects.create_user(
            username="inativo",
            nome_completo="Usuário Inativo",
            email="inativo@example.com",
            contrato=ContratoChoices.ESTAGIARIO,
            cargo="Estagiário",
            perfil_acesso=PerfilAcessoChoices.MEMBRO,
            password="Str0ng@123",
            ativo=False,
        )
        cls.lider = Usuario.objects.create_user(
            username="lider",
            nome_completo="Usuário Líder",
            email="lider@example.com",
            contrato=ContratoChoices.CLT,
            cargo="Líder Técnico",
            perfil_acesso=PerfilAcessoChoices.LIDER,
            password="Str0ng@123",
        )

    def test_listar_usuarios_filtra_por_status(self):
        apenas_ativos = listar_usuarios({"status": "ativo"})
        self.assertQuerySetEqual(
            apenas_ativos,
            [self.ativo, self.lider],
            ordered=False,
            transform=lambda x: x,
        )

        apenas_inativos = listar_usuarios({"status": "inativo"})
        self.assertQuerySetEqual(
            apenas_inativos,
            [self.inativo],
            ordered=False,
            transform=lambda x: x,
        )

    def test_alterar_status_usuario(self):
        alterar_status_usuario(self.ativo, ativo=False)
        self.ativo.refresh_from_db()
        self.assertFalse(self.ativo.ativo)
        self.assertFalse(self.ativo.is_active)


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
