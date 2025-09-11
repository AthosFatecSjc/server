from django.db import models


class Cargo(models.Model):
    sigla = models.CharField(max_length=20)

    class Meta:
        db_table = 'cargo'

    def __str__(self):
        return self.sigla


class Funcionario(models.Model):
    nome = models.CharField(max_length=100)
    time = models.CharField(max_length=100, blank=True)
    cargo = models.ForeignKey(Cargo, on_delete=models.SET_NULL, null=True)
    gerente = models.BooleanField(default=False)
    data_criacao = models.DateField(auto_now_add=True)

    class Meta:
        db_table = 'func'

    def __str__(self):
        return self.nome


class Projeto(models.Model):
    nome = models.CharField(max_length=100)
    data_criacao = models.DateField(auto_now_add=True)

    class Meta:
        db_table = 'projeto'

    def __str__(self):
        return self.nome


class ControleHorasEquipeResumo(models.Model):
    total_dev = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    total_projeto = models.DecimalField(max_digits=6, decimal_places=2, default=0)

    class Meta:
        db_table = 'controle_horas_equipe_values'

    def __str__(self):
        return f"Dev: {self.total_dev}h | Projeto: {self.total_projeto}h"


class ControleHorasEquipe(models.Model):
    mes = models.DateField()
    projeto = models.ForeignKey(Projeto, on_delete=models.CASCADE, db_column='projeto_id')
    funcionario = models.ForeignKey(Funcionario, on_delete=models.CASCADE, db_column='func_id')
    horas = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    resumo = models.ForeignKey(ControleHorasEquipeResumo, on_delete=models.SET_NULL, null=True, blank=True, db_column='values_id')

    class Meta:
        unique_together = ('mes', 'projeto', 'funcionario')
        db_table = 'controle_horas_equipe'

    def __str__(self):
        return f"{self.funcionario} - {self.projeto} - {self.mes.strftime('%m/%Y')} - {self.horas}h"



class MetaTempoControle(models.Model):
    goal_ci = models.CharField(max_length=100, blank=True)
    goal_estrategico = models.CharField(max_length=100, blank=True)

    class Meta:
        db_table = 'time_control_goal'

    def __str__(self):
        return f"CI: {self.goal_ci} | Estratégico: {self.goal_estrategico}"


class TempoGastoEquipe(models.Model):
    dia_semana = models.CharField(max_length=10)  # Ex: 'Segunda'
    dia_mes = models.PositiveIntegerField()
    mes = models.DateField()
    funcionario = models.ForeignKey(Funcionario, on_delete=models.CASCADE)
    tempo_gasto = models.DecimalField(max_digits=6, decimal_places=2)
    meta = models.ForeignKey(MetaTempoControle, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        db_table = 'time_control_spend_equipe'

    def __str__(self):
        return f"{self.funcionario} - {self.mes.strftime('%m/%Y')} - {self.tempo_gasto}h"


class TempoControleValores(models.Model):
    tempo_gasto = models.ForeignKey(TempoGastoEquipe, on_delete=models.CASCADE)
    realizado_equipe = models.DecimalField(max_digits=6, decimal_places=2)
    total_real = models.DecimalField(max_digits=6, decimal_places=2)
    total_meta = models.DecimalField(max_digits=6, decimal_places=2)
    aproveitamento = models.DecimalField(max_digits=5, decimal_places=2)  # Percentual

    class Meta:
        db_table = 'time_control_CH_values'

    def __str__(self):
        return f"Aproveitamento: {self.aproveitamento}%"
