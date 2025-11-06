"""Decorators to enforce access control based on ``perfil_acesso``."""

from functools import wraps
from typing import Callable, Iterable

from django.contrib.auth.views import redirect_to_login
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden

from .models import PerfilAcessoChoices

FORBIDDEN_MESSAGE = "Você não tem permissão para acessar esta página."


def _perfil_required(allowed_perfis: Iterable[str]) -> Callable:
    allowed = set(allowed_perfis)

    def decorator(view_func: Callable) -> Callable:
        @wraps(view_func)
        def _wrapped(request: HttpRequest, *args, **kwargs) -> HttpResponse:
            user = request.user
            if not getattr(user, "is_authenticated", False):
                return redirect_to_login(request.get_full_path())

            user_perfil = getattr(user, "perfil_acesso", None)
            if user_perfil not in allowed:
                return HttpResponseForbidden(FORBIDDEN_MESSAGE)

            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator


def perfil_gerente_required(view_func: Callable) -> Callable:
    """Permite acesso apenas para usuários com perfil ``GERENTE``."""

    return _perfil_required({PerfilAcessoChoices.GERENTE})(view_func)


def perfil_lider_required(view_func: Callable) -> Callable:
    """Permite acesso para usuários com perfil ``LIDER`` ou ``GERENTE``."""

    return _perfil_required(
        {
            PerfilAcessoChoices.LIDER,
            PerfilAcessoChoices.GERENTE,
        }
    )(view_func)


def perfil_membro_or_above_required(view_func: Callable) -> Callable:
    """Permite acesso para usuários com perfil ``MEMBRO``, ``LIDER`` ou ``GERENTE``."""

    return _perfil_required(
        {
            PerfilAcessoChoices.MEMBRO,
            PerfilAcessoChoices.LIDER,
            PerfilAcessoChoices.GERENTE,
        }
    )(view_func)
