from django.core.management.base import BaseCommand, CommandError

from apps.dashboards.services import JiraService
from apps.relatorios.models import Funcionario
from apps.usuarios.utils import garantir_usuario_placeholder


class Command(BaseCommand):
    """
    Sincroniza utilizadores do Jira (assignees) com o modelo Funcionario (OLTP).

    Busca tarefas de todos os projetos no Jira, extrai os nomes únicos dos
    assignees e garante que existam registos correspondentes na tabela
    Funcionario. Novos funcionários são criados com o valor/hora padrão.
    """

    help = "Sincroniza os assignees das tarefas do Jira com o modelo Funcionario."

    def handle(self, *args, **options):
        """
        Executa a lógica principal do comando de sincronização.

        Este método conecta-se ao Jira, obtém a lista de assignees das tarefas,
        e utiliza `update_or_create` para adicionar novos funcionários ao banco
        de dados operacional, mantendo os existentes.
        """
        self.stdout.write("Iniciando a sincronização de utilizadores do Jira...")
        projetos = self._buscar_dados_do_jira()
        assignees, total_tasks = self._coletar_assignees(projetos)

        if not assignees:
            self._informar_sem_assignees()
            return

        self._informar_quantidades(assignees, total_tasks)
        resumo = self._processar_assignees(assignees)
        self._exibir_resumo(resumo)

    def _buscar_dados_do_jira(self):
        self.stdout.write("Buscando dados de projetos e tarefas do Jira...")
        projetos = JiraService().get_all_tasks_data()
        if projetos is None:
            raise CommandError(
                "Falha ao buscar dados do Jira. Verifique a conexão e as credenciais."
            )
        return projetos

    def _coletar_assignees(self, projetos):
        assignees = set()
        total_tasks_processadas = 0
        for projeto in projetos:
            tasks = projeto.get("tasks", [])
            for task in tasks:
                assignee_name = task.get("assignee")
                if assignee_name and assignee_name != "Sem responsável":
                    assignees.add(assignee_name.strip())
                total_tasks_processadas += 1
        return assignees, total_tasks_processadas

    def _informar_sem_assignees(self):
        self.stdout.write(
            self.style.WARNING("Nenhum assignee encontrado nas tarefas do Jira.")
        )

    def _informar_quantidades(self, assignees, total_tasks):
        self.stdout.write(
            f"Encontrados {len(assignees)} utilizadores únicos em {total_tasks} tarefas analisadas."
        )

    def _processar_assignees(self, assignees):
        resumo = {
            "criados": 0,
            "atualizados": 0,
            "usuarios_criados": 0,
            "usuarios_existentes": 0,
        }

        for nome_assignee in assignees:
            if self._registrar_funcionario(nome_assignee):
                resumo["criados"] += 1
            else:
                resumo["atualizados"] += 1

            placeholder_status = self._garantir_placeholder(nome_assignee)
            if placeholder_status == "criado":
                resumo["usuarios_criados"] += 1
            elif placeholder_status == "existente":
                resumo["usuarios_existentes"] += 1

        return resumo

    def _registrar_funcionario(self, nome_assignee):
        funcionario, criado = Funcionario.objects.update_or_create(
            nome=nome_assignee,
        )

        if criado:
            self.stdout.write(
                f"  [CRIADO] Funcionário: {funcionario.nome} (ID: {funcionario.id}) com valor/hora padrão."
            )
        return criado

    def _garantir_placeholder(self, nome_assignee):
        try:
            placeholder = garantir_usuario_placeholder(nome_assignee)
        except ValueError:
            self.stdout.write(
                self.style.WARNING(
                    f"  [USUARIO] Nome inválido ao criar placeholder para '{nome_assignee}'."
                )
            )
            return "erro"

        if placeholder.criado:
            self.stdout.write(
                f"  [USUARIO] Criado placeholder '{placeholder.usuario.username}' para {nome_assignee}."
            )
            return "criado"
        return "existente"

    def _exibir_resumo(self, resumo):
        self.stdout.write(self.style.SUCCESS("\nSincronização concluída com sucesso!"))
        self.stdout.write(
            self.style.SUCCESS(f"  - {resumo['criados']} funcionários criados.")
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"  - {resumo['atualizados']} funcionários já existentes."
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                "  - {usuarios_criados} usuários placeholder criados "
                "({usuarios_existentes} já existiam).".format(**resumo)
            )
        )
