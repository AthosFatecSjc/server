"""Serviços e regras de negócio do módulo de usuários."""

from __future__ import annotations

from typing import Any

from django.db import transaction
from django.db.models import Q

from apps.usuarios.models import Usuario


def listar_usuarios(filtros: dict[str, Any] | None = None):
    """Retorna um queryset filtrado de usuários conforme parâmetros informados."""
    filtros = filtros or {}
    queryset = Usuario.objects.all()

    termo = (filtros.get("busca") or "").strip()
    if termo:
        queryset = queryset.filter(
            Q(nome_completo__icontains=termo)
            | Q(username__icontains=termo)
            | Q(email__icontains=termo)
        )

    perfil = filtros.get("perfil_acesso")
    if perfil:
        queryset = queryset.filter(perfil_acesso=perfil)

    status = filtros.get("status")
    if status == "ativo":
        queryset = queryset.filter(ativo=True)
    elif status == "inativo":
        queryset = queryset.filter(ativo=False)

    return queryset


def obter_usuario_por_pk(pk: int) -> Usuario:
    """Recupera um usuário garantindo consistência."""
    return Usuario.objects.get(pk=pk)


@transaction.atomic
def alterar_status_usuario(usuario: Usuario, *, ativo: bool) -> Usuario:
    """Ativa ou inativa um usuário respeitando a integridade transacional."""
    usuario.ativo = ativo
    usuario.save()
    return usuario
