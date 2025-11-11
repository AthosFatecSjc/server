from django.conf import settings
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.decorators.http import require_POST, require_safe

from apps.usuarios.models import PerfilAcessoChoices

User = get_user_model()

PROFILE_REDIRECTS = {
    PerfilAcessoChoices.GERENTE: "home",
    PerfilAcessoChoices.LIDER: "home",
    PerfilAcessoChoices.MEMBRO: "home",
}


def _get_redirect_for_user(user) -> str:
    url_name = PROFILE_REDIRECTS.get(user.perfil_acesso, "home")
    return reverse(url_name)


def _resolve_next(request, fallback: str) -> str:
    candidate = request.POST.get("next") or request.GET.get("next")
    if candidate and url_has_allowed_host_and_scheme(
        url=candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return candidate
    return fallback


@require_safe
def index(request):
    if not request.user.is_authenticated:
        return redirect("login")

    return render(
        request,
        "config/index.html",
        {"usuario": request.user},
    )


@method_decorator(require_safe, name="get")
@method_decorator(require_POST, name="post")
class LoginView(View):
    template_name = "auth/login.html"
    http_method_names = ["get", "head", "post"]

    def get(self, request):
        if request.user.is_authenticated:
            return redirect(_get_redirect_for_user(request.user))

        next_url = request.GET.get("next", "")
        return render(
            request,
            self.template_name,
            {"error_message": None, "next": next_url, "username": ""},
        )

    def post(self, request):
        if request.user.is_authenticated:
            return redirect(_get_redirect_for_user(request.user))

        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        next_url = request.POST.get("next", "")

        if not username or not password:
            context = {
                "error_message": "Informe usuário e senha.",
                "next": next_url,
                "username": username,
            }
            return render(request, self.template_name, context)

        user = authenticate(request, username=username, password=password)

        if user is None:
            try:
                usuario = User.objects.get(username=username)
            except User.DoesNotExist:
                error_message = "Usuário ou senha inválidos."
            else:
                if getattr(usuario, "ativo", usuario.is_active):
                    error_message = "Usuário ou senha inválidos."
                else:
                    error_message = (
                        "Usuário inativo. Entre em contato com o administrador."
                    )

            context = {
                "error_message": error_message,
                "next": next_url,
                "username": username,
            }
            return render(request, self.template_name, context)

        if not getattr(user, "ativo", user.is_active):
            context = {
                "error_message": "Usuário inativo. Entre em contato com o administrador.",
                "next": next_url,
                "username": username,
            }
            return render(request, self.template_name, context)

        login(request, user)
        request.session.set_expiry(settings.SESSION_COOKIE_AGE)
        redirect_url = _resolve_next(request, _get_redirect_for_user(user))
        return redirect(redirect_url)


@require_safe
def logout_view(request):
    logout(request)
    return redirect("login")


@require_safe
def chrome_devtools_descriptor(_request):
    return JsonResponse({"targets": []})
