from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.relatorios.models import Cargo, Funcionario

Usuario = get_user_model()


class UsuarioSignalTests(TestCase):
    def setUp(self):
        Funcionario.objects.all().delete()
        Cargo.objects.all().delete()

    def test_salvar_usuario_atualiza_cargo_do_funcionario(self):
        Funcionario.objects.create(nome="Ana Dev")

        Usuario.objects.create_user(
            username="ana.dev",
            nome_completo="Ana Dev",
            email="ana@example.com",
            password="Secret123!",
            cargo="Dev Backend",
        )

        funcionario = Funcionario.objects.get(nome="Ana Dev")
        cargo = Cargo.objects.get(sigla="DEV_BACKEND")
        self.assertEqual(funcionario.cargo, cargo)

    def test_cargo_em_branco_remove_relacionamento(self):
        cargo = Cargo.objects.create(sigla="QA")
        Funcionario.objects.create(nome="Beto QA", cargo=cargo)

        usuario = Usuario.objects.create_user(
            username="beto.qa",
            nome_completo="Beto QA",
            email="beto@example.com",
            password="Secret123!",
            cargo="QA",
        )
        funcionario = Funcionario.objects.get(nome="Beto QA")
        self.assertEqual(funcionario.cargo, cargo)

        usuario.cargo = ""
        usuario.save()

        funcionario.refresh_from_db()
        self.assertIsNone(funcionario.cargo)
