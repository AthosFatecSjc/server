from datetime import date, timedelta

from django.test import TestCase
from django.utils import timezone

from apps.dashboards.equipes.services import DashboardEquipesService
from olap_models.models import DimFuncionario, DimProjeto, DimTempo, FatoRegistroHoras


class DashboardEquipesServiceTests(TestCase):
    databases = {"default", "olap"}

    @classmethod
    def setUpTestData(cls):
        cls.dev_a = DimFuncionario.objects.using("olap").create(nome="Alice")
        cls.dev_b = DimFuncionario.objects.using("olap").create(nome="Bob")
        cls.projeto_1 = DimProjeto.objects.using("olap").create(
            nome="Projeto 1", data_criacao=date(2024, 1, 1)
        )
        cls.projeto_2 = DimProjeto.objects.using("olap").create(
            nome="Projeto 2", data_criacao=date(2024, 1, 1)
        )

        cls.dim_tempo_recente = DimTempo.objects.using("olap").create(
            data_completa=date.today(),
            dia=date.today().day,
            mes=date.today().month,
            ano=date.today().year,
            trimestre="Q1",
            dia_da_semana="Segunda",
        )

        FatoRegistroHoras.objects.using("olap").create(
            funcionario=cls.dev_a,
            projeto=cls.projeto_1,
            data=cls.dim_tempo_recente,
            horas_trabalhadas=5,
            custo=100,
        )

    def test_get_desenvolvedores_dropdown_filtra_por_projeto(self):
        dropdown = DashboardEquipesService.get_desenvolvedores_dropdown(
            projeto_id=self.projeto_1.id,
            data_inicio_dt=None,
            data_fim_dt=None,
            desenvolvedores_ids=None,
        )

        nomes = {dev["name"] for dev in dropdown}
        self.assertSetEqual(nomes, {"Alice"})
        self.assertTrue(all(dev["selected"] for dev in dropdown))

    def test_get_desenvolvedores_dropdown_fallback_sem_registros(self):
        dropdown = DashboardEquipesService.get_desenvolvedores_dropdown(
            projeto_id=self.projeto_2.id,
            data_inicio_dt=None,
            data_fim_dt=None,
            desenvolvedores_ids=None,
        )

        nomes = {dev["name"] for dev in dropdown}
        self.assertSetEqual(nomes, {"Alice", "Bob"})
        self.assertTrue(all(dev["selected"] for dev in dropdown))

    def test_aplicar_filtros_horas_quando_datas_invalidas_usa_padrao(self):
        registros, data_inicio_dt, data_fim_dt = (
            DashboardEquipesService.aplicar_filtros_horas(
                projeto_id=None,
                data_inicio="invalida",
                data_fim="invalida",
                desenvolvedores_ids=None,
            )
        )

        self.assertGreaterEqual(registros.count(), 1)
        self.assertIsNotNone(data_inicio_dt)
        self.assertIsNotNone(data_fim_dt)
        # Verifica se o registro recente está incluído no range padrão (últimos 30 dias).
        inicio = (
            data_inicio_dt.date() if hasattr(data_inicio_dt, "date") else data_inicio_dt
        )
        fim = data_fim_dt.date() if hasattr(data_fim_dt, "date") else data_fim_dt
        self.assertTrue(inicio <= self.dim_tempo_recente.data_completa <= fim)

    def test_gerar_dados_grafico_horas_retorna_data_iso_e_valores(self):
        registros = FatoRegistroHoras.objects.all()

        dados = DashboardEquipesService.gerar_dados_grafico_horas(registros)

        self.assertEqual(len(dados), 1)
        ponto = dados[0]
        self.assertIn("data_iso", ponto)
        self.assertAlmostEqual(ponto["Alice"], 5.0)
        self.assertEqual(ponto["Bob"], 0.0)
