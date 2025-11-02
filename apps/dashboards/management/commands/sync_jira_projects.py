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

                try:
                    _projeto, created = Projeto.objects.update_or_create(
                        nome=nome,
                        defaults={
                            "data_criacao": date.today(),
                            "orcamento_previsto": DEFAULT_ORCAMENTO,
                        },
                    )

                    if created:
                        criados += 1
                    else:
                        atualizados += 1

                except IntegrityError as e:
                    logger.error("Erro ao sincronizar %s: %s", projeto_id, e)
                    continue

        self.stdout.write(
            self.style.SUCCESS(
                f" Sincronização concluída: {criados} criados, {atualizados} atualizados."
            )
        )
