from django.db import models

class DimProjeto(models.Model):
    nome_projeto = models.CharField(max_length=100)
    data_criacao = models.DateField(null=True, blank=True)

    class Meta:
        db_table = 'dim_projeto'

class DimCargo(models.Model):
    nome_cargo = models.CharField(max_length=20, unique=True)

    class Meta:
        db_table = 'dim_cargo'

class DimFuncionario(models.Model):
    nome_funcionario = models.CharField(max_length=100)
    time = models.CharField(max_length=100, blank=True)
    data_contratacao = models.DateField(null=True, blank=True)
    cargo = models.ForeignKey(DimCargo, on_delete=models.SET_NULL, null=True, db_column='fk_cargo')
    gerente = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, db_column='fk_gerente')
    valor_hora = models.DecimalField(max_digits=8, decimal_places=2, default=40.00, help_text="Valor/hora do desenvolvedor (R$)")

    class Meta:
        db_table = 'dim_funcionario'

class DimTempo(models.Model):
    id = models.IntegerField(primary_key=True) 
    data_completa = models.DateField(unique=True)
    ano = models.IntegerField()
    trimestre = models.CharField(max_length=2)
    mes = models.IntegerField()
    nome_mes = models.CharField(max_length=20)
    dia_do_mes = models.IntegerField()
    dia_da_semana = models.CharField(max_length=20)

    class Meta:
        db_table = 'dim_tempo'

class FatoRegistroHoras(models.Model):
    projeto = models.ForeignKey(DimProjeto, on_delete=models.SET_NULL, null=True, db_column='fk_projeto')
    funcionario = models.ForeignKey(DimFuncionario, on_delete=models.SET_NULL, null=True, db_column='fk_funcionario')
    data = models.ForeignKey(DimTempo, on_delete=models.SET_NULL, null=True, db_column='fk_data')
    horas_gastas = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    custo_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        db_table = 'fato_registro_horas'