from io import StringIO
from decimal import Decimal
from unittest.mock import patch
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.relatorios.models import Funcionario
from apps.dashboards.services import JiraService

VALOR_HORA_PADRAO = Decimal('40.00')


class SyncJiraUsersCommandTest(TestCase):
    """
    Testes unitários para o management command `sync_jira_users`.

    Simula a resposta do JiraService para verificar a criação e atualização
    de Funcionarios no banco de dados OLTP.
    """

    def setUp(self):
        """
        Limpa os funcionários antes de cada teste.
        """
        Funcionario.objects.all().delete()

    @patch('apps.dashboards.services.JiraService.get_all_tasks_data')
    def test_sync_creates_new_funcionarios(self, mock_get_all_tasks_data):
        """
        Verifica a criação de novos funcionários com valor/hora padrão.
        """
        mock_get_all_tasks_data.return_value = [
            {'tasks': [{'assignee': 'Alice Wonderland'}]},
            {'tasks': [{'assignee': 'Bob The Builder'}, {'assignee': 'Alice Wonderland'}]}
        ]

        out = StringIO()
        call_command('sync_jira_users', stdout=out)

        self.assertEqual(Funcionario.objects.count(), 2)
        alice = Funcionario.objects.get(nome='Alice Wonderland')
        bob = Funcionario.objects.get(nome='Bob The Builder')
        self.assertEqual(alice.valor_hora, VALOR_HORA_PADRAO)
        self.assertEqual(bob.valor_hora, VALOR_HORA_PADRAO)

        output = out.getvalue()
        self.assertIn('Encontrados 2 utilizadores únicos', output)
        self.assertIn('[CRIADO] Funcionário: Alice Wonderland', output)
        self.assertIn('[CRIADO] Funcionário: Bob The Builder', output)
        self.assertIn('2 funcionários criados.', output)
        self.assertIn('0 funcionários já existentes.', output)

    @patch('apps.dashboards.services.JiraService.get_all_tasks_data')
    def test_sync_does_not_duplicate_existing(self, mock_get_all_tasks_data):
        """
        Verifica que funcionários existentes não são duplicados e
        novos são criados corretamente.
        """
        Funcionario.objects.create(nome='Charlie Chaplin', valor_hora=Decimal('55.00'))
        self.assertEqual(Funcionario.objects.count(), 1)

        mock_get_all_tasks_data.return_value = [
            {'tasks': [{'assignee': 'Charlie Chaplin '}]},
            {'tasks': [{'assignee': 'Diana Prince'}]}
        ]

        out = StringIO()
        call_command('sync_jira_users', stdout=out)

        self.assertEqual(Funcionario.objects.count(), 2)
        charlie = Funcionario.objects.get(nome='Charlie Chaplin')
        diana = Funcionario.objects.get(nome='Diana Prince')
        self.assertEqual(charlie.valor_hora, Decimal('55.00')) # Mantém valor original
        self.assertEqual(diana.valor_hora, VALOR_HORA_PADRAO) # Aplica padrão ao novo

        output = out.getvalue()
        self.assertIn('Encontrados 2 utilizadores únicos', output)
        self.assertIn('[CRIADO] Funcionário: Diana Prince', output)
        self.assertNotIn('[CRIADO] Funcionário: Charlie Chaplin', output)
        self.assertIn('1 funcionários criados.', output)
        self.assertIn('1 funcionários já existentes.', output)

    @patch('apps.dashboards.services.JiraService.get_all_tasks_data')
    def test_sync_handles_no_assignees_found(self, mock_get_all_tasks_data):
        """
        Verifica o comportamento quando não há assignees válidos nos dados do Jira.
        """
        mock_get_all_tasks_data.return_value = [
            {'tasks': [{'assignee': None}]},
            {'tasks': [{'assignee': 'Sem responsável'}]}
        ]

        out = StringIO()
        call_command('sync_jira_users', stdout=out)

        self.assertEqual(Funcionario.objects.count(), 0)
        output = out.getvalue()
        self.assertIn('Nenhum assignee encontrado nas tarefas do Jira.', output)
        self.assertNotIn('[CRIADO]', output)

    @patch('apps.dashboards.services.JiraService.get_all_tasks_data')
    def test_sync_handles_jira_api_error(self, mock_get_all_tasks_data):
        """
        Verifica se um CommandError é levantado se o JiraService retornar None.
        """
        mock_get_all_tasks_data.return_value = None

        with self.assertRaises(CommandError) as cm:
            call_command('sync_jira_users')

        self.assertIn('Falha ao buscar dados do Jira', str(cm.exception))
        self.assertEqual(Funcionario.objects.count(), 0)

    @patch('apps.dashboards.services.JiraService.get_all_tasks_data')
    def test_sync_handles_empty_jira_response(self, mock_get_all_tasks_data):
        """
        Verifica o comportamento quando a API retorna uma lista vazia.
        """
        mock_get_all_tasks_data.return_value = []

        out = StringIO()
        call_command('sync_jira_users', stdout=out)

        self.assertEqual(Funcionario.objects.count(), 0)
        output = out.getvalue()
        self.assertIn('Nenhum assignee encontrado nas tarefas do Jira.', output)