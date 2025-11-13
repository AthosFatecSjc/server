"""Modelos para relatórios e controle de horas."""

from datetime import datetime
from pprint import pformat

from django.db import models


class Cargo(models.Model):
    """Modelo para cargos dos funcionários"""

    sigla = models.CharField(max_length=20)

    class Meta:
        """Meta dados do modelo Cargo"""

        db_table = "cargo"

    def __str__(self):
        return str(self.sigla)


class Funcionario(models.Model):
    """Modelo para funcionários"""

    nome = models.CharField(max_length=100)
    time = models.CharField(max_length=100, blank=True)
    cargo = models.ForeignKey(Cargo, on_delete=models.SET_NULL, null=True)
    gerente = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="subordinados",
    )
    data_criacao = models.DateField(auto_now_add=True)
    valor_hora = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=40.00,
        help_text="Valor/hora do desenvolvedor (R$)",
    )
    contrato = models.CharField(
        max_length=20,
        choices=[("CLT", "CLT"), ("ESTAGIARIO", "Estagiário")],
        default="CLT",
    )

    class Meta:
        """Meta dados do modelo Funcionario"""

        db_table = "funcionario"

    def __str__(self):
        return str(self.nome)


class Projeto(models.Model):
    """Modelo para projetos"""

    id = models.AutoField(primary_key=True)
    jira_id = models.PositiveIntegerField(null=True)
    jira_key = models.CharField(max_length=50, blank=True, default="")
    nome = models.CharField(max_length=100)
    data_criacao = models.DateField(auto_now_add=True)
    orcamento_previsto = models.DecimalField(
        max_digits=15, decimal_places=2, default=20000.00
    )

    def save(self, *args, **kwargs):
        if not self.orcamento_previsto:
            self.orcamento_previsto = 20000.00
        super().save(*args, **kwargs)

    class Meta:
        """Meta dados do modelo Projeto"""

        db_table = "projeto"

    def __str__(self):
        return pformat(self.__dict__, indent=4, width=120)


class _RemovedManager:
    """Stub manager that raises when used."""

    def __getattr__(self, attr):
        raise RuntimeError(
            "Este recurso foi removido do modelo OLTP. "
            "Atualize os relatórios/dashboards para usar Issue/Projeto."
        )


class _RemovedModel:
    """Placeholder para manter imports existentes enquanto o schema é normalizado."""

    objects = _RemovedManager()

    def __init__(self, *args, **kwargs):
        raise RuntimeError(
            "Este modelo foi removido do schema OLTP. "
            "Atualize os relatórios para não dependerem dele."
        )


def _removed_model(name: str):
    return type(
        name,
        (_RemovedModel,),
        {
            "__module__": __name__,
            "__doc__": f"{name} foi removido do schema OLTP. "
            "Atualize os relatórios/dashboards para usar Issue/Projeto.",
        },
    )


ControleHorasEquipe = _removed_model("ControleHorasEquipe")
ControleHorasEquipeResumo = _removed_model("ControleHorasEquipeResumo")
MetaTempoControle = _removed_model("MetaTempoControle")
TempoGastoEquipe = _removed_model("TempoGastoEquipe")
TempoControleValores = _removed_model("TempoControleValores")


class TipoIssue(models.Model):
    """
    Modelo para tipos de issue do projeto
    """

    id = models.AutoField(primary_key=True)
    nome = models.CharField(max_length=255, null=False, blank=False)
    descricao = models.CharField(max_length=1024, blank=True, default="")
    jira_id = models.PositiveIntegerField(null=False, blank=False)
    projeto = models.ForeignKey(
        Projeto, on_delete=models.CASCADE, null=False, blank=False
    )
    data_criacao = models.DateField(default=datetime.now)

    class Meta:
        """
        Regras para criação da tabela no banco de dados
        """

        db_table = "tipo_issue"

    def save(self, *args, **kwargs):
        if not self.data_criacao:
            self.data_criacao = datetime.now()
        super().save(*args, **kwargs)

    def __str__(self):
        return pformat(self.__dict__, indent=4, width=120)


class Issue(models.Model):
    """
    Modelo para issues do projeto
    """

    id = models.AutoField(primary_key=True)
    jira_id = models.PositiveIntegerField(null=False, blank=False)
    jira_key = models.CharField(max_length=50, null=False, blank=False)
    projeto = models.ForeignKey(
        Projeto, on_delete=models.CASCADE, null=False, blank=False
    )
    titulo = models.CharField(max_length=255, null=False, blank=False)
    tipo_issue = models.ForeignKey(TipoIssue, on_delete=models.SET_NULL, null=True)
    criado_em = models.DateTimeField(null=True)
    tempo_gasto_seconds = models.PositiveIntegerField(default=0, null=True)
    tempo_estimado_seconds = models.PositiveIntegerField(default=0, null=True)
    funcionario = models.ForeignKey(Funcionario, on_delete=models.SET_NULL, null=True)
    atualizado_em = models.DateTimeField(null=True)
    status = models.CharField(max_length=100, blank=True, default="")

    class Meta:
        """
        Regras para criação da tabela no banco de dados
        """

        db_table = "issue"

    def __str__(self):
        return pformat(self.__dict__, indent=4, width=120)


class PlanejamentoProjeto(models.Model):
    """
    Guarda as horas previstas por projeto e ano após a normalização do OLTP.
    Substitui o antigo MetaTempoControle, removido do schema.
    """

    projeto = models.ForeignKey(
        Projeto, on_delete=models.CASCADE, related_name="planejamentos"
    )
    ano = models.PositiveIntegerField()
    horas_previstas = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        db_table = "planejamento_projeto"
        unique_together = ("projeto", "ano")
        ordering = ("projeto_id", "ano")

    def __str__(self):
        return f"{self.projeto.nome} ({self.ano}) - {self.horas_previstas}h"


class RegistroProdutividade(models.Model):
    """
    Registra as horas (ou códigos especiais) lançadas por dia e funcionário.
    Valores negativos representam códigos de ausência (ex: -1 = Férias).
    """

    funcionario = models.ForeignKey(
        Funcionario,
        on_delete=models.CASCADE,
        related_name="registros_produtividade",
    )
    dia = models.DateField()
    valor = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "registro_produtividade"
        ordering = ("dia",)
        unique_together = ("funcionario", "dia")

    def __str__(self):
        return f"{self.funcionario.nome} - {self.dia} => {self.valor}"


class MetaProdutividade(models.Model):
    """Meta de horas mensais por funcionário."""

    funcionario = models.ForeignKey(
        Funcionario,
        on_delete=models.CASCADE,
        related_name="metas_produtividade",
    )
    ano = models.PositiveIntegerField()
    mes = models.PositiveIntegerField()
    meta_horas = models.DecimalField(max_digits=6, decimal_places=2, default=154.0)

    class Meta:
        db_table = "meta_produtividade"
        ordering = ("funcionario_id", "ano", "mes")
        unique_together = ("funcionario", "ano", "mes")

    def __str__(self):
        return f"{self.funcionario.nome} {self.mes:02d}/{self.ano} - {self.meta_horas}h"
