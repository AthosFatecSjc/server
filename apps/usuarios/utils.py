"""Utilitários para criação e sincronização automática de usuários."""

from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils.text import slugify

from apps.usuarios.models import PerfilAcessoChoices

Usuario = get_user_model()


@dataclass(frozen=True)
class UsuarioPlaceholderResult:
    """Estrutura auxiliar para indicar criação automática de usuários."""

    usuario: Usuario
    criado: bool


def _limpar_nome(nome: str) -> str:
    return " ".join((nome or "").split())


def _username_base(nome: str, max_length: int) -> str:
    slug = slugify(nome or "", allow_unicode=False)
    username = slug.replace("-", ".").strip(".")
    if not username:
        username = "dev"

    if len(username) > max_length:
        username = username[:max_length]
    return username


def gerar_username_unico(nome: str) -> str:
    """Gera um username único baseado no nome completo."""
    max_length = Usuario._meta.get_field("username").max_length
    base = _username_base(nome, max_length=max(4, max_length - 4))
    username = base
    sufixo = 1

    while Usuario.objects.filter(username=username).exists():
        suffix_str = str(sufixo)
        limit = max_length - len(suffix_str)
        trimmed = base[:limit] if limit > 0 else base
        username = f"{trimmed}{suffix_str}"
        sufixo += 1

    return username


def gerar_email_unico(username: str) -> str:
    """Gera um e-mail fake único reutilizando o domínio padrão."""
    domain = (settings.DEFAULT_DEV_USER_EMAIL_DOMAIN or "devs.local").strip()
    if not domain:
        domain = "devs.local"

    base_email = f"{username}@{domain}"
    if not Usuario.objects.filter(email=base_email).exists():
        return base_email

    sufixo = 1
    while True:
        email = f"{username}{sufixo}@{domain}"
        if not Usuario.objects.filter(email=email).exists():
            return email
        sufixo += 1


def garantir_usuario_placeholder(nome_completo: str) -> UsuarioPlaceholderResult:
    """Cria (ou retorna) um usuário placeholder com senha padrão."""
    nome_normalizado = _limpar_nome(nome_completo)
    if not nome_normalizado:
        raise ValueError("Nome do desenvolvedor não pode ser vazio.")

    existente = Usuario.objects.filter(nome_completo__iexact=nome_normalizado).first()
    if existente:
        return UsuarioPlaceholderResult(usuario=existente, criado=False)

    username = gerar_username_unico(nome_normalizado)
    email = gerar_email_unico(username)

    usuario = Usuario(
        nome_completo=nome_normalizado,
        username=username,
        email=email,
        cargo=settings.DEFAULT_DEV_USER_CARGO,
        perfil_acesso=PerfilAcessoChoices.MEMBRO,
        ativo=False,
    )
    usuario.set_password(settings.DEFAULT_DEV_USER_PASSWORD)
    usuario.save()
    return UsuarioPlaceholderResult(usuario=usuario, criado=True)
