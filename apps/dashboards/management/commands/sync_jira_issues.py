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
                " Projeto<id: %s, jira_id: %s, tipos_issue: %s)>.",
                projeto.id,
                jira_project_id,
                tipos_issue_acordados,
            )

            jira_issues = jira_service.get_issues(projeto.jira_key)
            logger.error(
                "RTX | jira_service.get_issues(%s): %s",
                jira_project_id,
                len(jira_issues),
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

        issue_data, error_message = self._extract_issue_data(issue_jira, projeto)
        if error_message:
            self.stdout.write(self.style.ERROR(error_message))
            return status

        issue_jira_fields = issue_data["fields"]
        issue_jira_id = int(issue_data["id"])
        issue_jira_key = issue_data["key"]
        issue_jira_summary = issue_data["summary"]
        tipo_issue = issue_data["tipo_issue"]
        issue_jira_assignee = self._extract_assignee_name(issue_jira_fields)
        funcionario_id = self._get_funcionario_id(issue_jira_assignee)

        issue_payload = self._build_issue_payload(
            issue_jira_summary,
            tipo_issue.id,
            issue_jira_fields,
            funcionario_id,
        )

        try:
            issue = Issue.objects.filter(jira_id=issue_jira_id).first()

            if issue:
                self._update_issue(issue, issue_payload)
                status = StatusIntegracao.STATUS_ATUALIZADO
            else:
                self._create_issue(
                    projeto,
                    issue_jira_id,
                    issue_jira_key,
                    self._optional_field(issue_jira_fields, "created"),
                    issue_payload,
                )
                status = StatusIntegracao.STATUS_CRIADO

        except IntegrityError as e:
            self.stdout.write(
                self.style.ERROR(f"Erro ao sincronizar issue: {issue_jira_key}. {e}.")
            )

        return status

    def _extract_issue_data(self, issue_jira: dict, projeto: Projeto):
        issue_jira_id = issue_jira.get("id", "").strip()
        issue_jira_key = issue_jira.get("key", "").strip()
        issue_jira_fields = issue_jira.get("fields", {})
        issue_jira_summary = issue_jira_fields.get("summary", "")
        issue_jira_tipo_issue_id = (
            issue_jira_fields.get("issuetype", {}).get("id", "").strip()
        )

        validations = (
            (not issue_jira_id, "Issue sem id, ignorado."),
            (
                not issue_jira_key,
                f"Issue sem key, ignorado: {issue_jira_id}.",
            ),
            (
                not issue_jira_fields,
                f"Issue sem fields, ignorado: {issue_jira_key},",
            ),
            (
                not issue_jira_summary,
                f"Issue sem summary, ignorado: {issue_jira_key}.",
            ),
            (
                not issue_jira_tipo_issue_id,
                f"Issue sem tipo de issue id, ignorado: {issue_jira_key}.",
            ),
        )

        for condition, message in validations:
            if condition:
                return None, message

        tipo_issue = TipoIssue.objects.filter(
            jira_id=int(issue_jira_tipo_issue_id), projeto_id=projeto.id
        ).first()
        if not tipo_issue:
            issue_jira_tipo_issue_name = (
                issue_jira_fields.get("issuetype", {}).get("name", "").strip()
            )
            return (
                None,
                f"Tipo de issue não permitida no projeto: {projeto.nome} ({issue_jira_tipo_issue_name}), ignorado: {issue_jira_key}.",
            )

        return (
            {
                "id": issue_jira_id,
                "key": issue_jira_key,
                "fields": issue_jira_fields,
                "summary": issue_jira_summary,
                "tipo_issue": tipo_issue,
            },
            None,
        )

    def _build_issue_payload(
        self,
        summary: str,
        tipo_issue_id: int,
        issue_fields: dict,
        funcionario_id: int | None,
    ) -> dict:
        return {
            "titulo": summary,
            "tipo_issue_id": tipo_issue_id,
            "tempo_gasto_seconds": self._optional_field(issue_fields, "timespent"),
            "tempo_estimado_seconds": self._optional_field(
                issue_fields, "timeestimate"
            ),
            "funcionario_id": funcionario_id,
            "atualizado_em": self._optional_field(issue_fields, "updated"),
            "status": self._extract_status(issue_fields),
        }

    @staticmethod
    def _update_issue(issue: Issue, data: dict) -> None:
        for attr, value in data.items():
            setattr(issue, attr, value)
        issue.save()

    @staticmethod
    def _create_issue(
        projeto: Projeto,
        issue_jira_id: int,
        issue_jira_key: str,
        created_at,
        data: dict,
    ) -> None:
        Issue.objects.create(
            jira_id=int(issue_jira_id),
            jira_key=issue_jira_key,
            projeto_id=projeto.id,
            criado_em=created_at,
            **data,
        )

    @staticmethod
    def _optional_field(issue_fields: dict, key: str):
        value = issue_fields.get(key)
        return value if value else None

    @staticmethod
    def _extract_status(issue_fields: dict) -> str:
        status_info = issue_fields.get("status") or {}
        return status_info.get("name", "").strip()

    @staticmethod
    def _extract_assignee_name(issue_fields: dict) -> str:
        assignee = issue_fields.get("assignee") or {}
        return assignee.get("displayName", "").strip()

    @staticmethod
    def _get_funcionario_id(nome: str | None):
        if not nome:
            return None
        funcionario = Funcionario.objects.filter(nome=nome).first()
        return funcionario.id if funcionario else None
