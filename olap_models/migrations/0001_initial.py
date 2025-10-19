import django.db.models.deletion
from django.db import migrations, models

# Disable pylint duplicate-code for generated migration file
# pylint: disable=duplicate-code


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='DimCargo',
            fields=[
                ('id', models.BigAutoField(auto_created=True,
                 primary_key=True, serialize=False, verbose_name='ID')),
                ('nome_cargo', models.CharField(max_length=20, unique=True)),
            ],
            options={
                'db_table': 'dim_cargo',
            },
        ),
        migrations.CreateModel(
            name='DimProjeto',
            fields=[
                ('id', models.BigAutoField(auto_created=True,
                 primary_key=True, serialize=False, verbose_name='ID')),
                ('nome_projeto', models.CharField(max_length=100)),
                ('data_criacao', models.DateField(blank=True, null=True)),
            ],
            options={
                'db_table': 'dim_projeto',
            },
        ),
        migrations.CreateModel(
            name='DimTempo',
            fields=[
                ('id', models.IntegerField(primary_key=True, serialize=False)),
                ('data_completa', models.DateField(unique=True)),
                ('ano', models.IntegerField()),
                ('trimestre', models.CharField(max_length=2)),
                ('mes', models.IntegerField()),
                ('nome_mes', models.CharField(max_length=20)),
                ('dia_do_mes', models.IntegerField()),
                ('dia_da_semana', models.CharField(max_length=20)),
            ],
            options={
                'db_table': 'dim_tempo',
            },
        ),
        migrations.CreateModel(
            name='DimFuncionario',
            fields=[
                ('id', models.BigAutoField(auto_created=True,
                 primary_key=True, serialize=False, verbose_name='ID')),
                ('nome_funcionario', models.CharField(max_length=100)),
                ('time', models.CharField(blank=True, max_length=100)),
                ('data_contratacao', models.DateField(blank=True, null=True)),
                ('cargo', models.ForeignKey(db_column='fk_cargo', null=True,
                 on_delete=django.db.models.deletion.SET_NULL, to='olap_models.dimcargo')),
                ('gerente', models.ForeignKey(blank=True, db_column='fk_gerente', null=True,
                 on_delete=django.db.models.deletion.SET_NULL, to='olap_models.dimfuncionario')),
            ],
            options={
                'db_table': 'dim_funcionario',
            },
        ),
        migrations.CreateModel(
            name='FatoRegistroHoras',
            fields=[
                ('id', models.BigAutoField(auto_created=True,
                 primary_key=True, serialize=False, verbose_name='ID')),
                ('horas_gastas', models.DecimalField(
                    decimal_places=2, default=0, max_digits=6)),
                ('data', models.ForeignKey(db_column='fk_data', null=True,
                 on_delete=django.db.models.deletion.SET_NULL, to='olap_models.dimtempo')),
                ('funcionario', models.ForeignKey(db_column='fk_funcionario', null=True,
                 on_delete=django.db.models.deletion.SET_NULL, to='olap_models.dimfuncionario')),
                ('projeto', models.ForeignKey(db_column='fk_projeto', null=True,
                 on_delete=django.db.models.deletion.SET_NULL, to='olap_models.dimprojeto')),
            ],
            options={
                'db_table': 'fato_registro_horas',
            },
        ),
    ]
