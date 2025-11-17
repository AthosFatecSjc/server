from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import connections, transaction
from django.db.utils import OperationalError, ProgrammingError

# Modelos OLTP
# usado para granularidade diária
from apps.relatorios.models import Cargo, Funcionario, Issue, Projeto, TipoIssue

# Modelos OLAP
from olap_models.models import (
    DimCargo,
    DimFuncionario,
    DimIssue,
    DimModulo,
    DimProjeto,
    DimTempo,
    FatoRegistroHoras,
)

PLACEHOLDER_FUNCIONARIO_ID = 0


class Command(BaseCommand):
    """
    Executa o processo de ETL (Extract, Transform, Load) completo para popular
    o Data Warehouse (OLAP) com base nos dados do sistema operacional (OLTP).
    """

    help = "Executa o processo de ETL completo para popular o banco de dados OLAP."

    @transaction.atomic(using="olap")
    def handle(self, *args, **options):
        """
        Método principal: orquestra a execução do ETL.
        """
        inicio = datetime.now()
        self.stdout.write(
            self.style.WARNING(" Iniciando o processo de ETL para o Data Warehouse...")
        )

        self.garantir_esquema_olap()
        self.limpar_tabelas_olap()
        self.popular_dim_tempo()
        self.popular_dimensoes_simples()
        self.popular_dim_modulo()
        self.popular_dim_funcionario()
        self.popular_dim_issue()
        self.popular_fato_registro_horas()

        fim = datetime.now()
        duracao = (fim - inicio).total_seconds()
        self.stdout.write(
            self.style.SUCCESS(f" ETL concluído com sucesso em {duracao:.2f}s")
        )

    def limpar_tabelas_olap(self):
        """
        Remove todos os dados das tabelas OLAP para evitar duplicação.
        """
        self.stdout.write(" Limpando tabelas OLAP...")
        FatoRegistroHoras.objects.using("olap").all().delete()
        DimIssue.objects.using("olap").all().delete()
        DimModulo.objects.using("olap").all().delete()
        DimFuncionario.objects.using("olap").all().delete()
        DimCargo.objects.using("olap").all().delete()
        DimProjeto.objects.using("olap").all().delete()
        DimTempo.objects.using("olap").all().delete()

    def garantir_esquema_olap(self):
        """
        Garante que o esquema mínimo do banco OLAP exista antes do ETL.
        Cria a tabela DimIssue e a FK em FatoRegistroHoras quando necessário.
        """
        connection = connections["olap"]
        try:
            existing_tables = set(connection.introspection.table_names())
        except (ProgrammingError, OperationalError) as exc:
            raise CommandError(
                f"Não foi possível inspecionar as tabelas do banco OLAP: {exc}"
            ) from exc

        if DimIssue._meta.db_table not in existing_tables:
            self._criar_tabela_dim_issue(connection)

        if DimModulo._meta.db_table not in existing_tables:
            self._criar_tabela_dim_modulo(connection)

        if not self._tabela_possui_coluna(
            connection, FatoRegistroHoras._meta.db_table, "issue_id"
        ):
            self._adicionar_fk_issue_em_fato(connection)

        if not self._tabela_possui_coluna(
            connection, FatoRegistroHoras._meta.db_table, "modulo_id"
        ):
            self._adicionar_fk_modulo_em_fato(connection)

    def _criar_tabela_dim_issue(self, connection):
        self.stdout.write(" Criando tabela DimIssue no banco OLAP...")
        try:
            with connection.schema_editor() as schema_editor:
                schema_editor.create_model(DimIssue)
        except Exception as exc:
            raise CommandError(
                f"Falha ao criar a tabela {DimIssue._meta.db_table}: {exc}"
            ) from exc

    def _adicionar_fk_issue_em_fato(self, connection):
        self.stdout.write(
            " Adicionando coluna de relacionamento Issue em FatoRegistroHoras..."
        )
        issue_field = FatoRegistroHoras._meta.get_field("issue")
        try:
            with connection.schema_editor() as schema_editor:
                schema_editor.add_field(FatoRegistroHoras, issue_field)
        except Exception as exc:
            raise CommandError(
                f"Falha ao adicionar a coluna issue_id em {FatoRegistroHoras._meta.db_table}: {exc}"
            ) from exc

    def _criar_tabela_dim_modulo(self, connection):
        self.stdout.write(" Criando tabela DimModulo no banco OLAP...")
        try:
            with connection.schema_editor() as schema_editor:
                schema_editor.create_model(DimModulo)
        except Exception as exc:
            raise CommandError(
                f"Falha ao criar a tabela {DimModulo._meta.db_table}: {exc}"
            ) from exc

    def _adicionar_fk_modulo_em_fato(self, connection):
        self.stdout.write(
            " Adicionando coluna de relacionamento Módulo em FatoRegistroHoras..."
        )
        modulo_field = FatoRegistroHoras._meta.get_field("modulo")
        try:
            with connection.schema_editor() as schema_editor:
                schema_editor.add_field(FatoRegistroHoras, modulo_field)
        except Exception as exc:
            raise CommandError(
                f"Falha ao adicionar a coluna modulo_id em {FatoRegistroHoras._meta.db_table}: {exc}"
            ) from exc

    def _tabela_possui_coluna(self, connection, table_name, column_name):
        try:
            with connection.cursor() as cursor:
                description = connection.introspection.get_table_description(
                    cursor, table_name
                )
        except (ProgrammingError, OperationalError):
            return False

        return any(column.name == column_name for column in description)

    def popular_dim_tempo(self):
        """
        Popula a Dimensão Tempo (DimTempo) com granularidade DIÁRIA.
        Usa data_completa como chave natural (não força id).
        """
        self.stdout.write(" Populando Dimensão Tempo...")
        start_date = date(2020, 1, 1)
        end_date = date(datetime.now().year + 1, 12, 31)

        meses_pt = [
            "Janeiro",
            "Fevereiro",
            "Março",
            "Abril",
            "Maio",
            "Junho",
            "Julho",
            "Agosto",
            "Setembro",
            "Outubro",
            "Novembro",
            "Dezembro",
        ]

        dias_semana_pt = [
            "Segunda",
            "Terça",
            "Quarta",
            "Quinta",
            "Sexta",
            "Sábado",
            "Domingo",
        ]

        count = 0
        current_date = start_date
        while current_date <= end_date:
            DimTempo.objects.using("olap").update_or_create(
                data_completa=current_date,
                defaults={
                    "ano": current_date.year,
                    "trimestre": f"T{(current_date.month - 1) // 3 + 1}",
                    "mes": current_date.month,
                    "mes_nome": meses_pt[current_date.month - 1],
                    "dia": current_date.day,
                    "hora": 0,
                    "dia_da_semana": dias_semana_pt[current_date.weekday()],
                },
            )
            count += 1
            current_date += timedelta(days=1)

        self.stdout.write(
            self.style.SUCCESS(f" DimTempo populada com {count} registros.")
        )

    def popular_dimensoes_simples(self):
        """
        Popula as dimensões Cargo e Projeto.
        """
        self.stdout.write(" Populando Dimensões Cargo e Projeto...")

        for cargo in Cargo.objects.all():
            DimCargo.objects.using("olap").update_or_create(
                id=cargo.id,
                defaults={"nome_cargo": cargo.sigla},
            )

        for projeto in Projeto.objects.all():
            DimProjeto.objects.using("olap").update_or_create(
                id=projeto.id,
                defaults={
                    "nome": projeto.nome,
                    "data_criacao": projeto.data_criacao,
                },
            )

        self.stdout.write(self.style.SUCCESS(" DimCargo e DimProjeto populadas."))

    def popular_dim_modulo(self):
        """Popula DimModulo a partir dos tipos de issue do OLTP."""

        self.stdout.write(" Populando Dimensão Módulo/Epic...")

        criados = 0
        atualizados = 0

        DimModulo.objects.using("olap").update_or_create(
            source_tipo_issue_id=None,
            defaults={"nome": "Não mapeado", "jira_id": None, "projeto": None},
        )

        for tipo in (
            TipoIssue.objects.select_related("projeto")
            .order_by("projeto_id", "nome")
            .all()
        ):
            projeto_dim = (
                DimProjeto.objects.using("olap").filter(id=tipo.projeto_id).first()
            )
            _, created = DimModulo.objects.using("olap").update_or_create(
                source_tipo_issue_id=tipo.id,
                defaults={
                    "nome": tipo.nome,
                    "jira_id": tipo.jira_id,
                    "projeto": projeto_dim,
                },
            )
            if created:
                criados += 1
            else:
                atualizados += 1

        self.stdout.write(
            self.style.SUCCESS(
                f" DimModulo populada ({criados} criados, {atualizados} atualizados)."
            )
        )

    def popular_dim_funcionario(self):
        """
        Popula DimFuncionario, corrigindo campos texto e relacionamentos.
        """
        self.stdout.write(" Populando Dimensão Funcionário...")

        count = 0
        for func in Funcionario.objects.select_related("cargo", "gerente").all():
            cargo_dim = DimCargo.objects.using("olap").filter(id=func.cargo_id).first()

            DimFuncionario.objects.using("olap").update_or_create(
                id=func.id,
                defaults={
                    "nome": func.nome,
                    "time": func.time,
                    "data_contratacao": func.data_criacao,
                    "cargo": cargo_dim.nome_cargo if cargo_dim else "Não definido",
                    "nome_gerente": func.gerente.nome if func.gerente else "",
                    "valor_hora": func.valor_hora,
                },
            )
            count += 1

        # garante uma linha curinga para issues sem responsável
        DimFuncionario.objects.using("olap").update_or_create(
            id=PLACEHOLDER_FUNCIONARIO_ID,
            defaults={
                "nome": "Não atribuído",
                "time": "N/A",
                "data_contratacao": date(1900, 1, 1),
                "cargo": "Não definido",
                "nome_gerente": "",
                "valor_hora": 0,
            },
        )

        self.stdout.write(
            self.style.SUCCESS(f" DimFuncionario populada com {count} registros.")
        )

    def popular_dim_issue(self):
        """
        Popula DimIssue a partir do modelo Issue no banco OLTP.
        Armazena a chave da issue, tipo, título e data de criação.
        """
        self.stdout.write(" Populando Dimensão Issue...")

        count = 0
        for issue in Issue.objects.select_related("tipo_issue").all():
            # prefira a jira_key (ex: PROJ-123) como identificador legível
            issue_key = issue.jira_key if issue.jira_key else str(issue.jira_id)
            created_date = issue.criado_em.date() if issue.criado_em else None
            issue_type = issue.tipo_issue.nome if issue.tipo_issue else None
            modulo_dim = None
            if issue.tipo_issue_id:
                modulo_dim = (
                    DimModulo.objects.using("olap")
                    .filter(source_tipo_issue_id=issue.tipo_issue_id)
                    .first()
                )
            if not modulo_dim:
                modulo_dim = (
                    DimModulo.objects.using("olap")
                    .filter(source_tipo_issue_id=None)
                    .first()
                )

            DimIssue.objects.using("olap").update_or_create(
                issue_id=issue_key,
                defaults={
                    "issue_type": issue_type or (modulo_dim.nome if modulo_dim else ""),
                    "issue_title": issue.titulo,
                    "created_date": created_date,
                    "modulo": modulo_dim,
                },
            )
            count += 1

        self.stdout.write(
            self.style.SUCCESS(f" DimIssue populada com {count} registros.")
        )

    def popular_fato_registro_horas(self):
        """
        Popula FatoRegistroHoras com granularidade diária a partir das Issues.
        Usa a data de criação da issue como chave temporal.
        """
        self.stdout.write(
            " Populando FatoRegistroHoras (granularidade diária a partir de issues)..."
        )

        registros_criados = 0
        registros_ignorados = 0
        duas_casas = Decimal("0.01")

        funcionarios_dim = {f.id: f for f in DimFuncionario.objects.using("olap").all()}
        projetos_dim = {p.id: p for p in DimProjeto.objects.using("olap").all()}
        tempos_dim = {t.data_completa: t for t in DimTempo.objects.using("olap").all()}
        issues_dim = {
            issue.issue_id: issue for issue in DimIssue.objects.using("olap").all()
        }
        modulos_dim = {
            modulo.source_tipo_issue_id: modulo
            for modulo in DimModulo.objects.using("olap").all()
        }
        modulo_default = modulos_dim.get(None)

        acumulado = {}

        for issue in (
            Issue.objects.select_related("funcionario", "projeto")
            .exclude(criado_em__isnull=True)
            .iterator()
        ):
            if not issue.projeto_id:
                registros_ignorados += 1
                continue

            data_completa = issue.criado_em.date()
            funcionario_id = issue.funcionario_id or PLACEHOLDER_FUNCIONARIO_ID
            func_dim = funcionarios_dim.get(funcionario_id)
            projeto_dim = projetos_dim.get(issue.projeto_id)
            data_dim = tempos_dim.get(data_completa)
            modulo_dim = None
            if issue.tipo_issue_id:
                modulo_dim = modulos_dim.get(issue.tipo_issue_id)
            modulo_dim = modulo_dim or modulo_default
            if not (func_dim and projeto_dim and data_dim):
                registros_ignorados += 1
                continue

            horas_issue = Decimal(issue.tempo_gasto_seconds or 0) / Decimal("3600")
            modulo_key = modulo_dim.id if modulo_dim else None
            key = (funcionario_id, issue.projeto_id, data_completa, modulo_key)

            entry = acumulado.setdefault(
                key,
                {
                    "func": func_dim,
                    "proj": projeto_dim,
                    "data": data_dim,
                    "horas": Decimal("0"),
                    "custo": Decimal("0"),
                    "modulo": modulo_dim,
                    "issue": None,
                },
            )

            entry["horas"] += horas_issue
            entry["custo"] += horas_issue * func_dim.valor_hora
            if not entry["issue"]:
                entry["issue"] = issues_dim.get(issue.jira_key)

        for entry in acumulado.values():
            FatoRegistroHoras.objects.using("olap").update_or_create(
                funcionario=entry["func"],
                projeto=entry["proj"],
                data=entry["data"],
                defaults={
                    "horas_trabalhadas": entry["horas"].quantize(
                        duas_casas, rounding=ROUND_HALF_UP
                    ),
                    "custo": entry["custo"].quantize(
                        duas_casas, rounding=ROUND_HALF_UP
                    ),
                    "modulo": entry["modulo"],
                    "issue": entry["issue"],
                },
            )
            registros_criados += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"✔ FatoRegistroHoras: {registros_criados} inseridos | {registros_ignorados} ignorados."
            )
        )
