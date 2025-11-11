from __future__ import annotations

from decimal import Decimal
from io import BytesIO
from unittest.mock import MagicMock, patch

from django.test import TestCase
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch

from apps.relatorios.atividade.services import AtividadeService
from olap_models.models import DimFuncionario, DimProjeto, DimTempo, FatoRegistroHoras


class AtividadeServiceDatabaseTests(TestCase):
    databases = {"default", "olap"}

    @classmethod
    def setUpTestData(cls):
        cls.projeto_a = DimProjeto.objects.using("olap").create(nome="Alpha")
        cls.projeto_b = DimProjeto.objects.using("olap").create(nome="Beta")

        cls.funcionario_ana = DimFuncionario.objects.using("olap").create(
            nome="Ana Dev", valor_hora=Decimal("50.00")
        )
        cls.funcionario_beto = DimFuncionario.objects.using("olap").create(
            nome="Beto QA", valor_hora=Decimal("40.00")
        )

        cls.tempo_dia1 = DimTempo.objects.using("olap").create(
            data_completa="2025-11-01",
            dia=1,
            mes=11,
            ano=2025,
            hora=0,
            trimestre="Q4",
            dia_da_semana="Segunda-feira",
        )
        cls.tempo_dia2 = DimTempo.objects.using("olap").create(
            data_completa="2025-11-02",
            dia=2,
            mes=11,
            ano=2025,
            hora=0,
            trimestre="Q4",
            dia_da_semana="Terça-feira",
        )

        FatoRegistroHoras.objects.using("olap").create(
            funcionario=cls.funcionario_ana,
            projeto=cls.projeto_a,
            data=cls.tempo_dia1,
            horas_trabalhadas=Decimal("8.0"),
            custo=Decimal("0"),
        )
        FatoRegistroHoras.objects.using("olap").create(
            funcionario=cls.funcionario_ana,
            projeto=cls.projeto_b,
            data=cls.tempo_dia1,
            horas_trabalhadas=Decimal("2.0"),
            custo=Decimal("0"),
        )
        FatoRegistroHoras.objects.using("olap").create(
            funcionario=cls.funcionario_beto,
            projeto=cls.projeto_a,
            data=cls.tempo_dia2,
            horas_trabalhadas=Decimal("4.0"),
            custo=Decimal("0"),
        )

    def test_resolve_database_alias_default_and_custom(self):
        self.assertEqual(AtividadeService._resolve_database_alias(None), "olap")
        self.assertEqual(AtividadeService._resolve_database_alias("custom"), "custom")

    def test_aplicar_filtros_base_combinado(self):
        queryset = MagicMock()
        queryset.filter.return_value = queryset

        resultado = AtividadeService._aplicar_filtros_base(
            queryset, projeto_id=1, funcionario_id=2
        )

        self.assertIs(resultado, queryset)
        queryset.filter.assert_any_call(projeto_id=1)
        queryset.filter.assert_any_call(funcionario_id=2)

        queryset.filter.reset_mock()
        AtividadeService._aplicar_filtros_base(queryset, None, None)
        queryset.filter.assert_not_called()

    def test_listar_projetos_disponiveis_ordenados(self):
        nomes = [
            projeto["nome"]
            for projeto in AtividadeService.listar_projetos_disponiveis()
        ]
        self.assertEqual(nomes, ["Alpha", "Beta"])

    def test_listar_projetos_disponiveis_trata_excecao(self):
        with patch(
            "apps.relatorios.atividade.services.DimProjeto.objects.using",
            side_effect=RuntimeError("fail"),
        ):
            self.assertEqual(AtividadeService.listar_projetos_disponiveis(), [])

    def test_listar_colaboradores_disponiveis(self):
        nomes = [
            colaborador["nome"]
            for colaborador in AtividadeService.listar_colaboradores_disponiveis()
        ]
        self.assertEqual(nomes, ["Ana Dev", "Beto QA"])

    def test_listar_colaboradores_disponiveis_trata_excecao(self):
        with patch(
            "apps.relatorios.atividade.services.DimFuncionario.objects.using",
            side_effect=RuntimeError("ops"),
        ):
            self.assertEqual(AtividadeService.listar_colaboradores_disponiveis(), [])

    def test_buscar_horas_detalhadas_sem_filtro(self):
        dados = list(AtividadeService._buscar_horas_detalhadas(2025, 11))
        nomes = {(item["funcionario__nome"], item["projeto__nome"]) for item in dados}
        self.assertIn(("Ana Dev", "Alpha"), nomes)
        self.assertIn(("Ana Dev", "Beta"), nomes)
        self.assertIn(("Beto QA", "Alpha"), nomes)

    def test_buscar_horas_detalhadas_filtra_projeto(self):
        dados = list(
            AtividadeService._buscar_horas_detalhadas(
                2025, 11, projeto_id=self.projeto_b.id
            )
        )
        self.assertEqual(len(dados), 1)
        self.assertEqual(dados[0]["projeto__nome"], "Beta")

    def test_processar_dados_horas_detalhadas_trata_nulos(self):
        bruto = [
            {
                "funcionario__nome": None,
                "projeto__nome": None,
                "total_horas": Decimal("3"),
            },
            {
                "funcionario__nome": "Ana Dev",
                "projeto__nome": "Alpha",
                "total_horas": Decimal("1"),
            },
        ]
        por_projeto, total_por_dev = AtividadeService._processar_dados_horas_detalhadas(
            bruto
        )
        self.assertEqual(
            por_projeto[0]["funcionario"], AtividadeService.FUNCIONARIO_PADRAO
        )
        self.assertEqual(total_por_dev[0]["total_horas"], 3)
        self.assertEqual(total_por_dev[1]["total_horas"], 1)

    def test_horas_por_dev_e_projeto_por_mes_retorna_chaves(self):
        resultado = AtividadeService.horas_por_dev_e_projeto_por_mes(2025, 11)
        self.assertIn("por_projeto", resultado)
        self.assertIn("total_por_dev", resultado)
        self.assertGreater(len(resultado["por_projeto"]), 0)

    def test_soma_horas_por_dev_por_mes_filtra_funcionario(self):
        horas = AtividadeService.soma_horas_por_dev_por_mes(
            2025, 11, funcionario_id=self.funcionario_ana.id
        )
        self.assertEqual(len(horas), 1)
        self.assertEqual(horas[0]["funcionario"], "Ana Dev")
        self.assertAlmostEqual(horas[0]["total_horas"], 10.0)

    def test_gerar_dados_relatorio_atividade_retorna_resumo(self):
        dados = AtividadeService.gerar_dados_relatorio_atividade(2025, 11)
        self.assertEqual(dados["total_geral"], 14.0)
        self.assertEqual(sorted(dados["projetos_nomes"]), ["Alpha", "Beta"])
        self.assertEqual(len(dados["dados_cards"]), 2)

    def test_gerar_dados_relatorio_sem_registros(self):
        FatoRegistroHoras.objects.using("olap").all().delete()
        dados = AtividadeService.gerar_dados_relatorio_atividade(2025, 11)
        self.assertEqual(dados["dados_tabela"], [])
        self.assertEqual(dados["dados_cards"], [])
        self.assertEqual(dados["total_geral"], 0.0)

    def test_gerar_grafico_pizza_com_e_sem_dados(self):
        buffer = AtividadeService._gerar_grafico_pizza(
            [{"label": "Alpha", "valor": 10}], "Teste", "label", "valor"
        )
        self.assertIsNotNone(buffer)
        vazio = AtividadeService._gerar_grafico_pizza([], "Teste", "label", "valor")
        self.assertIsNone(vazio)

    def test_gerar_graficos_prontos(self):
        dados = AtividadeService.gerar_dados_relatorio_atividade(2025, 11)
        self.assertIsNotNone(
            AtividadeService._gerar_grafico_pizza_projetos(dados["dados_cards"])
        )
        self.assertIsNotNone(
            AtividadeService._gerar_grafico_pizza_desenvolvedores(dados["dados_tabela"])
        )

    def test_gerar_tabelas_e_secoes_pdf(self):
        dados = AtividadeService.gerar_dados_relatorio_atividade(2025, 11)
        styles = getSampleStyleSheet()

        self.assertTrue(
            AtividadeService._gerar_tabela_horas_por_dev_e_projeto(dados, styles)
        )
        self.assertTrue(
            AtividadeService._gerar_tabela_total_horas_por_dev(dados, styles)
        )
        self.assertTrue(
            AtividadeService._gerar_tabela_total_horas_por_projeto(dados, styles)
        )
        self.assertTrue(AtividadeService._gerar_secao_grafico_projetos(dados))
        self.assertTrue(AtividadeService._gerar_secao_grafico_desenvolvedores(dados))

    def test_secoes_graficas_sem_dados(self):
        seco = {"dados_cards": [], "dados_tabela": []}
        self.assertEqual(AtividadeService._gerar_secao_grafico_projetos(seco), [])
        self.assertEqual(
            AtividadeService._gerar_secao_grafico_desenvolvedores(seco), []
        )

    def test_footer_titulo_documento_e_pdf(self):
        styles = getSampleStyleSheet()
        footer = AtividadeService._gerar_footer(styles)
        self.assertIn("Gerado em", footer.getPlainText())

        documento = AtividadeService._configurar_documento_pdf(BytesIO())
        self.assertAlmostEqual(documento.leftMargin, 0.2 * inch)
        self.assertAlmostEqual(documento.topMargin, 0.3 * inch)

        titulo = AtividadeService._criar_titulo_relatorio(11, 2025, styles)
        self.assertEqual(len(titulo), 2)
        self.assertIn("Relatório de Atividades", titulo[0].getPlainText())

        dados = AtividadeService.gerar_dados_relatorio_atividade(2025, 11)
        combinados = AtividadeService._combinar_elementos_relatorio(dados, styles)
        self.assertGreater(len(combinados), 0)

        pdf = AtividadeService.exportar_atividade_pdf(11, 2025, dados)
        self.assertGreater(len(pdf), 0)
