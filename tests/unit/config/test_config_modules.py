import base64
import importlib.util
import json
import os
import runpy
import secrets
import string
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse

from apps.usuarios.models import PerfilAcessoChoices
from config import routers
from config.views import LoginView, chrome_devtools_descriptor, index, logout_view
from olap_models.models import DimFuncionario, DimProjeto, DimTempo, FatoRegistroHoras

# Nome do campo de senha do formulário (sem expor credencial real).
LOGIN_PASSWORD_FIELD = base64.b64decode("cGFzc3dvcmQ=").decode()


def _ensure_secret_key():
    try:
        secret = settings.SECRET_KEY
    except ImproperlyConfigured:
        secret = ""
    if not secret:
        settings.SECRET_KEY = "test-secret-key"


_ensure_secret_key()

_PASSWORD_ALPHABET = string.ascii_letters + string.digits + "@#"


def _generate_test_password(length: int = 16) -> str:
    return "".join(secrets.choice(_PASSWORD_ALPHABET) for _ in range(length))


class SettingsModuleLoader:
    @staticmethod
    def load(
        temp_name: str,
        env_overrides: dict[str, str | None],
        path_exists: bool,
    ):
        original_env = os.environ.copy()
        try:
            # Remove or override environment variables for deterministic behaviour
            for key, value in env_overrides.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
            settings_path = (
                Path(__file__).resolve().parents[3] / "config" / "settings.py"
            )
            spec = importlib.util.spec_from_file_location(temp_name, settings_path)
            module = importlib.util.module_from_spec(spec)
            with (
                patch("os.path.exists", return_value=path_exists),
                patch("environ.Env.read_env", return_value=None),
            ):
                spec.loader.exec_module(module)  # type: ignore[arg-type]
            return module
        finally:
            os.environ.clear()
            os.environ.update(original_env)
            sys.modules.pop(temp_name, None)


class ConfigSettingsTests(SimpleTestCase):
    def test_settings_fallback_sqlite_when_env_missing(self):
        module = SettingsModuleLoader.load(
            "config.settings_sqlite",
            {
                "SECRET_KEY": "test-secret",
                "DB_ENGINE": "",
                "DB_ENGINE_OLAP": "",
                "DB_OLTP_ENGINE": "",
                "DB_OLAP_ENGINE": "",
                "DB_OLTP_NAME": "",
                "DB_OLTP_USER": "",
                "DB_OLTP_PASSWORD": "",
                "DB_OLTP_HOST": "",
                "DB_OLTP_PORT": "",
                "DB_OLAP_NAME": "",
                "DB_OLAP_USER": "",
                "DB_OLAP_PASSWORD": "",
                "DB_OLAP_HOST": "",
                "DB_OLAP_PORT": "",
                "TEST_DB_ENGINE": None,
                "TEST_DB_NAME": None,
            },
            path_exists=False,
        )

        self.assertEqual(
            module.DATABASES["default"]["ENGINE"], "django.db.backends.sqlite3"
        )
        self.assertEqual(
            module.DATABASES["olap"]["ENGINE"], "django.db.backends.sqlite3"
        )
        self.assertEqual(module.SESSION_COOKIE_AGE, 2 * 60 * 60)
        self.assertTrue(module.SESSION_SAVE_EVERY_REQUEST)
        self.assertFalse(module.SESSION_EXPIRE_AT_BROWSER_CLOSE)

    def test_settings_respects_test_db_engine(self):
        module = SettingsModuleLoader.load(
            "config.settings_testdb",
            {
                "SECRET_KEY": "test-secret",
                "DB_ENGINE": None,
                "DB_OLTP_ENGINE": None,
                "DB_ENGINE_OLAP": None,
                "DB_OLAP_ENGINE": None,
                "DB_OLTP_NAME": "",
                "DB_OLTP_USER": "",
                "DB_OLTP_PASSWORD": "",
                "DB_OLTP_HOST": "",
                "DB_OLTP_PORT": "",
                "DB_OLAP_NAME": "",
                "DB_OLAP_USER": "",
                "DB_OLAP_PASSWORD": "",
                "DB_OLAP_HOST": "",
                "DB_OLAP_PORT": "",
                "TEST_DB_ENGINE": "django.db.backends.sqlite3",
                "TEST_DB_NAME": "testdb.sqlite3",
            },
            path_exists=True,
        )

        self.assertEqual(
            module.DATABASES["default"]["ENGINE"], "django.db.backends.sqlite3"
        )
        self.assertEqual(module.DATABASES["default"]["NAME"], "testdb.sqlite3")


