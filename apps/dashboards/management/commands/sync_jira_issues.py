import logging

from django.core.management.base import BaseCommand
from django.db import IntegrityError, transaction

from apps.dashboards.services import JiraService
from apps.relatorios.models import Funcionario, Issue, Projeto, TipoIssue
from apps.utils.enums.status_integracao_enum import StatusIntegracao

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Sincroniza as issue do Jira baseado nos projetos com o banco OLTP.
    """

    help = "Busca issues do Jira baseado nos projetos e os insere ou atualiza no banco OLTP."

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.WARNING(" Iniciando sincronização de issues do Jira...")
        )

        jira_project_ids = list(
            Projeto.objects.filter(jira_id__isnull=False).values_list(
                "jira_id", flat=True
            )
        )

        if not jira_project_ids:
            self.stdout.write(
                self.style.ERROR("Nenhum projeto Jira encontrado na base OLTP.")
            )
            return

        jira_service = JiraService()

        for jira_project_id in jira_project_ids:

            projeto = Projeto.objects.filter(jira_id=jira_project_id).first()

            tipos_issue_acordados = list(
                TipoIssue.objects.filter(projeto__jira_id=jira_project_id).values_list(
                    "jira_id", flat=True
                )
            )
            logger.error(
                f""" Projeto<id: {projeto.id}, jira_id: {jira_project_id}, tipos_issue: {tipos_issue_acordados})>."""
            )

            jira_issues = jira_service.get_issues(projeto.jira_key)
            logger.error(
                f"""RTX | jira_service.get_issues({jira_project_id}): {len(jira_issues)}"""
            )

            if not jira_issues:
                self.stdout.write(
                    self.style.ERROR(
                        f"Nenhuma issue encontrado para o projeto: {projeto.jira_key} - {projeto.nome} no Jira Rest API."
                    )
                )
                continue

            criados, atualizados, ignorados = 0, 0, 0

            for issue in jira_issues:
                with transaction.atomic():
                    status = self.salva_issue(issue, projeto)

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

    def salva_issue(self, issue_jira: dict, projeto: Projeto) -> StatusIntegracao:
        status = StatusIntegracao.STATUS_IGNORADO

        issue_jira_id = issue_jira.get("id", "").strip()
        if not issue_jira_id:
            self.stdout.write(self.style.ERROR(f"Issue sem id, ignorado."))
            return status

        issue_jira_key = issue_jira.get("key", "").strip()
        if not issue_jira_key:
            self.stdout.write(
                self.style.ERROR(f"Issue sem key, ignorado: {issue_jira_id}.")
            )
            return status

        issue_jira_fields = issue_jira.get("fields", {})
        if not issue_jira_fields:
            self.stdout.write(
                self.style.ERROR(f"Issue sem fields, ignorado: {issue_jira_key},")
            )
            return status

        issue_jira_summary = issue_jira_fields.get("summary", "")
        if not issue_jira_summary:
            self.stdout.write(
                self.style.ERROR(f"Issue sem summary, ignorado: {issue_jira_key}.")
            )
            return status

        issue_jira_tipo_issue_id = (
            issue_jira_fields.get("issuetype", {}).get("id", "").strip()
        )
        if not issue_jira_tipo_issue_id:
            self.stdout.write(
                self.style.ERROR(
                    f"Issue sem tipo de issue id, ignorado: {issue_jira_key}."
                )
            )
            return status

        if not TipoIssue.objects.filter(
            jira_id=int(issue_jira_tipo_issue_id), projeto_id=projeto.id
        ).first():
            issue_jira_tipo_issue_name = (
                issue_jira_fields.get("issuetype", {}).get("name", "").strip()
            )

            self.stdout.write(
                self.style.ERROR(
                    f"Tipo de issue não permitida no projeto: {projeto.nome} ({issue_jira_tipo_issue_name}), ignorado: {issue_jira_key}."
                )
            )
            return status

        issue_jira_assignee = (
            issue_jira_fields.get("assignee", {}).get("displayName", "").strip()
            if issue_jira_fields.get("assignee", 0)
            else None
        )

        try:
            issue = Issue.objects.filter(jira_id=int(issue_jira_id)).first()

            if issue:
                # Update existing
                issue.titulo = issue_jira_summary
                issue.tipo_issue_id = (
                    TipoIssue.objects.filter(jira_id=issue_jira_tipo_issue_id)
                    .first()
                    .id
                )
                issue.tempo_gasto_seconds = (
                    issue_jira_fields.get("timespent", 0)
                    if issue_jira_fields.get("timespent", 0)
                    else None
                )
                issue.tempo_estimado_seconds = (
                    issue_jira_fields.get("timeestimate", 0)
                    if issue_jira_fields.get("timeestimate", 0)
                    else None
                )
                issue.funcionario_id = (
                    Funcionario.objects.filter(nome=issue_jira_assignee).first().id
                    if issue_jira_assignee
                    else None
                )
                issue.atualizado_em = (
                    issue_jira_fields.get("updated", "")
                    if issue_jira_fields.get("updated")
                    else None
                )
                issue.status = (
                    issue_jira_fields.get("status", {}).get("name", "")
                    if issue_jira_fields.get("status")
                    else None
                )
                issue.save()
                status = StatusIntegracao.STATUS_ATUALIZADO
            else:
                # Create new
                issue = Issue.objects.create(
                    jira_id=int(issue_jira_id),
                    jira_key=issue_jira_key,
                    projeto_id=projeto.id,
                    titulo=issue_jira_summary,
                    tipo_issue_id=TipoIssue.objects.filter(
                        jira_id=issue_jira_tipo_issue_id
                    )
                    .first()
                    .id,
                    criado_em=(
                        issue_jira_fields.get("created", "")
                        if issue_jira_fields.get("created")
                        else None
                    ),
                    tempo_gasto_seconds=(
                        issue_jira_fields.get("timespent", 0)
                        if issue_jira_fields.get("timespent", 0)
                        else None
                    ),
                    tempo_estimado_seconds=(
                        issue_jira_fields.get("timeestimate", 0)
                        if issue_jira_fields.get("timeestimate", 0)
                        else None
                    ),
                    funcionario_id=(
                        Funcionario.objects.filter(nome=issue_jira_assignee).first().id
                        if issue_jira_assignee
                        else None
                    ),
                    atualizado_em=(
                        issue_jira_fields.get("updated", "")
                        if issue_jira_fields.get("updated")
                        else None
                    ),
                    status=(
                        issue_jira_fields.get("status", {}).get("name", "")
                        if issue_jira_fields.get("status")
                        else None
                    ),
                )
                status = StatusIntegracao.STATUS_CRIADO

            return status

        except IntegrityError as e:
            self.stdout.write(
                self.style.ERROR(f"Erro ao sincronizar issue: {issue_jira_key}. {e}.")
            )
            return status
