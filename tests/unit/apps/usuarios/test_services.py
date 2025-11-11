"""Unit tests for Usuario service layer."""

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.usuarios.models import ContratoChoices, PerfilAcessoChoices
from apps.usuarios.services import (
    alterar_status_usuario,
    listar_usuarios,
    obter_usuario_por_pk,
)

Usuario = get_user_model()


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
            username="lider-test",
            nome_completo="Usuário Líder",
            email="lider@example.com",
            contrato=ContratoChoices.CLT,
            cargo="Líder Técnico",
            perfil_acesso=PerfilAcessoChoices.LIDER,
            password="Str0ng@123",
        )

    def test_listar_usuarios_filtra_por_status(self):
        apenas_ativos = listar_usuarios({"status": "ativo"}).filter(
            username__in=[self.ativo.username, self.lider.username]
        )
        self.assertQuerySetEqual(
            apenas_ativos,
            [self.ativo, self.lider],
            ordered=False,
            transform=lambda x: x,
        )

        apenas_inativos = listar_usuarios({"status": "inativo"})
        self.assertIn(self.inativo, apenas_inativos)
        self.assertNotIn(self.ativo, apenas_inativos)

    def test_alterar_status_usuario(self):
        alterar_status_usuario(self.ativo, ativo=False)
        self.ativo.refresh_from_db()
        self.assertFalse(self.ativo.ativo)
        self.assertFalse(self.ativo.is_active)

    def test_obter_usuario_por_pk(self):
        usuario = obter_usuario_por_pk(self.ativo.pk)
        self.assertEqual(usuario, self.ativo)
