from django.core.management.base import BaseCommand, CommandError
from apps.dashboards.services import JiraService
from apps.relatorios.models import Funcionario


class Command(BaseCommand):
    """
    Sincroniza utilizadores do Jira (assignees) com o modelo Funcionario (OLTP).

    Busca tarefas de todos os projetos no Jira, extrai os nomes únicos dos
    assignees e garante que existam registos correspondentes na tabela
    Funcionario. Novos funcionários são criados com o valor/hora padrão.
    """

    help = 'Sincroniza os assignees das tarefas do Jira com o modelo Funcionario.'

    def handle(self, *args, **options):
        """
        Executa a lógica principal do comando de sincronização.

        Este método conecta-se ao Jira, obtém a lista de assignees das tarefas,
        e utiliza `update_or_create` para adicionar novos funcionários ao banco
        de dados operacional, mantendo os existentes.
        """
        self.stdout.write('Iniciando a sincronização de utilizadores do Jira...')

        jira_service = JiraService()

        self.stdout.write('Buscando dados de projetos e tarefas do Jira...')
        projetos_com_tasks = jira_service.get_all_tasks_data()

        if projetos_com_tasks is None:
            raise CommandError(
                'Falha ao buscar dados do Jira. Verifique a conexão e as credenciais.'
            )

        assignees = set()
        total_tasks_processadas = 0
        for projeto in projetos_com_tasks:
            for task in projeto.get('tasks', []):
                assignee_name = task.get('assignee')
                if assignee_name and assignee_name != 'Sem responsável':
                    assignees.add(assignee_name.strip())
                total_tasks_processadas += 1

        if not assignees:
            self.stdout.write(self.style.WARNING(
                'Nenhum assignee encontrado nas tarefas do Jira.'))
            return

        self.stdout.write(
            'Encontrados {} utilizadores únicos em {} tarefas analisadas.'.format(
                len(assignees), total_tasks_processadas
            ))

        criados = 0
        atualizados = 0
        for nome_assignee in assignees:
            funcionario, created = Funcionario.objects.update_or_create(
                nome=nome_assignee,
            )

            if created:
                criados += 1
                self.stdout.write(
                    '  [CRIADO] Funcionário: {} (ID: {}) com valor/hora padrão.'.format(
                        funcionario.nome, funcionario.id
                    ))
            else:
                atualizados += 1

        self.stdout.write(self.style.SUCCESS(
            '\nSincronização concluída com sucesso!'
        ))
        self.stdout.write(self.style.SUCCESS(
            '  - {} funcionários criados.'.format(criados)
        ))
        self.stdout.write(self.style.SUCCESS(
            '  - {} funcionários já existentes.'.format(atualizados)
        ))