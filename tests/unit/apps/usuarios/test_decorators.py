"""Tests for perfil access decorators."""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponse
from django.test import RequestFactory, TestCase

from apps.usuarios.decorators import (
    FORBIDDEN_MESSAGE,
    perfil_gerente_required,
    perfil_lider_required,
    perfil_membro_or_above_required,
)
from apps.usuarios.models import PerfilAcessoChoices


class PerfilDecoratorsTests(TestCase):
    """Behavior of the access control decorators."""

    def setUp(self):
        self.factory = RequestFactory()
        self.user_model = get_user_model()
        self.gerente = self.user_model.objects.create_user(
            username="decor-gerente",
            email="decor-gerente@example.com",
            nome_completo="Decor Gerente",
            perfil_acesso=PerfilAcessoChoices.GERENTE,
            password="Str0ng@123",
        )
        self.lider = self.user_model.objects.create_user(
            username="decor-lider",
            email="decor-lider@example.com",
            nome_completo="Decor Lider",
            perfil_acesso=PerfilAcessoChoices.LIDER,
            password="Str0ng@123",
        )
        self.membro = self.user_model.objects.create_user(
            username="decor-membro",
            email="decor-membro@example.com",
            nome_completo="Decor Membro",
            perfil_acesso=PerfilAcessoChoices.MEMBRO,
            password="Str0ng@123",
        )

    def test_perfil_gerente_required_redirects_anonymous(self):
        @perfil_gerente_required
        def sample_view(_request):
            return HttpResponse("ok")

        request = self.factory.get("/alguma-url/")
        request.user = AnonymousUser()

        response = sample_view(request)

        self.assertEqual(response.status_code, 302)
        self.assertIn(settings.LOGIN_URL, response.headers["Location"])

    def test_perfil_gerente_required_blocks_non_gerente(self):
        @perfil_gerente_required
        def sample_view(_request):
            return HttpResponse("ok")

        request = self.factory.get("/alguma-url/")
        request.user = self.lider

        response = sample_view(request)

        self.assertEqual(response.status_code, 403)
        self.assertIn(FORBIDDEN_MESSAGE, response.content.decode())

    def test_perfil_gerente_required_allows_gerente(self):
        @perfil_gerente_required
        def sample_view(_request):
            return HttpResponse("ok")

        request = self.factory.get("/alguma-url/")
        request.user = self.gerente

        response = sample_view(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"ok")

    def test_perfil_lider_required_allows_lider_and_gerente(self):
        @perfil_lider_required
        def sample_view(_request):
            return HttpResponse("ok")

        for user in (self.lider, self.gerente):
            with self.subTest(perfil=user.perfil_acesso):
                request = self.factory.get("/alguma-url/")
                request.user = user

                response = sample_view(request)

                self.assertEqual(response.status_code, 200)

    def test_perfil_lider_required_blocks_membro(self):
        @perfil_lider_required
        def sample_view(_request):
            return HttpResponse("ok")

        request = self.factory.get("/alguma-url/")
        request.user = self.membro

        response = sample_view(request)

        self.assertEqual(response.status_code, 403)

    def test_perfil_membro_or_above_required_allows_all_perfis(self):
        @perfil_membro_or_above_required
        def sample_view(_request):
            return HttpResponse("ok")

        for user in (self.membro, self.lider, self.gerente):
            with self.subTest(perfil=user.perfil_acesso):
                request = self.factory.get("/alguma-url/")
                request.user = user

                response = sample_view(request)

                self.assertEqual(response.status_code, 200)
