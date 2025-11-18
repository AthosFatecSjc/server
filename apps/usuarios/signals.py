"""Sinais relacionados ao modelo de usuário."""

from __future__ import annotations

from django.apps import apps as django_apps
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.text import slugify

from apps.usuarios.models import Usuario


def _normalizar_sigla(cargo: str) -> str:
    if not cargo:
        return ""
    slug = slugify(cargo, allow_unicode=False)
    return slug.replace("-", "_").upper()[:20]


def sincronizar_usuario_para_funcionarios(usuario: Usuario):
    """Atualiza o cargo dos funcionários com base no usuário correspondente."""
    nome = (usuario.nome_completo or "").strip()
    funcionario_model = django_apps.get_model(
        "relatorios", "Funcionario"
    )  # pylint: disable=invalid-name
    cargo_model = django_apps.get_model(
        "relatorios", "Cargo"
    )  # pylint: disable=invalid-name

    if not nome:
        return

    funcionarios = funcionario_model.objects.filter(nome__iexact=nome)
    if not funcionarios.exists():
        return

    sigla = _normalizar_sigla(usuario.cargo)
    cargo_obj = None
    if sigla:
        cargo_obj = cargo_model.objects.filter(sigla__iexact=sigla).first()
        if not cargo_obj:
            cargo_obj = cargo_model.objects.create(sigla=sigla)

    novo_id = cargo_obj.id if cargo_obj else None
    ids_atualizados = funcionarios.exclude(cargo_id=novo_id)
    if cargo_obj:
        ids_atualizados.update(cargo=cargo_obj)
    else:
        ids_atualizados.update(cargo=None)


@receiver(post_save, sender=Usuario)
def usuario_post_save(sender, instance: Usuario, **_kwargs):
    sincronizar_usuario_para_funcionarios(instance)