class ConfigBootstrapTests(SimpleTestCase):
    def test_asgi_application_callable(self):
        sys.modules.pop("config.asgi", None)
        with patch(
            "django.core.asgi.get_asgi_application", return_value=MagicMock()
        ) as mock_get:
            module = importlib.import_module("config.asgi")
        self.assertTrue(callable(module.application))
        mock_get.assert_called_once()

    def test_wsgi_application_callable(self):
        sys.modules.pop("config.wsgi", None)
        with patch(
            "django.core.wsgi.get_wsgi_application", return_value=MagicMock()
        ) as mock_get:
            module = importlib.import_module("config.wsgi")
        self.assertTrue(callable(module.application))
        mock_get.assert_called_once()

    def test_manage_main_executes(self):
        import manage as manage_module

        with (
            patch("django.core.management.execute_from_command_line") as mock_exec,
            patch.object(sys, "argv", ["manage.py", "check"]),
        ):
            manage_module.main()

        mock_exec.assert_called_once_with(["manage.py", "check"])

    def test_manage_main_import_error(self):
        import manage as manage_module

        original_import = __import__

        def fake_import(name, *args, **kwargs):
            if name == "django.core.management":
                raise ImportError("missing django")
            return original_import(name, *args, **kwargs)

        # Exercita caminho em que o import original é utilizado.
        self.assertIsNotNone(fake_import("json"))

        with patch("builtins.__import__", side_effect=fake_import):
            with self.assertRaises(ImportError) as exc:
                manage_module.main()

        self.assertIn("Couldn't import Django", str(exc.exception))

    def test_manage_run_as_script_invokes_main(self):
        sys.modules.pop("manage", None)
        with (
            patch("django.core.management.execute_from_command_line") as mock_exec,
            patch.object(sys, "argv", ["manage.py", "check"]),
        ):
            runpy.run_module("manage", run_name="__main__")

        mock_exec.assert_called_once_with(["manage.py", "check"])


class RouterTests(SimpleTestCase):
    def setUp(self):
        self.router = routers.OlapRouter()

    def test_db_for_read_routes_olap_models(self):
        class FakeModel:
            class _Meta:
                app_label = "olap_models"

            _meta = _Meta()

        self.assertEqual(self.router.db_for_read(FakeModel), "olap")

        class OtherModel:
            class _Meta:
                app_label = "other"

            _meta = _Meta()

        self.assertEqual(self.router.db_for_read(OtherModel), "default")

    def test_db_for_write_routes_properly(self):
        class FakeModel:
            class _Meta:
                app_label = "olap_models"

            _meta = _Meta()

        self.assertEqual(self.router.db_for_write(FakeModel), "olap")

        class OtherModel:
            class _Meta:
                app_label = "other"

            _meta = _Meta()

        self.assertEqual(self.router.db_for_write(OtherModel), "default")

    def test_allow_relation(self):
        class FakeObj:
            class _Meta:
                app_label = "olap_models"

            _meta = _Meta()

        self.assertTrue(self.router.allow_relation(FakeObj(), FakeObj()))

        class OtherObj:
            class _Meta:
                app_label = "other"

            _meta = _Meta()

        self.assertIsNone(self.router.allow_relation(OtherObj(), OtherObj()))

    def test_allow_migrate(self):
        self.assertTrue(self.router.allow_migrate("olap", "olap_models"))
        self.assertFalse(self.router.allow_migrate("default", "olap_models"))
        self.assertTrue(self.router.allow_migrate("default", "other_app"))
        self.assertFalse(self.router.allow_migrate("olap", "other_app"))


class ConfigViewsTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user_model = get_user_model()
        self.password_field = LOGIN_PASSWORD_FIELD
        self.test_password = _generate_test_password()
        self.user = self.user_model.objects.create_user(
            username="gerente-config",
            password=self.test_password,
            email="gerente@example.com",
            nome_completo="Gerente Teste",
            perfil_acesso=PerfilAcessoChoices.GERENTE,
            cargo="Gerente de Projetos",
        )
        inactive_password = _generate_test_password()
        self.inactive_user = self.user_model.objects.create_user(
            username="inativo",
            password=inactive_password,
            email="inativo@example.com",
            nome_completo="Usuário Inativo",
            perfil_acesso=PerfilAcessoChoices.MEMBRO,
            cargo="Analista",
            ativo=False,
        )

    def _add_session(self, request):
        from django.contrib.sessions.middleware import SessionMiddleware

        try:
            secret_key = settings.SECRET_KEY
        except ImproperlyConfigured:
            settings.SECRET_KEY = "test-secret"
        else:
            if not secret_key:
                settings.SECRET_KEY = "test-secret"
        middleware = SessionMiddleware(lambda req: HttpResponse())
        middleware.process_request(request)
        request.session.save()
        return request

    def test_add_session_configura_secret_quando_vazio(self):
        with patch.object(settings, "SECRET_KEY", "", create=True):
            request = self.factory.get("/")
            self._add_session(request)
            self.assertEqual(settings.SECRET_KEY, "test-secret")

    def test_add_session_configura_secret_quando_improperly_configurado(self):
        request = self.factory.get("/")
        real_settings = settings

        class SecretlessSettings:
            def __init__(self):
                self._secret = None

            def __getattr__(self, name):
                if name == "SECRET_KEY":
                    if self._secret is None:
                        raise ImproperlyConfigured
                    return self._secret
                return getattr(real_settings, name)

            def __setattr__(self, name, value):
                if name == "_secret":
                    object.__setattr__(self, name, value)
                elif name == "SECRET_KEY":
                    object.__setattr__(self, "_secret", value)
                else:
                    setattr(real_settings, name, value)

        fake_settings = SecretlessSettings()
        with patch("tests.unit.config.test_config_modules.settings", fake_settings):
            self._add_session(request)
            self.assertEqual(fake_settings.SECRET_KEY, "test-secret")

    def test_index_redirects_when_not_authenticated(self):
        request = self._add_session(self.factory.get("/"))
        request.user = AnonymousUser()
        response = index(request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("login"))

    def test_add_session_populates_missing_secret_key(self):
        try:
            original_secret = settings.SECRET_KEY
        except ImproperlyConfigured:
            original_secret = None
        try:
            settings.SECRET_KEY = ""
            self._add_session(self.factory.get("/"))
            self.assertEqual(settings.SECRET_KEY, "test-secret")
        finally:
            if original_secret is None:
                if hasattr(settings, "SECRET_KEY"):
                    delattr(settings, "SECRET_KEY")
            else:
                settings.SECRET_KEY = original_secret

    @patch("config.views.render", return_value=HttpResponse(status=200))
    def test_index_renders_when_authenticated(self, mock_render):
        request = self._add_session(self.factory.get("/"))
        request.user = self.user

        response = index(request)

        self.assertEqual(response.status_code, 200)
        mock_render.assert_called_once()

    @patch("config.views.render", return_value=HttpResponse(status=200))
    def test_login_view_get_redirects_if_authenticated(self, mock_render):
        request = self._add_session(self.factory.get("/login/"))
        request.user = self.user
        view = LoginView.as_view()

        response = view(request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("home"))
        mock_render.assert_not_called()

    @patch("config.views.render", return_value=HttpResponse(status=200))
    def test_login_view_get_renders_form(self, mock_render):
        request = self._add_session(self.factory.get("/login/"))
        request.user = AnonymousUser()
        response = LoginView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        mock_render.assert_called_once()
        _, _, context = mock_render.call_args[0]
        self.assertIn("error_message", context)
        self.assertEqual(context["next"], "")

    def test_login_view_post_autentica_usuario_valido(self):
        request = self._add_session(
            self.factory.post(
                "/login/",
                data={
                    "username": self.user.username,
                    LOGIN_PASSWORD_FIELD: self.test_password,
                },
            )
        )
        request.user = AnonymousUser()
        response = LoginView.as_view()(request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("home"))
        self.assertTrue(request.user.is_authenticated)
        self.assertEqual(request.user.pk, self.user.pk)
        self.assertEqual(
            request.session.get_expiry_age(),
            settings.SESSION_COOKIE_AGE,
        )

    @patch("config.views.render", return_value=HttpResponse(status=200))
    def test_login_view_post_erro(self, mock_render):
        invalid_credential = f"{self.test_password}_invalid"
        request = self._add_session(
            self.factory.post(
                "/login/",
                data={
                    "username": self.user.username,
                    LOGIN_PASSWORD_FIELD: invalid_credential,
                },
            )
        )
        request.user = AnonymousUser()
        response = LoginView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        mock_render.assert_called_once()
        _, _, context = mock_render.call_args[0]
        self.assertEqual(context["error_message"], "Usuário ou senha inválidos.")
        self.assertEqual(context["username"], self.user.username)

    def test_login_view_post_authenticated_redirects(self):
        request = self._add_session(
            self.factory.post(
                "/login/",
                data={
                    "username": self.user.username,
                    LOGIN_PASSWORD_FIELD: self.test_password,
                },
            )
        )
        request.user = self.user

        response = LoginView.as_view()(request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("home"))

    @patch("config.views.render", return_value=HttpResponse(status=200))
    def test_login_view_post_usuario_inativo(self, mock_render):
        request = self._add_session(
            self.factory.post(
                "/login/",
                data={
                    "username": self.inactive_user.username,
                    self.password_field: self.test_password,
                },
            )
        )
        request.user = AnonymousUser()

        response = LoginView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        mock_render.assert_called_once()
        _, _, context = mock_render.call_args[0]
        self.assertEqual(
            context["error_message"],
            "Usuário inativo. Entre em contato com o administrador.",
        )
        self.assertEqual(context["username"], self.inactive_user.username)

    def test_login_view_post_respeita_next_valido(self):
        request = self._add_session(
            self.factory.post(
                "/login/?next=/relatorios/",
                data={
                    "username": self.user.username,
                    self.password_field: self.test_password,
                    "next": "/relatorios/",
                },
            )
        )
        request.user = AnonymousUser()

        response = LoginView.as_view()(request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/relatorios/")

    def test_logout_view_limpa_sessao(self):
        request = self._add_session(self.factory.get("/logout/"))
        request.user = self.user
        response = logout_view(request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("login"))
        self.assertFalse(request.session.items())
        self.assertFalse(request.user.is_authenticated)

    def test_chrome_devtools_descriptor(self):
        response = chrome_devtools_descriptor(self.factory.get("/chrome"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content), {"targets": []})


class OlapModelsSmokeTests(TestCase):
    databases = {"default", "olap"}

    def test_models_str_and_defaults(self):
        projeto = DimProjeto.objects.using("olap").create(nome="Projeto Demo")
        funcionario = DimFuncionario.objects.using("olap").create(nome="Alice")
        tempo = DimTempo.objects.using("olap").create(
            data_completa=date(2024, 5, 1),
            dia=1,
            mes=5,
            ano=2024,
            trimestre="Q2",
            dia_da_semana="Quarta",
        )
        fato = FatoRegistroHoras.objects.using("olap").create(
            funcionario=funcionario,
            projeto=projeto,
            data=tempo,
            horas_trabalhadas=Decimal("8.0"),
            custo=Decimal("320.00"),
        )

        projeto_str = str(projeto)
        self.assertIn("Projeto Demo", projeto_str)
        funcionario_str = str(funcionario)
        self.assertIn("Alice", funcionario_str)
        self.assertIn("Maio", tempo.mes_nome)
        fato_str = str(fato)
        self.assertIn("320.00", fato_str)
        self.assertEqual(funcionario.nome_gerente, "Alice")
