import io
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from apps.relatorios.models import (
    Cargo,
    ControleHorasEquipe,
    Funcionario,
    Projeto,
    TempoGastoEquipe,
)
from olap_models.management.commands.rodar_etl import Command
from olap_models.models import (
    DimCargo,
    DimFuncionario,
    DimProjeto,
    DimTempo,
    FatoRegistroHoras,
)


class RodarEtlCommandTests(TestCase):
    databases = {"default", "olap"}

    def setUp(self):
        self.command = Command()
        self.command.stdout = io.StringIO()

        self.cargo = Cargo.objects.create(sigla="DEV")
        self.gerente = Funcionario.objects.create(nome="Gerente", cargo=self.cargo)
        self.funcionario = Funcionario.objects.create(
            nome="Alice",
            cargo=self.cargo,
            gerente=self.gerente,
            valor_hora=Decimal("80.00"),
        )
        self.projeto = Projeto.objects.create(nome="Projeto XPTO")

        self.controle = ControleHorasEquipe.objects.create(
            mes=date(2024, 1, 1),
            projeto=self.projeto,
            funcionario=self.funcionario,
            horas=Decimal("10.00"),
        )

        TempoGastoEquipe.objects.create(
            dia_mes=1,
            mes=date(2024, 1, 1),
            funcionario=self.funcionario,
            tempo_gasto=Decimal("8.0"),
        )

        # Registro inválido para exercitar o tratamento de ValueError
        TempoGastoEquipe.objects.create(
            dia_mes=31,
            mes=date(2024, 2, 1),
            funcionario=self.funcionario,
            tempo_gasto=Decimal("5.0"),
        )

    def test_handle_executa_etapas_na_ordem(self):
        command = Command()
        command.stdout = io.StringIO()

        with (
            patch.object(command, "limpar_tabelas_olap") as limpar,
            patch.object(command, "popular_dim_tempo") as tempo,
            patch.object(command, "popular_dimensoes_simples") as dims,
            patch.object(command, "popular_dim_funcionario") as dim_func,
            patch.object(command, "popular_fato_registro_horas") as fato,
            patch(
                "olap_models.management.commands.rodar_etl.datetime"
            ) as mock_datetime,
        ):
            mock_datetime.now.return_value = datetime(2024, 1, 1, 12, 0, 0)
            mock_datetime.side_effect = lambda *args, **kwargs: datetime(
                *args, **kwargs
            )

            command.handle()

        limpar.assert_called_once()
        tempo.assert_called_once()
        dims.assert_called_once()
        dim_func.assert_called_once()
        fato.assert_called_once()

    def test_limpar_tabelas_olap_remove_dados(self):
        DimTempo.objects.using("olap").create(
            data_completa=date(2023, 1, 1),
            ano=2023,
            mes=1,
            dia=1,
            trimestre="T1",
            hora=0,
            mes_nome="Janeiro",
            dia_da_semana="Domingo",
        )
        DimProjeto.objects.using("olap").create(nome="Antigo")

        self.command.limpar_tabelas_olap()

        self.assertEqual(DimTempo.objects.using("olap").count(), 0)
        self.assertEqual(DimProjeto.objects.using("olap").count(), 0)

    def test_popular_dim_tempo_cria_registros(self):
        with patch(
            "olap_models.management.commands.rodar_etl.datetime"
        ) as mock_datetime:
            mock_datetime.now.return_value = datetime(2020, 1, 1)
            mock_datetime.side_effect = lambda *args, **kwargs: datetime(
                *args, **kwargs
            )
            self.command.popular_dim_tempo()

        self.assertTrue(
            DimTempo.objects.using("olap")
            .filter(data_completa=date(2020, 1, 1))
            .exists()
        )
        self.assertTrue(
            DimTempo.objects.using("olap")
            .filter(data_completa=date(2021, 12, 31))
            .exists()
        )

    def test_popular_dimensoes_simples_popula_cargo_e_projeto(self):
        self.command.popular_dimensoes_simples()

        self.assertTrue(
            DimCargo.objects.using("olap").filter(id=self.cargo.id).exists()
        )
        self.assertTrue(
            DimProjeto.objects.using("olap").filter(id=self.projeto.id).exists()
        )

    def test_popular_dim_funcionario_popula_dimensao(self):
        self.command.popular_dimensoes_simples()
        self.command.popular_dim_funcionario()

        dim_func = DimFuncionario.objects.using("olap").get(id=self.funcionario.id)
        self.assertEqual(dim_func.nome, "Alice")
        self.assertEqual(dim_func.nome_gerente, "Gerente")
        self.assertEqual(dim_func.cargo, "DEV")

    def test_popular_fato_registro_horas_cria_registros(self):
        self.command.popular_dim_tempo()
        self.command.popular_dimensoes_simples()
        self.command.popular_dim_funcionario()

        self.command.popular_fato_registro_horas()

        fatos = FatoRegistroHoras.objects.using("olap").all()
        self.assertEqual(fatos.count(), 1)
        fato = fatos[0]
        self.assertAlmostEqual(float(fato.horas_trabalhadas), 8.0)
        self.assertAlmostEqual(float(fato.custo), 640.0)

    def test_popular_fato_registro_horas_ignora_registros_incompletos(self):
        FatoRegistroHoras.objects.using("olap").all().delete()
        self.command.popular_dim_tempo()
        self.command.popular_dimensoes_simples()
        self.command.popular_dim_funcionario()

        # Remove o vínculo do controle no mapa utilizado pelo ETL para simular registro incompleto
        with (
            patch.object(self.command, "stdout") as mock_stdout,
            patch(
                "olap_models.management.commands.rodar_etl.DimProjeto.objects"
            ) as mock_dim_obj,
        ):
            mock_dim_obj.using.return_value.all.return_value = []
            self.command.popular_fato_registro_horas()

        self.assertEqual(FatoRegistroHoras.objects.using("olap").count(), 0)

    def test_command_via_call_command(self):
        with (
            patch.object(Command, "limpar_tabelas_olap") as limpar,
            patch.object(Command, "popular_dim_tempo") as tempo,
            patch.object(Command, "popular_dimensoes_simples"),
            patch.object(Command, "popular_dim_funcionario"),
            patch.object(Command, "popular_fato_registro_horas"),
            patch(
                "olap_models.management.commands.rodar_etl.datetime"
            ) as mock_datetime,
        ):
            mock_datetime.now.return_value = datetime(2024, 1, 1)
            mock_datetime.side_effect = lambda *args, **kwargs: datetime(
                *args, **kwargs
            )

            call_command("rodar_etl")

        limpar.assert_called_once()
        tempo.assert_called_once()
