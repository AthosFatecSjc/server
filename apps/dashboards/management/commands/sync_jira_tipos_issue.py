import logging

from django.core.management.base import BaseCommand
from django.db import IntegrityError, transaction

from apps.dashboards.services import JiraService
from apps.relatorios.models import Projeto, TipoIssue
from apps.utils.enums.status_integracao_enum import StatusIntegracao

logger = logging.getLogger(__name__)

TIPOS_DE_ISSUE_ACORDADOS = ["BUG", "ERRO", "TAREFA"]


class Command(BaseCommand):
    """
    Sincroniza os tipos de issue do Jira baseado nos projetos com o banco OLTP.
    """

    help = "Busca os tipos de issue do Jira baseado nos projetos e os insere ou atualiza no banco OLTP."

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.WARNING(" Iniciando sincronização de tipos de issue do Jira...")
        )

        jira_project_ids = list(Projeto.objects.filter(jira_id__isnull=False).values_list("jira_id", flat=True))

        if not jira_project_ids:
            self.stdout.write(
                self.style.ERROR("Nenhum projeto Jira encontrado na base OLTP.")
            )
            return
        
        jira_service = JiraService()

        for jira_project_id in jira_project_ids:

            tipos_issue = jira_service.get_tipos_issue(jira_project_id)

            projeto = Projeto.objects.filter(jira_id=jira_project_id).first()
            
            if not tipos_issue:
                self.stdout.write(
                    self.style.NOTICE(
                        f" Nenhum tipo de issue encontrado para o projeto { projeto.nome if projeto else '' }"
                    )
                )
                continue
            
            criados, atualizados, ignorados = 0, 0, 0
                        
            for tipo_issue in tipos_issue:
                with transaction.atomic():
                    status = self.salva_tipo_issue(tipo_issue, projeto.id)
                
                    if status == StatusIntegracao.STATUS_CRIADO:
                        criados += 1
                    elif status == StatusIntegracao.STATUS_ATUALIZADO:
                        atualizados += 1
                    else:
                        ignorados += 1
            
            self.stdout.write(
                self.style.SUCCESS(
                    f" Sincronização de tipo de issue para o projeto {projeto.jira_id} - {projeto.nome} concluída: {criados} criados, {atualizados} atualizados, {ignorados} ignorados."
                )
            )


    def salva_tipo_issue(self, tipo_issue_jira: dict, projeto_id: int) -> StatusIntegracao:
        status = StatusIntegracao.STATUS_IGNORADO

        tipo_issue_jira_id = tipo_issue_jira.get("id", "").strip()
        if not tipo_issue_jira_id:
            logger.warning(f"Tipo de issue sem id, ignorado: {tipo_issue_jira}")
            return status

        tipo_issue_jira_name = tipo_issue_jira.get("name", "").strip()
        if not tipo_issue_jira_name:
            logger.warning(f"Tipo de issue sem nome, ignorado: {tipo_issue_jira}")
            return status

        tipo_issue_jira_description = tipo_issue_jira.get("description", "").strip()

        if tipo_issue_jira_name.upper() not in TIPOS_DE_ISSUE_ACORDADOS:
            logger.warning(f"Tipo de issue '{tipo_issue_jira_name}' não está na lista de tipos acordados, ignorado.")
            return status

        try:
            tipo_issue = TipoIssue.objects.filter(jira_id=int(tipo_issue_jira_id)).first()

            if tipo_issue:
                # Update existing
                tipo_issue.nome = tipo_issue_jira_name
                tipo_issue.descricao = tipo_issue_jira_description
                tipo_issue.save()
                status = StatusIntegracao.STATUS_ATUALIZADO
            else:
                # Create new
                tipo_issue = TipoIssue.objects.create(
                    jira_id=int(tipo_issue_jira_id),
                    nome=tipo_issue_jira_name,
                    descricao=tipo_issue_jira_description,
                    projeto_id=projeto_id
                )
                status = StatusIntegracao.STATUS_CRIADO

            return status

        except IntegrityError as e:
            logger.error(f"Erro ao sincronizar tipo de issue - id: {tipo_issue_jira_id}, name: {tipo_issue_jira_name}. {e}")
            return status
