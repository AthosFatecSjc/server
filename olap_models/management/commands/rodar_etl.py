from datetime import datetime, date, timedelta
from django.core.management.base import BaseCommand
from django.db import transaction

# Importe os modelos dos dois bancos de dados
from apps.relatorios.models import Cargo, ControleHorasEquipe, Funcionario, Projeto
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
    o Data Warehouse (banco de dados OLAP) a partir dos dados do banco
    operacional (OLTP).
    """

    help = "Executa o processo de ETL completo para popular o banco de dados OLAP."

    def handle(self, *args, **options):
        """
        Método principal do comando. Orquestra a sequência de execução do ETL.
        """
        self.stdout.write("Iniciando o processo de ETL para o Data Warehouse...")

        self.limpar_tabelas_olap()
        self.popular_dim_tempo()
        self.popular_dimensoes_simples()
        self.popular_dim_funcionario()
        self.popular_fato_registro_horas()

        self.stdout.write(self.style.SUCCESS("Processo de ETL concluído com sucesso!"))

    def limpar_tabelas_olap(self):
        """
        Limpa todos os dados das tabelas do banco de dados OLAP.
        Isso garante que cada execução do ETL seja uma carga nova e consistente,
        evitando dados duplicados ou órfãos. A ordem da exclusão é importante
        devido às restrições de chave estrangeira.
        """
        self.stdout.write("Limpando tabelas OLAP...")
        FatoRegistroHoras.objects.using("olap").all().delete()
        DimFuncionario.objects.using("olap").all().delete()
        DimCargo.objects.using("olap").all().delete()
        DimProjeto.objects.using("olap").all().delete()
        DimTempo.objects.using("olap").all().delete()

    def popular_dim_tempo(self):
        """
        Popula a Dimensão Tempo (DimTempo) com um intervalo de datas pré-definido.
        Esta dimensão não é extraída dos dados de origem, mas gerada
        programaticamente para garantir um calendário completo para análises.
        """
        self.stdout.write('Populando Dimensão Tempo...')
        start_date = date(2020, 1, 1)
        end_date = date(datetime.now().year + 1, 12, 31)
        current_date = start_date
        while current_date <= end_date:
            DimTempo.objects.using("olap").update_or_create(
                id=int(current_date.strftime("%Y%m%d")),
                defaults={
                    'data_completa': current_date,
                    'ano': current_date.year,
                    'trimestre': f'T{(current_date.month - 1) // 3 + 1}',
                    'mes': current_date.month,
                    'mes_nome': current_date.strftime('%B'),
                    'dia': current_date.day,
                    'dia_da_semana': current_date.strftime('%A')
                }
            )
            current_date += timedelta(days=1)

    def popular_dimensoes_simples(self):
        """
        Popula as dimensões mais simples (DimCargo e DimProjeto) que possuem uma
        relação direta 1-para-1 com as tabelas de origem.
        """
        self.stdout.write("Populando Dimensão Cargo...")
        for cargo in Cargo.objects.all():
            DimCargo.objects.using("olap").update_or_create(
                id=cargo.id, defaults={"nome_cargo": cargo.sigla}
            )

        self.stdout.write("Populando Dimensão Projeto...")
        for projeto in Projeto.objects.all():
            DimProjeto.objects.using("olap").update_or_create(
                id=projeto.id,
                defaults={'nome': projeto.nome,
                          'data_criacao': projeto.data_criacao}
            )

    def popular_dim_funcionario(self):
        """
        Popula a Dimensão Funcionário (DimFuncionario), que é mais complexa.
        Este método lê da tabela de origem 'Funcionario' e faz a busca (lookup)
        pelas chaves estrangeiras correspondentes nas dimensões já populadas (ex: DimCargo).
        """
        self.stdout.write("Populando Dimensão Funcionário...")
        for func in Funcionario.objects.all():
            cargo_dim = DimCargo.objects.using("olap").filter(id=func.cargo_id).first()

            gerente_dim = None
            if func.gerente:
                gerente_dim = (
                    DimFuncionario.objects.using("olap")
                    .filter(id=func.gerente.id)
                    .first()
                )

            DimFuncionario.objects.using("olap").update_or_create(
                id=func.id,
                defaults={
                    'nome': func.nome,
                    'time': func.time,
                    'data_contratacao': func.data_criacao,
                    'cargo': cargo_dim,
                    'nome_gerente': gerente_dim,
                    'valor_hora': func.valor_hora
                }
            )

    @transaction.atomic(using="olap")
    def popular_fato_registro_horas(self):
        """
        Popula a tabela Fato principal (FatoRegistroHoras).
        Este é o passo final e mais intensivo, que itera sobre os dados
        transacionais (ControleHorasEquipe), faz o lookup das chaves em todas
        as dimensões relacionadas (Projeto, Funcionário, Tempo) e insere o
        registro de fato no Data Warehouse. A operação é envolvida em uma
        transação atômica para otimizar a performance.
        """
        self.stdout.write("Populando Tabela Fato Registro Horas...")
        for registro in ControleHorasEquipe.objects.all().iterator():
            func_dim = DimFuncionario.objects.using(
                'olap').filter(id=registro.funcionario_id).first()
            projeto_dim = DimProjeto.objects.using(
                'olap').filter(id=registro.projeto_id).first()
            data_dim_id = int(registro.mes.strftime('%Y%m%d'))
            data_dim = DimTempo.objects.using(
                'olap').filter(id=data_dim_id).first()

            if projeto_dim and func_dim and data_dim:
                FatoRegistroHoras.objects.using('olap').create(
                    funcionario=func_dim,
                    projeto=projeto_dim,
                    data=data_dim,
                    horas_trabalhadas=registro.horas,
                    custo=registro.horas * func_dim.valor_hora
                )
