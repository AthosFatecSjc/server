import logging
from datetime import date

from django.core.management.base import BaseCommand
from django.db import IntegrityError, transaction

from apps.dashboards.services import JiraService
from apps.relatorios.models import Projeto

logger = logging.getLogger(__name__)

DEFAULT_ORCAMENTO = 20000.00


class Command(BaseCommand):
    """
    Sincroniza os projetos do Jira com o banco OLTP.
    """

    help = "Busca projetos do Jira e os insere ou atualiza no banco OLTP."

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.WARNING(" Iniciando sincronização de projetos do Jira...")
        )

        jira_service = JiraService()
        projetos = jira_service.get_projects()

        if not projetos:
            self.stdout.write(
                self.style.ERROR("Nenhum projeto retornado pela API do Jira.")
            )
            return

        criados, atualizados = 0, 0

        with transaction.atomic():
            for projeto_jira in projetos:
                nome = projeto_jira.get("name", "").strip()
                if not nome:
                    logger.warning("Projeto Jira sem nome ignorado: %s", projeto_jira)
                    continue

                jira_id = projeto_jira.get("id", "").strip()
                if not jira_id:
                    logger.warning(f"Projeto Jira sem id, ignorado: {projeto_jira}")
                    continue

                jira_key = projeto_jira.get("key", "").strip()
                if not jira_key:
                    logger.warning(f"Projeto Jira sem key, ignorado: {projeto_jira}")
                    continue

                try:
                    projeto = Projeto.objects.filter(jira_id=int(jira_id)).first()

                    if not projeto:
                        projeto = Projeto.objects.filter(nome=nome).first()

                    if projeto:
                        # Update existing
                        projeto.jira_id = int(jira_id)
                        projeto.jira_key = jira_key
                        projeto.nome = nome
                        projeto.data_criacao = date.today()
                        projeto.orcamento_previsto = DEFAULT_ORCAMENTO
                        projeto.save()
                        created = False
                    else:
                        # Create new
                        projeto = Projeto.objects.create(
                            jira_id=int(jira_id),
                            jira_key=jira_key,
                            nome=nome,
                            data_criacao=date.today(),
                            orcamento_previsto=DEFAULT_ORCAMENTO,
                        )
                        created = True

                    if created:
                        criados += 1
                    else:
                        atualizados += 1

                except IntegrityError as e:
                    logger.error("Erro ao sincronizar projeto '%s': %s", nome, e)
                    continue

        self.stdout.write(
            self.style.SUCCESS(
                f" Sincronização concluída: {criados} criados, {atualizados} atualizados."
            )
        )
