"""Unit tests for CustoPorDesenvolvedorService."""

from decimal import Decimal

from django.test import TestCase

from apps.dashboards.projetos.services import CustoPorDesenvolvedorService
from olap_models.models import DimFuncionario, DimProjeto, DimTempo, FatoRegistroHoras


class CustoPorDesenvolvedorServiceTest(TestCase):
    """Test suite for CustoPorDesenvolvedorService."""

    databases = {'default', 'olap'}

    @classmethod
    def setUpTestData(cls):
        """Set up test data for all test methods."""
        cls.projeto = DimProjeto.objects.using('olap').create(
            nome="Projeto Teste"
        )

        cls.funcionario1 = DimFuncionario.objects.using('olap').create(
            nome="João Silva",
            valor_hora=Decimal("50.00")
        )

        cls.funcionario2 = DimFuncionario.objects.using('olap').create(
            nome="Maria Santos",
            valor_hora=Decimal("45.00")
        )

        cls.tempo = DimTempo.objects.using('olap').create(
            data_completa="2024-01-15",
            dia=15,
            mes=1,
            ano=2024,
            trimestre="Q1",
            dia_da_semana="Segunda-feira"
        )

    def setUp(self):
        """Set up test fixtures before each test method."""
        FatoRegistroHoras.objects.using('olap').create(
            funcionario=self.funcionario1,
            projeto=self.projeto,
            data=self.tempo,
            horas_trabalhadas=Decimal("100.00"),
            custo=Decimal("5000.00")
        )

        FatoRegistroHoras.objects.using('olap').create(
            funcionario=self.funcionario2,
            projeto=self.projeto,
            data=self.tempo,
            horas_trabalhadas=Decimal("90.00"),
            custo=Decimal("4050.00")
        )

    def tearDown(self):
        """Clean up after each test method."""
        FatoRegistroHoras.objects.using('olap').all().delete()

    def test_obter_custo_sem_filtro_retorna_todos_desenvolvedores_ordenados(self):
        """
        Given: Registros de horas de múltiplos desenvolvedores
        When: Obtendo custos sem filtro de projeto
        Then: Deve retornar todos desenvolvedores ordenados por custo decrescente
        """
        service = CustoPorDesenvolvedorService()
        resultado = service.obter_custo_por_desenvolvedor()

        self.assertEqual(len(resultado), 2)
        self.assertEqual(resultado[0]['nome'], "João Silva")
        self.assertEqual(resultado[0]['custo'], Decimal("5000.00"))
        self.assertEqual(resultado[1]['nome'], "Maria Santos")
        self.assertEqual(resultado[1]['custo'], Decimal("4050.00"))

    def test_obter_custo_com_filtro_projeto_retorna_apenas_projeto_especifico(self):
        """
        Given: Registros em múltiplos projetos
        When: Filtrando por projeto específico
        Then: Deve retornar apenas custos do projeto filtrado
        """
        outro_projeto = DimProjeto.objects.using('olap').create(
            nome="Outro Projeto"
        )

        FatoRegistroHoras.objects.using('olap').create(
            funcionario=self.funcionario1,
            projeto=outro_projeto,
            data=self.tempo,
            horas_trabalhadas=Decimal("50.00"),
            custo=Decimal("2500.00")
        )

        service = CustoPorDesenvolvedorService()
        resultado = service.obter_custo_por_desenvolvedor(
            projeto_id=self.projeto.id
        )

        self.assertEqual(len(resultado), 2)
        self.assertEqual(resultado[0]['custo'], Decimal("5000.00"))
        self.assertEqual(resultado[1]['custo'], Decimal("4050.00"))

    def test_obter_custo_sem_dados_retorna_lista_vazia(self):
        """
        Given: Nenhum registro de horas
        When: Obtendo custos
        Then: Deve retornar lista vazia
        """
        FatoRegistroHoras.objects.using('olap').all().delete()

        service = CustoPorDesenvolvedorService()
        resultado = service.obter_custo_por_desenvolvedor()

        self.assertEqual(resultado, [])

    def test_formatar_para_grafico_com_dados_retorna_estrutura_correta(self):
        """
        Given: Lista de desenvolvedores com custos
        When: Formatando para gráfico
        Then: Deve retornar labels, values e max_value com margem de 10%
        """
        service = CustoPorDesenvolvedorService()
        dados = [
            {'nome': 'João Silva', 'custo': Decimal('5000.00')},
            {'nome': 'Maria Santos', 'custo': Decimal('4050.00')}
        ]

        resultado = service.formatar_para_grafico(dados)

        self.assertEqual(resultado['labels'], ['João Silva', 'Maria Santos'])
        self.assertEqual(resultado['values'], [5000.00, 4050.00])
        self.assertAlmostEqual(resultado['max_value'], 5500.00, places=2)

    def test_formatar_para_grafico_sem_dados_retorna_estrutura_vazia(self):
        """
        Given: Lista vazia de desenvolvedores
        When: Formatando para gráfico
        Then: Deve retornar estrutura vazia com valores zerados
        """
        service = CustoPorDesenvolvedorService()
        resultado = service.formatar_para_grafico([])

        self.assertEqual(resultado, {
            'labels': [],
            'values': [],
            'max_value': 0
        })

    def test_formatar_para_grafico_com_um_desenvolvedor_calcula_max_value_corretamente(self):
        """
        Given: Apenas um desenvolvedor
        When: Formatando para gráfico
        Then: Deve calcular max_value com margem de 10%
        """
        service = CustoPorDesenvolvedorService()
        dados = [{'nome': 'João Silva', 'custo': Decimal('1000.00')}]

        resultado = service.formatar_para_grafico(dados)

        self.assertEqual(len(resultado['labels']), 1)
        self.assertEqual(len(resultado['values']), 1)
        self.assertAlmostEqual(resultado['max_value'], 1100.00, places=2)
