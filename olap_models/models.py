from datetime import datetime

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q


class DimProjeto(models.Model):
    """
    Modelo para dimensão de Projetos
    Originalmente criado para dashboard de custo
    """

    id = models.AutoField(primary_key=True)
    nome = models.CharField(max_length=100)
    data_criacao = models.DateField(default=datetime.now)

    class Meta:
        """
        Regras para criação da tabela no banco de dados
        """

        db_table = "dim_projeto"

    def __str__(self):
        return str(self.__dict__, indent=4, ensure_ascii=False)


class DimCargo(models.Model):
    nome_cargo = models.CharField(max_length=20, unique=True)

    class Meta:
        db_table = "dim_cargo"


class DimFuncionario(models.Model):
    """
    Modelo para dimensão de funcionários
    Originalmente criado para dashboard de custo
    """

    id = models.AutoField(primary_key=True)
    nome = models.CharField(max_length=100)
    time = models.CharField(max_length=100, blank=True)

    data_contratacao = models.DateField(default=datetime.now)
    cargo = models.CharField(max_length=20, default="dev")
    nome_gerente = models.CharField(max_length=100, blank=True)
    valor_hora = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=40.00,
        help_text="Valor/hora do desenvolvedor (R$)",
    )

    def save(self, *args, **kwargs):
        if not self.nome_gerente:
            self.nome_gerente = self.nome
        if not self.cargo:
            self.cargo = "dev"
        super().save(*args, **kwargs)

    class Meta:
        """
        Regras para criação da tabela no banco de dados
        """

        db_table = "dim_funcionario"

    def __str__(self):
        return str(self.__dict__, indent=4, ensure_ascii=False)


class DimTempo(models.Model):
    """
    Modelo para dimensão de Data
    Originalmente criado para dashboard de custo
    """

    id = models.AutoField(primary_key=True)
    hora = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(23)], default=0
    )
    dia = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(31)], default=1
    )
    mes = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(12)], default=1
    )
    ano = models.IntegerField(
        validators=[
            MinValueValidator(1900),
            MaxValueValidator(datetime.now().year + 1),
        ],
        default=1900,
    )
    mes_nome = models.CharField(max_length=20, editable=False, blank=True)
    data_completa = models.DateField(unique=True)
    trimestre = models.CharField(max_length=2)
    dia_da_semana = models.CharField(max_length=20)

    class Meta:
        """
        Regras para criação da tabela no banco de dados
        """

        db_table = "dim_tempo"
        constraints = [
            models.CheckConstraint(
                check=Q(hora__gte=0) & Q(hora__lte=23), name="hora_range_valid"
            ),
            models.CheckConstraint(
                check=Q(dia__gte=1) & Q(dia__lte=31), name="dia_range_valid"
            ),
            models.CheckConstraint(
                check=Q(mes__gte=1) & Q(mes__lte=12), name="mes_range_valid"
            ),
            models.CheckConstraint(
                check=Q(ano__gte=1900) & Q(ano__lte=datetime.now().year + 1),
                name="ano_range_valid",
            ),
        ]

    def save(self, *args, **kwargs):
        """
        Popula o nome do mês automaticamente em português.
        """

        meses_pt = [
            "Janeiro",
            "Fevereiro",
            "Março",
            "Abril",
            "Maio",
            "Junho",
            "Julho",
            "Agosto",
            "Setembro",
            "Outubro",
            "Novembro",
            "Dezembro",
        ]

        if 1 <= self.mes <= 12:
            self.mes_nome = meses_pt[self.mes - 1]

        super().save(*args, **kwargs)

    def __str__(self):
        return str(self.__dict__, indent=4, ensure_ascii=False)


class DimIssue(models.Model):
    """
    Dimensão para representar Issues trazidas do Jira.
    Armazena chave da issue (PROJ-123), tipo e sumário para análises.
    """

    id = models.AutoField(primary_key=True)
    issue_id = models.CharField(max_length=50, unique=True, null=True, blank=True)
    issue_type = models.CharField(max_length=30, null=True, blank=True)
    issue_summary = models.CharField(max_length=200, null=True, blank=True)
    created_date = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "dim_issue"

    def __str__(self):
        return str(self.__dict__, indent=4, ensure_ascii=False)


class FatoRegistroHoras(models.Model):
    """
    Modelo para tabela fato de registro de horas e custo de funcionários por projeto
    """

    funcionario = models.ForeignKey(DimFuncionario, on_delete=models.CASCADE, null=True)
    projeto = models.ForeignKey(DimProjeto, on_delete=models.CASCADE, null=True)
    data = models.ForeignKey(DimTempo, on_delete=models.CASCADE, null=True)
    horas_trabalhadas = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    custo = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    # referencia para a dimensão de issues (somente FK aqui)
    issue = models.ForeignKey(
        "DimIssue",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    class Meta:
        """
        Regras para criação da tabela no banco de dados
        """

        db_table = "fato_registro_horas"
        constraints = [
            models.CheckConstraint(
                check=Q(horas_trabalhadas__gte=0), name="total_horas_non_negative"
            ),
            models.CheckConstraint(
                check=Q(custo__gte=0), name="custo_total_non_negative"
            ),
            models.UniqueConstraint(
                fields=["funcionario_id", "projeto_id", "data_id"],
                name="unique_fato_per_day",
            ),
        ]

    def __str__(self):
        return str(self.__dict__, indent=4, ensure_ascii=False)
