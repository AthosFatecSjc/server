"""Unit tests for Usuario forms."""

from django import forms
from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.usuarios.forms import BaseUsuarioForm, UsuarioCreateForm, UsuarioUpdateForm
from apps.usuarios.models import ContratoChoices, PerfilAcessoChoices

Usuario = get_user_model()


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
                "ativo": "True",
                "senha": "Str0ng@123",
                "confirmar_senha": "Str0ng@123",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("Já existe um usuário com este e-mail.", form.errors["email"])

    def test_create_form_rejeita_username_duplicado(self):
        form = UsuarioCreateForm(
            data={
                "nome_completo": "Outro Usuário",
                "username": "existing",
                "email": "novo@example.com",
                "contrato": ContratoChoices.CLT,
                "cargo": "Gerente",
                "perfil_acesso": PerfilAcessoChoices.GERENTE,
                "ativo": "True",
                "senha": "Str0ng@123",
                "confirmar_senha": "Str0ng@123",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn(
            "Já existe um usuário com este username.", form.errors["username"]
        )

    def test_create_form_configura_status_padrao(self):
        form = UsuarioCreateForm()
        self.assertEqual(form.initial["ativo"], "True")

    def test_create_form_aplica_classe_para_checkbox(self):
        class DummyUsuarioForm(BaseUsuarioForm):
            aceita_termos = forms.BooleanField(required=False)

        form = DummyUsuarioForm()
        self.assertIn("h-4 w-4", form.fields["aceita_termos"].widget.attrs["class"])

    def test_create_form_senhas_divergentes(self):
        form = UsuarioCreateForm(
            data={
                "nome_completo": "Pessoa Nova",
                "username": "pessoa.nova",
                "email": "pessoa.nova@example.com",
                "contrato": ContratoChoices.CLT,
                "cargo": "Analista",
                "perfil_acesso": PerfilAcessoChoices.MEMBRO,
                "ativo": "True",
                "senha": "Str0ng@123",
                "confirmar_senha": "OutraSenha@123",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn(
            "As senhas informadas não coincidem.", form.errors["confirmar_senha"]
        )

    def test_create_form_salva_usuario_com_senha_hash(self):
        form = UsuarioCreateForm(
            data={
                "nome_completo": "Usuário Novo",
                "username": "novousuario",
                "email": "novo@example.com",
                "contrato": ContratoChoices.CLT,
                "cargo": "Analista",
                "perfil_acesso": PerfilAcessoChoices.MEMBRO,
                "ativo": "True",
                "senha": "Str0ng@123",
                "confirmar_senha": "Str0ng@123",
            }
        )
        self.assertTrue(form.is_valid())
        usuario = form.save()
        self.assertTrue(usuario.check_password("Str0ng@123"))

    def test_update_form_sem_nova_senha_mantem_credencial(self):
        form = UsuarioUpdateForm(
            data={
                "nome_completo": "Usuário Atualizado",
                "username": self.usuario_existente.username,
                "email": self.usuario_existente.email,
                "contrato": self.usuario_existente.contrato,
                "cargo": "Head de Tecnologia",
                "perfil_acesso": PerfilAcessoChoices.GERENTE,
                "ativo": "False",
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

    def test_update_form_com_nova_senha(self):
        form = UsuarioUpdateForm(
            data={
                "nome_completo": "Usuário Atualizado",
                "username": self.usuario_existente.username,
                "email": self.usuario_existente.email,
                "contrato": self.usuario_existente.contrato,
                "cargo": "Head de Tecnologia",
                "perfil_acesso": PerfilAcessoChoices.GERENTE,
                "ativo": "True",
                "nova_senha": "NovaSenha@123",
                "confirmar_nova_senha": "NovaSenha@123",
            },
            instance=self.usuario_existente,
        )
        self.assertTrue(form.is_valid())
        usuario_atualizado = form.save()
        self.assertTrue(usuario_atualizado.check_password("NovaSenha@123"))
