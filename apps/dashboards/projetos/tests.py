"""Testes para os serviços do dashboard de projetos."""

# pylint: disable=protected-access

from datetime import datetime
from decimal import Decimal

from django.test import TestCase

from apps.dashboards.projetos.services import (
    CustoPorDesenvolvedorService,
    DashboardProjetoPdfService,
    DashboardProjetoService,
    OrcamentoInvalidoError,
    ProjetoNaoEncontradoError,
)
from apps.relatorios.models import Projeto
from olap_models.models import DimFuncionario, DimProjeto, DimTempo, FatoRegistroHoras


class CustoPorDesenvolvedorServiceTest(TestCase):
    """Testes para o módulo de dashboards de projetos.

    Os testes unitários foram movidos para a estrutura:
    tests/unit/apps/dashboards/projetos/test_services.py

    Esta mudança segue as boas práticas de organização de testes,
    separando testes unitários em uma hierarquia dedicada.
    """

    databases = {"default", "olap"}

    def setUp(self):
        """Cria dados de exemplo no banco OLAP para os testes."""
        self.projeto = DimProjeto.objects.using("olap").create(nome="Projeto Teste")

        self.funcionario1 = DimFuncionario.objects.using("olap").create(
            nome="João Silva", valor_hora=Decimal("50.00")
        )

        self.funcionario2 = DimFuncionario.objects.using("olap").create(
            nome="Maria Santos", valor_hora=Decimal("45.00")
        )

        self.tempo = DimTempo.objects.using("olap").create(
            data_completa="2024-01-15",
            dia=15,
            mes=1,
            ano=2024,
            trimestre="Q1",
            dia_da_semana="Segunda-feira",
        )

        FatoRegistroHoras.objects.using("olap").create(
            funcionario=self.funcionario1,
            projeto=self.projeto,
            data=self.tempo,
            horas_trabalhadas=Decimal("100.00"),
            custo=Decimal("5000.00"),  # 100h * R$50
        )

        FatoRegistroHoras.objects.using("olap").create(
            funcionario=self.funcionario2,
            projeto=self.projeto,
            data=self.tempo,
            horas_trabalhadas=Decimal("90.00"),
            custo=Decimal("4050.00"),  # 90h * R$45
        )

    def test_obter_custo_por_desenvolvedor_sem_filtro(self):
        """Testa obtenção de custos sem filtrar por projeto."""
        service = CustoPorDesenvolvedorService()
        resultado = service.obter_custo_por_desenvolvedor()

        self.assertEqual(len(resultado), 2)

        self.assertEqual(resultado[0]["nome"], "João Silva")
        self.assertEqual(resultado[0]["custo"], Decimal("5000.00"))
        self.assertEqual(resultado[1]["nome"], "Maria Santos")
        self.assertEqual(resultado[1]["custo"], Decimal("4050.00"))

    def test_obter_custo_por_desenvolvedor_com_filtro_projeto(self):
        """Testa obtenção de custos filtrando por projeto."""
        outro_projeto = DimProjeto.objects.using("olap").create(nome="Outro Projeto")

        FatoRegistroHoras.objects.using("olap").create(
            funcionario=self.funcionario1,
            projeto=outro_projeto,
            data=self.tempo,
            horas_trabalhadas=Decimal("50.00"),
            custo=Decimal("2500.00"),
        )

        service = CustoPorDesenvolvedorService()
        resultado = service.obter_custo_por_desenvolvedor(projeto_id=self.projeto.id)

        self.assertEqual(len(resultado), 2)
        self.assertEqual(resultado[0]["custo"], Decimal("5000.00"))

    def test_obter_custo_por_desenvolvedor_sem_dados(self):
        """Testa comportamento quando não há dados."""
        FatoRegistroHoras.objects.using("olap").all().delete()

        service = CustoPorDesenvolvedorService()
        resultado = service.obter_custo_por_desenvolvedor()
        self.assertEqual(len(resultado), 0)

    def test_formatar_para_grafico_com_dados(self):
        """Testa formatação de dados para o gráfico."""
        service = CustoPorDesenvolvedorService()
        dados = [
            {"nome": "João Silva", "custo": Decimal("5000.00")},
            {"nome": "Maria Santos", "custo": Decimal("4050.00")},
        ]

        resultado = service.formatar_para_grafico(dados)

        self.assertEqual(resultado["labels"], ["João Silva", "Maria Santos"])
        self.assertEqual(resultado["values"], [5000.00, 4050.00])
        self.assertAlmostEqual(resultado["max_value"], 5500.00, places=2)

    def test_formatar_para_grafico_sem_dados(self):
        """Testa formatação quando não há dados."""
        service = CustoPorDesenvolvedorService()
        resultado = service.formatar_para_grafico([])
        self.assertEqual(resultado["labels"], [])
        self.assertEqual(resultado["values"], [])
        self.assertEqual(resultado["max_value"], 0)

    def test_formatar_para_grafico_com_um_dado(self):
        """Testa formatação com apenas um desenvolvedor."""
        service = CustoPorDesenvolvedorService()
        dados = [{"nome": "João Silva", "custo": Decimal("1000.00")}]
        resultado = service.formatar_para_grafico(dados)

        self.assertEqual(len(resultado["labels"]), 1)
        self.assertEqual(len(resultado["values"]), 1)
        self.assertAlmostEqual(resultado["max_value"], 1100.00, places=2)


