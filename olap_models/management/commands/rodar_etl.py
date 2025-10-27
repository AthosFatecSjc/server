from datetime import date, datetime, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction

# Modelos OLTP
from apps.relatorios.models import TempoGastoEquipe  # usado para granularidade diária
from apps.relatorios.models import Cargo, ControleHorasEquipe, Funcionario, Projeto

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
        Popula FatoRegistroHoras com granularidade diária.
        Agora inclui o projeto por lookup em ControleHorasEquipe.
        """
        self.stdout.write(
            " Populando FatoRegistroHoras (granularidade diária + projeto)..."
        )

        registros_criados = 0
        registros_ignorados = 0

        funcionarios_dim = {f.id: f for f in DimFuncionario.objects.using("olap").all()}
        projetos_dim = {p.id: p for p in DimProjeto.objects.using("olap").all()}
        tempos_dim = {t.data_completa: t for t in DimTempo.objects.using("olap").all()}

        controle_por_func_mes = {
            (c.funcionario_id, c.mes): c.projeto_id
            for c in ControleHorasEquipe.objects.all()
        }

        for registro in TempoGastoEquipe.objects.select_related(
            "funcionario"
        ).iterator():
            try:
                data_completa = registro.mes.replace(day=registro.dia_mes)
            except ValueError:
                registros_ignorados += 1
                continue

            func_dim = funcionarios_dim.get(registro.funcionario_id)
            data_dim = tempos_dim.get(data_completa)

            projeto_id = controle_por_func_mes.get(
                (registro.funcionario_id, registro.mes)
            )
            projeto_dim = projetos_dim.get(projeto_id) if projeto_id else None

            if not (func_dim and data_dim and projeto_dim):
                registros_ignorados += 1
                continue

            custo_dia = float(registro.tempo_gasto) * float(func_dim.valor_hora)

            FatoRegistroHoras.objects.using("olap").update_or_create(
                funcionario=func_dim,
                projeto=projeto_dim,
                data=data_dim,
                defaults={
                    "horas_trabalhadas": registro.tempo_gasto,
                    "custo": custo_dia,
                },
            )
            registros_criados += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"✔ FatoRegistroHoras: {registros_criados} inseridos | {registros_ignorados} ignorados."
            )
        )
