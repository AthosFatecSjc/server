"""Modelos relacionados aos usuários do sistema."""

from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models


class ContratoChoices(models.TextChoices):
    """Tipos de contrato suportados para um usuário."""

    CLT = "CLT", "CLT"
    ESTAGIARIO = "ESTAGIARIO", "Estagiário"


class PerfilAcessoChoices(models.TextChoices):
    """Perfis de acesso disponíveis no sistema."""

    MEMBRO = "MEMBRO", "Membro"
    LIDER = "LIDER", "Líder"
    GERENTE = "GERENTE", "Gerente"


class Usuario(AbstractUser):
    """Modelo customizado de usuário com campos adicionais."""

    nome_completo = models.CharField(max_length=255)
    email = models.EmailField("email address", unique=True)
    contrato = models.CharField(
        max_length=20,
        choices=ContratoChoices.choices,
        default=ContratoChoices.CLT,
    )
    cargo = models.CharField(max_length=150)
    perfil_acesso = models.CharField(
        max_length=20,
        choices=PerfilAcessoChoices.choices,
        default=PerfilAcessoChoices.MEMBRO,
    )
    ativo = models.BooleanField(default=True)

    objects = UserManager()

    REQUIRED_FIELDS = ["email", "nome_completo"]

    class Meta(AbstractUser.Meta):
        ordering = ["nome_completo"]
        verbose_name = "Usuário"
        verbose_name_plural = "Usuários"
        db_table = "usuario"

    def clean(self):
        super().clean()
        if self.email:
            self.email = self.email.lower()

    def save(self, *args, **kwargs):
        self.is_active = self.ativo
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.nome_completo or self.username
