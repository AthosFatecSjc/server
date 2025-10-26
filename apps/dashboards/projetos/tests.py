"""Testes para os serviços do dashboard de projetos."""

from decimal import Decimal

from django.test import TestCase

from apps.dashboards.projetos.services import CustoPorDesenvolvedorService
from olap_models.models import DimFuncionario, DimProjeto, DimTempo, FatoRegistroHoras


class CustoPorDesenvolvedorServiceTest(TestCase):
    """Testes para o módulo de dashboards de projetos.

Os testes unitários foram movidos para a estrutura:
tests/unit/apps/dashboards/projetos/test_services.py

Esta mudança segue as boas práticas de organização de testes,
separando testes unitários em uma hierarquia dedicada.
"""

    def setUp(self):
        """Configuração inicial dos testes."""
        # Criar projeto
        self.projeto = DimProjeto.objects.create(
            nome="Projeto Teste"
        )
        
        # Criar funcionários
        self.funcionario1 = DimFuncionario.objects.create(
            nome="João Silva",
            valor_hora=Decimal("50.00")
        )
        
        self.funcionario2 = DimFuncionario.objects.create(
            nome="Maria Santos",
            valor_hora=Decimal("45.00")
        )
        
        # Criar dimensão tempo
        self.tempo = DimTempo.objects.create(
            data_completa="2024-01-15",
            dia=15,
            mes=1,
            ano=2024,
            trimestre="Q1",
            dia_da_semana="Segunda-feira"
        )
        
        # Criar registros de horas
        FatoRegistroHoras.objects.create(
            funcionario=self.funcionario1,
            projeto=self.projeto,
            data=self.tempo,
            horas_trabalhadas=Decimal("100.00"),
            custo=Decimal("5000.00")  # 100h * R$50
        )
        
        FatoRegistroHoras.objects.create(
            funcionario=self.funcionario2,
            projeto=self.projeto,
            data=self.tempo,
            horas_trabalhadas=Decimal("90.00"),
            custo=Decimal("4050.00")  # 90h * R$45
        )

    def test_obter_custo_por_desenvolvedor_sem_filtro(self):
        """Testa obtenção de custos sem filtrar por projeto."""
        service = CustoPorDesenvolvedorService()
        resultado = service.obter_custo_por_desenvolvedor()
        
        self.assertEqual(len(resultado), 2)
        
        # Deve estar ordenado por custo decrescente
        self.assertEqual(resultado[0]['nome'], "João Silva")
        self.assertEqual(resultado[0]['custo'], Decimal("5000.00"))
        
        self.assertEqual(resultado[1]['nome'], "Maria Santos")
        self.assertEqual(resultado[1]['custo'], Decimal("4050.00"))

    def test_obter_custo_por_desenvolvedor_com_filtro_projeto(self):
        """Testa obtenção de custos filtrando por projeto."""
        # Criar outro projeto e registro
        outro_projeto = DimProjeto.objects.create(nome="Outro Projeto")
        
        FatoRegistroHoras.objects.create(
            funcionario=self.funcionario1,
            projeto=outro_projeto,
            data=self.tempo,
            horas_trabalhadas=Decimal("50.00"),
            custo=Decimal("2500.00")
        )
        
        service = CustoPorDesenvolvedorService()
        
        # Filtrar pelo projeto original
        resultado = service.obter_custo_por_desenvolvedor(projeto_id=self.projeto.id)
        
        # Deve retornar apenas os custos do projeto filtrado
        self.assertEqual(len(resultado), 2)
        self.assertEqual(resultado[0]['custo'], Decimal("5000.00"))

    def test_obter_custo_por_desenvolvedor_sem_dados(self):
        """Testa comportamento quando não há dados."""
        # Limpar todos os registros
        FatoRegistroHoras.objects.all().delete()
        
        service = CustoPorDesenvolvedorService()
        resultado = service.obter_custo_por_desenvolvedor()
        
        self.assertEqual(len(resultado), 0)

    def test_formatar_para_grafico_com_dados(self):
        """Testa formatação de dados para o gráfico."""
        service = CustoPorDesenvolvedorService()
        dados = [
            {'nome': 'João Silva', 'custo': Decimal('5000.00')},
            {'nome': 'Maria Santos', 'custo': Decimal('4050.00')}
        ]
        
        resultado = service.formatar_para_grafico(dados)
        
        self.assertEqual(resultado['labels'], ['João Silva', 'Maria Santos'])
        self.assertEqual(resultado['values'], [5000.00, 4050.00])
        
        # Max value deve ter margem de 10%
        self.assertAlmostEqual(resultado['max_value'], 5500.00, places=2)

    def test_formatar_para_grafico_sem_dados(self):
        """Testa formatação quando não há dados."""
        service = CustoPorDesenvolvedorService()
        resultado = service.formatar_para_grafico([])
        
        self.assertEqual(resultado['labels'], [])
        self.assertEqual(resultado['values'], [])
        self.assertEqual(resultado['max_value'], 0)

    def test_formatar_para_grafico_com_um_dado(self):
        """Testa formatação com apenas um desenvolvedor."""
        service = CustoPorDesenvolvedorService()
        dados = [
            {'nome': 'João Silva', 'custo': Decimal('1000.00')}
        ]
        
        resultado = service.formatar_para_grafico(dados)
        
        self.assertEqual(len(resultado['labels']), 1)
        self.assertEqual(len(resultado['values']), 1)
        self.assertAlmostEqual(resultado['max_value'], 1100.00, places=2)
