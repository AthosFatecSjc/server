import sentry_sdk
from unittest.mock import patch
from django.core.management.base import BaseCommand, CommandError
from requests.exceptions import ConnectTimeout, HTTPError
from apps.dashboards.services import JiraService

class Command(BaseCommand):
    """
    Comando de gestão para testar a integração do Sentry com o JiraService.
    Permite simular diferentes cenários de falha na comunicação com a API do Jira
    para garantir que os erros são corretamente capturados e reportados ao Sentry.
    """
    help = 'Testa a integração do Sentry ao simular falhas na API do Jira.'

    def add_arguments(self, parser):
        """Adiciona os argumentos que o comando aceita."""
        parser.add_argument(
            '--fail-connection',
            action='store_true',
            help='Simula uma falha de conexão com a API do Jira (ex: timeout).',
        )
        parser.add_argument(
            '--fail-auth',
            action='store_true',
            help='Simula uma falha de autenticação (erro HTTP 401).',
        )
        parser.add_argument(
            '--empty-response',
            action='store_true',
            help='Simula uma resposta bem-sucedida mas com uma lista de projetos vazia.',
        )

    def handle(self, *args, **options):
        """Lógica principal do comando."""
        if not any([options['fail_connection'], options['fail_auth'], options['empty_response']]):
            raise CommandError(
                'Nenhum cenário de falha foi especificado. '
                'Use --fail-connection, --fail-auth, ou --empty-response.'
            )

        self.stdout.write(self.style.WARNING('A iniciar teste de integração com o Sentry...'))

        if options['fail_connection']:
            self.simulate_connection_error()

        if options['fail_auth']:
            self.simulate_auth_error()

        if options['empty_response']:
            self.simulate_empty_response()

        self.stdout.write(self.style.SUCCESS(
            'Teste concluído. Verifique o seu dashboard do Sentry para ver os eventos gerados.'
        ))

    @patch('apps.dashboards.services.requests.get')
    def simulate_connection_error(self, mock_get):
        """Simula um erro de timeout na conexão."""
        self.stdout.write('1. A simular falha de conexão (Timeout)...')
        mock_get.side_effect = ConnectTimeout("Simulação: Timeout ao conectar com a API do Jira.")

        jira_service = JiraService()
        jira_service.get_projects() # Esta chamada deve falhar e enviar para o Sentry
        sentry_sdk.flush() # Força o envio do evento ao Sentry
        self.stdout.write(self.style.SUCCESS('--> Evento de falha de conexão enviado.'))


    @patch('apps.dashboards.services.requests.get')
    def simulate_auth_error(self, mock_get):
        """Simula um erro de autenticação HTTP 401."""
        self.stdout.write('2. A simular falha de autenticação (HTTP 401)...')
        
        # O mock simula a resposta do requests
        mock_response = mock_get.return_value
        mock_response.status_code = 401
        mock_response.reason = "Unauthorized"
        # raise_for_status() irá levantar uma HTTPError com base no status code
        mock_response.raise_for_status.side_effect = HTTPError(
            "Simulação: 401 Client Error: Unauthorized for url: FAKE_URL"
        )

        jira_service = JiraService()
        jira_service.get_projects()
        sentry_sdk.flush()
        self.stdout.write(self.style.SUCCESS('--> Evento de falha de autenticação enviado.'))


    @patch('apps.dashboards.services.requests.get')
    def simulate_empty_response(self, mock_get):
        """Simula uma resposta bem-sucedida, mas com conteúdo vazio."""
        self.stdout.write('3. A simular resposta vazia (sucesso, mas sem dados)...')
        
        mock_response = mock_get.return_value
        mock_response.status_code = 200
        # O método .json() da resposta é configurado para retornar uma lista vazia
        mock_response.json.return_value = []
        # Garante que raise_for_status não levante uma exceção
        mock_response.raise_for_status.return_value = None

        jira_service = JiraService()
        jira_service.get_projects()
        sentry_sdk.flush()
        self.stdout.write(self.style.SUCCESS('--> Mensagem de aviso de resposta vazia enviada.'))