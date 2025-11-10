"""Unit tests for the custom Usuario model."""

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.usuarios.models import ContratoChoices, PerfilAcessoChoices

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

    def test_str_retorna_nome_completo(self):
        usuario = Usuario.objects.create_user(
            username="apelido",
            nome_completo="Nome Completo",
            email="apelido@example.com",
            contrato=ContratoChoices.CLT,
            cargo="Analista",
            perfil_acesso=PerfilAcessoChoices.MEMBRO,
            password="Str0ng@123",
        )
        self.assertEqual(str(usuario), "Nome Completo")
