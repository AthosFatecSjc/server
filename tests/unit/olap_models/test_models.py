from datetime import date

from django.test import TestCase

from olap_models.models import DimFuncionario, DimTempo


class DimModelsTests(TestCase):
    databases = {"olap"}

    def test_dim_funcionario_save_sets_defaults(self):
        funcionario = DimFuncionario.objects.using("olap").create(
            nome="Alice Example",
            cargo="",
            nome_gerente="",
        )

        # Após salvar, os campos devem ter sido normalizados
        self.assertEqual(funcionario.cargo, "dev")
        self.assertEqual(funcionario.nome_gerente, "Alice Example")

    def test_dim_tempo_str_retorna_dados_formatados(self):
        tempo = DimTempo.objects.using("olap").create(
            data_completa=date(2024, 1, 1),
            ano=2024,
            mes=1,
            dia=1,
            trimestre="T1",
            hora=0,
            mes_nome="Janeiro",
            dia_da_semana="Segunda",
        )

        tempo_str = str(tempo)
        self.assertIn("2024", tempo_str)
