#!/usr/bin/env python
"""
Script para popular dados mockados no banco OLAP
Execute: python popular_dados_mock.py
"""
import os
from datetime import date, datetime
from decimal import Decimal

import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from olap_models.models import (
    DimFuncionario,
    DimProjeto,
    DimTempo,
    FatoRegistroHoras,
)


def limpar_dados():
    """Remove dados existentes"""
    print("🧹 Limpando dados existentes...")
    FatoRegistroHoras.objects.using('olap').all().delete()
    DimTempo.objects.using('olap').all().delete()
    DimFuncionario.objects.using('olap').all().delete()
    DimProjeto.objects.using('olap').all().delete()
    print("✅ Dados limpos!")


def criar_projeto():
    """Cria projeto mockado"""
    print("\n📁 Criando projeto...")
    projeto = DimProjeto.objects.using('olap').create(
        nome="Sistema de Gestão",
        data_criacao=date(2025, 1, 15)
    )
    print(f"✅ Projeto criado: {projeto.nome} (ID: {projeto.id})")
    return projeto


def criar_funcionarios():
    """Cria desenvolvedores mockados"""
    print("\n👥 Criando desenvolvedores...")

    desenvolvedores = [
        {"nome": "Ana Silva", "valor_hora": Decimal("85.00"), "time": "Backend"},
        {"nome": "Carlos Santos", "valor_hora": Decimal("95.00"), "time": "Frontend"},
        {"nome": "Maria Oliveira", "valor_hora": Decimal("75.00"), "time": "Backend"},
        {"nome": "João Pereira", "valor_hora": Decimal("90.00"), "time": "Full Stack"},
        {"nome": "Juliana Costa", "valor_hora": Decimal("80.00"), "time": "Frontend"},
    ]

    funcionarios_criados = []
    for dev in desenvolvedores:
        func = DimFuncionario.objects.using('olap').create(
            nome=dev["nome"],
            valor_hora=dev["valor_hora"],
            time=dev["time"],
            cargo="dev",
            data_contratacao=date(2024, 6, 1)
        )
        funcionarios_criados.append(func)
        print(f"  ✅ {func.nome} - R$ {func.valor_hora}/h")

    return funcionarios_criados


def criar_datas():
    """Cria registros de tempo para outubro/2025"""
    print("\n📅 Criando datas...")

    datas_criadas = []
    dias_semana = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]

    # Criar datas de 1 a 25 de outubro de 2025
    for dia in range(1, 26):
        data_completa = date(2025, 10, dia)
        dia_semana_idx = data_completa.weekday()

        trimestre = "Q4"

        dim_tempo = DimTempo.objects.using('olap').create(
            hora=9,
            dia=dia,
            mes=10,
            ano=2025,
            data_completa=data_completa,
            trimestre=trimestre,
            dia_da_semana=dias_semana[dia_semana_idx]
        )
        datas_criadas.append(dim_tempo)

    print(f"✅ {len(datas_criadas)} datas criadas (01/10 a 25/10/2025)")
    return datas_criadas


def criar_registros_horas(projeto, funcionarios, datas):
    """Cria registros de horas trabalhadas"""
    print("\n⏰ Criando registros de horas...")

    total_registros = 0

    # Horas trabalhadas por desenvolvedor (variando)
    horas_por_dev = {
        0: 120,  # Ana - 120h
        1: 95,   # Carlos - 95h
        2: 110,  # Maria - 110h
        3: 85,   # João - 85h
        4: 100,  # Juliana - 100h
    }

    for idx, funcionario in enumerate(funcionarios):
        horas_totais = horas_por_dev[idx]
        horas_por_dia = horas_totais / len(datas)

        for data in datas:
            # Variar um pouco as horas por dia (± 20%)
            import random
            variacao = random.uniform(0.8, 1.2)
            horas = round(horas_por_dia * variacao, 2)

            custo = Decimal(str(horas)) * funcionario.valor_hora

            FatoRegistroHoras.objects.using('olap').create(
                funcionario=funcionario,
                projeto=projeto,
                data=data,
                horas_trabalhadas=Decimal(str(horas)),
                custo=Decimal(str(custo))
            )
            total_registros += 1

    print(f"✅ {total_registros} registros de horas criados!")

    # Mostrar resumo
    print("\n📊 RESUMO DOS CUSTOS POR DESENVOLVEDOR:")
    print("-" * 60)
    for funcionario in funcionarios:
        total = FatoRegistroHoras.objects.using('olap').filter(
            funcionario=funcionario,
            projeto=projeto
        ).aggregate(
            total_horas=django.db.models.Sum('horas_trabalhadas'),
            total_custo=django.db.models.Sum('custo')
        )
        print(f"{funcionario.nome:20} | {total['total_horas']:6}h | R$ {total['total_custo']:8.2f}")
    print("-" * 60)


def main():
    """Função principal"""
    print("=" * 60)
    print("🚀 POPULANDO BANCO OLAP COM DADOS MOCKADOS")
    print("=" * 60)

    try:
        limpar_dados()
        projeto = criar_projeto()
        funcionarios = criar_funcionarios()
        datas = criar_datas()
        criar_registros_horas(projeto, funcionarios, datas)

        print("\n" + "=" * 60)
        print("✅ DADOS MOCKADOS CRIADOS COM SUCESSO!")
        print("=" * 60)
        print(f"\n💡 Acesse: http://127.0.0.1:8000/dashboards/projeto/")
        print(f"   Projeto ID: {projeto.id}")

    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
