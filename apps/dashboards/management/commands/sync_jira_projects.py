import logging
from datetime import date

from django.core.management.base import BaseCommand
from django.db import IntegrityError, transaction

from apps.dashboards.services import JiraService
from apps.relatorios.models import Projeto
from apps.utils.enums.status_integracao_enum import StatusIntegracao

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

        criados, atualizados, ignorados = 0, 0, 0

        with transaction.atomic():
            for projeto in projetos:
                status = self.salva_projeto(projeto)

                if status == StatusIntegracao.STATUS_CRIADO:
                    criados += 1
                elif status == StatusIntegracao.STATUS_ATUALIZADO:
                    atualizados += 1
                else:
                    ignorados += 1

        self.stdout.write(
            self.style.SUCCESS(
                f" Sincronização concluída: {criados} criados, {atualizados} atualizados, {ignorados} ignorados."
            )
        )

    def salva_projeto(self, projeto):
        status = StatusIntegracao.STATUS_IGNORADO
        nome = projeto.get("name", "").strip()

        if not nome:
            logger.warning("Projeto Jira sem nome ignorado: %s", projeto)
            return status

        jira_id = self._clean_str(projeto.get("id"))
        if not jira_id:
            logger.warning("Projeto Jira sem id, ignorado: %s", projeto)

        jira_key = self._clean_str(projeto.get("key"))
        if not jira_key:
            logger.warning("Projeto Jira sem key, ignorado: %s", projeto)

        try:
            projeto = (
                Projeto.objects.filter(jira_id=int(jira_id)).first()
                if jira_id
                else None
            )

            if not projeto:
                projeto = Projeto.objects.filter(nome=nome).first()

            if projeto:
                # Update existing
                if jira_id:
                    projeto.jira_id = int(jira_id)
                if jira_key:
                    projeto.jira_key = jira_key
                projeto.nome = nome
                projeto.data_criacao = date.today()
                projeto.orcamento_previsto = DEFAULT_ORCAMENTO
                projeto.save()
                status = StatusIntegracao.STATUS_ATUALIZADO
            else:
                # Create new
                projeto = Projeto.objects.create(
                    jira_id=int(jira_id) if jira_id else None,
                    jira_key=jira_key or None,
                    nome=nome,
                    data_criacao=date.today(),
                    orcamento_previsto=DEFAULT_ORCAMENTO,
                )
                status = StatusIntegracao.STATUS_CRIADO

            return status

        except IntegrityError as e:
            logger.error("Erro ao sincronizar projeto '%s': %s", nome, e)
            return status

    @staticmethod
    def _clean_str(value):
        if value is None:
            return ""
        return str(value).strip()