class DashboardProjetoServiceTest(TestCase):  # pylint: disable=protected-access
    """Testes unitários para o DashboardProjetoService."""

    databases = {"default", "olap"}

    def setUp(self):
        self.projeto = Projeto.objects.create(
            nome="Projeto Financeiro",
            orcamento_previsto=Decimal("20000.00"),
            data_criacao=datetime.now(),
        )

    def test_parse_valor_orcamento_valido(self):
        valor = DashboardProjetoService._parse_valor_orcamento("15000.50")
        self.assertEqual(valor, Decimal("15000.50"))

    def test_parse_valor_orcamento_invalido(self):
        with self.assertRaises(OrcamentoInvalidoError):
            DashboardProjetoService._parse_valor_orcamento("abc")

    def test_parse_valor_orcamento_vazio(self):
        with self.assertRaises(OrcamentoInvalidoError):
            DashboardProjetoService._parse_valor_orcamento("")

    def test_atualizar_orcamento_previsto_sucesso(self):
        result = DashboardProjetoService.atualizar_orcamento_previsto(
            self.projeto.id, "20000"
        )
        self.projeto.refresh_from_db()
        self.assertEqual(self.projeto.orcamento_previsto, Decimal("20000"))
        self.assertIn("orcamento_previsto", result)
        self.assertEqual(result["orcamento_previsto"], 20000.0)

    def test_atualizar_orcamento_previsto_inexistente(self):
        with self.assertRaises(ProjetoNaoEncontradoError):
            DashboardProjetoService.atualizar_orcamento_previsto(9999, "15000")

    def test_to_float_conversoes(self):
        self.assertEqual(DashboardProjetoService._to_float(Decimal("10.5")), 10.5)
        self.assertEqual(DashboardProjetoService._to_float("10.5"), 10.5)
        self.assertEqual(DashboardProjetoService._to_float(None), 0.0)
        self.assertEqual(DashboardProjetoService._to_float("abc"), 0.0)

    def test_criar_contexto_base(self):
        contexto = DashboardProjetoService._criar_contexto_base(
            1, "Teste", datetime.now()
        )
        self.assertIn("orcamento_previsto", contexto)
        self.assertEqual(contexto["total_custo"], Decimal("0"))

    def test_calcular_metricas_financeiras(self):
        resultado = DashboardProjetoService._calcular_metricas_financeiras(
            self.projeto.id, Decimal("10000")
        )
        self.assertIn("orcamento_previsto", resultado)
        self.assertEqual(resultado["orcamento_previsto"], 10000.0)


class DashboardProjetoPdfServiceTest(TestCase):  # pylint: disable=protected-access
    """Testes unitários para o DashboardProjetoPdfService."""

    databases = {"default", "olap"}

    def test_format_currency(self):
        self.assertEqual(
            DashboardProjetoPdfService._format_currency(1234.56), "R$ 1.234,56"
        )

    def test_build_cards_table(self):
        dados = {
            "orcamento_previsto": 20000,
            "custo_realizado": 5000,
            "saldo_remanescente": 15000,
            "percentual_utilizado": 25.0,
        }
        tabela = DashboardProjetoPdfService._build_cards_table(dados)
        self.assertEqual(len(tabela._cellvalues), 4)

    def test_build_dev_table_com_dados(self):
        dados = {
            "custo_por_dev": [
                {
                    "funcionario_nome": "Ruth Mira",
                    "total_horas": 40,
                    "valor_hora": 120.0,
                    "custo_total": 4800.0,
                }
            ]
        }
        tabela = DashboardProjetoPdfService._build_dev_table(dados)
        self.assertIn("Ruth Mira", str(tabela._cellvalues))

    def test_build_dev_table_sem_dados(self):
        dados = {"custo_por_dev": []}
        tabela = DashboardProjetoPdfService._build_dev_table(dados)
        self.assertIn("Nenhum registro encontrado", str(tabela._cellvalues))

    def test_gerar_pdf_bytes(self):
        dados = {
            "nome_projeto": "Athos Insight",
            "orcamento_previsto": 20000.0,
            "custo_realizado": 10000.0,
            "saldo_remanescente": 10000.0,
            "percentual_utilizado": 50.0,
            "custo_por_dev": [
                {
                    "funcionario_nome": "Renato Mendes",
                    "total_horas": 35,
                    "valor_hora": 150.0,
                    "custo_total": 5250.0,
                }
            ],
            "data_geracao": datetime.now(),
        }
        pdf = DashboardProjetoPdfService.gerar_pdf(dados)
        self.assertIsInstance(pdf, bytes)
        self.assertGreater(len(pdf), 1000)
