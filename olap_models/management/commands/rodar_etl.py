from datetime import date, datetime, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

# Modelos OLTP
from apps.relatorios.models import Cargo, Funcionario, Issue, Projeto

# Modelos OLAP
from olap_models.models import (
    DimCargo,
    DimFuncionario,
    DimProjeto,
    DimTempo,
    FatoRegistroHoras,
)


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

        self.limpar_tabelas_olap()
        self.popular_dim_tempo()
        self.popular_dimensoes_simples()
        self.popular_dim_funcionario()
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
        DimFuncionario.objects.using("olap").all().delete()
        DimCargo.objects.using("olap").all().delete()
        DimProjeto.objects.using("olap").all().delete()
        DimTempo.objects.using("olap").all().delete()

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

        self.stdout.write(
            self.style.SUCCESS(f" DimFuncionario populada com {count} registros.")
        )

    def popular_fato_registro_horas(self):
        """
        Popula FatoRegistroHoras a partir das issues sincronizadas com o Jira.
        Cada issue contribui com suas horas trabalhadas no dia do último update
        (fallback para data de criação), agregando por funcionário + projeto + dia.
        """
        self.stdout.write(
            " Populando FatoRegistroHoras (baseado em issues sincronizadas)..."
        )

        registros_criados = 0
        registros_ignorados = 0

        funcionarios_dim = {f.id: f for f in DimFuncionario.objects.using("olap").all()}
        projetos_dim = {p.id: p for p in DimProjeto.objects.using("olap").all()}
        tempos_dim = {t.data_completa: t for t in DimTempo.objects.using("olap").all()}

        agregados: dict[tuple[int, int, int], dict[str, object]] = {}

        for issue in Issue.objects.select_related("funcionario", "projeto").iterator():
            if not issue.funcionario_id:
                registros_ignorados += 1
                continue

            data_base = issue.atualizado_em or issue.criado_em
            if not data_base:
                registros_ignorados += 1
                continue

            data_completa = data_base.date()
            horas_decimais = Decimal(issue.tempo_gasto_seconds or 0) / Decimal("3600")
            if horas_decimais <= 0:
                registros_ignorados += 1
                continue

            func_dim = funcionarios_dim.get(issue.funcionario_id)
            projeto_dim = projetos_dim.get(issue.projeto_id)
            data_dim = tempos_dim.get(data_completa)

            if not (func_dim and projeto_dim and data_dim):
                registros_ignorados += 1
                continue

            chave = (func_dim.id, projeto_dim.id, data_dim.id)
            agregado = agregados.setdefault(
                chave,
                {
                    "funcionario": func_dim,
                    "projeto": projeto_dim,
                    "data": data_dim,
                    "horas": Decimal("0"),
                    "custo": Decimal("0"),
                },
            )
            agregado["horas"] += horas_decimais
            agregado["custo"] += horas_decimais * func_dim.valor_hora

        for agregado in agregados.values():
            FatoRegistroHoras.objects.using("olap").update_or_create(
                funcionario=agregado["funcionario"],
                projeto=agregado["projeto"],
                data=agregado["data"],
                defaults={
                    "horas_trabalhadas": agregado["horas"],
                    "custo": agregado["custo"],
                },
            )
            registros_criados += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"✔ FatoRegistroHoras: {registros_criados} inseridos | {registros_ignorados} ignorados."
            )
        )
