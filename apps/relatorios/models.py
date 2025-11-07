"""Modelos para relatórios e controle de horas."""

from datetime import date, datetime
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


class ControleHorasEquipeResumo(models.Model):
    """Modelo para resumo de controle de horas da equipe"""

    total_dev = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    total_projeto = models.DecimalField(max_digits=6, decimal_places=2, default=0)

    class Meta:
        """Meta dados do modelo ControleHorasEquipeResumo"""

        db_table = "controle_horas_equipe_resumo"

    def __str__(self):
        return f"Dev: {self.total_dev}h | Projeto: {self.total_projeto}h"


class ControleHorasEquipe(models.Model):
    """Modelo para controle de horas da equipe"""

    mes = models.DateField()
    projeto = models.ForeignKey(Projeto, on_delete=models.CASCADE)
    funcionario = models.ForeignKey(Funcionario, on_delete=models.CASCADE)
    horas = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    resumo = models.ForeignKey(
        ControleHorasEquipeResumo, on_delete=models.SET_NULL, null=True, blank=True
    )

    class Meta:
        """Meta dados do modelo ControleHorasEquipe"""

        unique_together = ("mes", "projeto", "funcionario")
        db_table = "controle_horas_equipe"

    def __str__(self) -> str:
        mes_value = self.mes
        if isinstance(mes_value, date):
            mes_str = mes_value.strftime("%m/%Y")
        else:
            mes_str = "N/A"
        return f"""{
            self.funcionario} - {
            self.projeto} - {
            mes_str} - {
                self.horas}h"""


class MetaTempoControle(models.Model):
    """Modelo para metas de tempo de controle"""

    objetivo_clt = models.CharField(max_length=100, blank=True)
    objetivo_estagiario = models.CharField(max_length=100, blank=True)

    class Meta:
        """Meta dados do modelo MetaTempoControle"""

        db_table = "meta_tempo_controle"

    def __str__(self):
        return f"objetivo clt: {self.objetivo_clt} | objetivo estagiario: {self.objetivo_estagiario}"


class TempoGastoEquipe(models.Model):
    """Modelo para tempo gasto pela equipe"""

    dia_semana = models.CharField(max_length=10)
    dia_mes = models.PositiveIntegerField()
    mes = models.DateField()
    funcionario = models.ForeignKey(Funcionario, on_delete=models.CASCADE)
    tempo_gasto = models.DecimalField(max_digits=6, decimal_places=2)
    meta = models.ForeignKey(
        MetaTempoControle, on_delete=models.SET_NULL, null=True, blank=True
    )

    class Meta:
        """Meta dados do modelo TempoGastoEquipe"""

        db_table = "controle_tempo_equipe"
        constraints = [
            models.UniqueConstraint(
                fields=["funcionario", "dia_mes", "mes"],
                name="unique_funcionario_dia_mes",
            )
        ]

    def __str__(self) -> str:
        mes_value = self.mes
        mes_str = mes_value.strftime("%m/%Y") if isinstance(mes_value, date) else "N/A"
        return f"""{
            self.funcionario} - {
            mes_str} - {
            self.tempo_gasto}h"""


class TempoControleValores(models.Model):
    """Modelo para valores de controle de tempo"""

    controle_tempo_equipe = models.ForeignKey(
        TempoGastoEquipe, on_delete=models.CASCADE
    )
    realizado_equipe = models.DecimalField(max_digits=6, decimal_places=2)
    total_real = models.DecimalField(max_digits=6, decimal_places=2)
    total_meta = models.DecimalField(max_digits=6, decimal_places=2)
    aproveitamento = models.DecimalField(max_digits=5, decimal_places=2)  # Percentual

    class Meta:
        """Meta dados do modelo TempoControleValores"""

        db_table = "controle_tempo_resumo"

    def __str__(self):
        return f"Aproveitamento: {self.aproveitamento}%"


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
