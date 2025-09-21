from django.db.models import Sum
from apps.relatorios.models import TempoGastoEquipe, Funcionario

def calcular_spends_por_dev(mes, ano):
    funcionarios = Funcionario.objects.all()
    resultados = []

    total_real = 0.0
    total_meta = 0.0
    soma_diaria_total = {d: 0.0 for d in range(1, 32)}

    for func in funcionarios:
        registros = TempoGastoEquipe.objects.filter(
            funcionario=func,
            mes__month=mes,
            mes__year=ano
        ).values('dia_mes').annotate(total_horas=Sum('tempo_gasto'))

        dias_por_func = {}
        for r in registros:
            dia = r['dia_mes']
            horas_dia = float(r['total_horas'])
            dias_por_func[dia] = round(horas_dia, 1)
            soma_diaria_total[dia] += horas_dia

        for d in range(1, 32):
            if d not in dias_por_func:
                dias_por_func[d] = 0.0

        horas_real = sum(dias_por_func.values())
        meta = 154.0
        percentual = (horas_real / meta * 100) if meta > 0 else 0

        resultados.append({
            "funcionario": func.nome,
            "dias": dias_por_func,
            "real": round(horas_real, 1),
            "meta": meta,
            "percentual": round(percentual, 1)
        })

        total_real += horas_real
        total_meta += meta

    percentual_total = (total_real / total_meta * 100) if total_meta > 0 else 0
    
    soma_diaria_total_arredondada = {dia: round(valor, 1) for dia, valor in soma_diaria_total.items()}
    
    resultados.append({
        "funcionario": "REALIZADO",
        "dias": soma_diaria_total_arredondada,
        "real": round(total_real, 1),
        "meta": total_meta,
        "percentual": round(percentual_total, 1)
    })

    return resultados