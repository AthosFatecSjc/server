from django.db.models import Sum
from apps.relatorios.models import ControleHorasEquipe, TempoGastoEquipe, TempoControleValores
import datetime

def soma_horas_por_dev_mes(ano):
    queryset = (
        ControleHorasEquipe.objects
        .filter(mes__year=ano)
        .values("funcionario__nome", "mes__month")
        .annotate(total_horas=Sum("horas"))
        .order_by("funcionario__nome", "mes__month")
    )

    resultado = {}
    for item in queryset:
        dev = item["funcionario__nome"]
        mes = item["mes__month"]
        horas = item["total_horas"] or 0
        resultado.setdefault(dev, {})[mes] = float(horas)
    return resultado


def soma_horas_previstas_por_dev_mes(ano, *, source='tempo_controle_valores', field_name=None):
    if source == 'tempo_controle_valores':
        qs = (
            TempoControleValores.objects
            .filter(controle_tempo_equipe__mes__year=ano)
            .values(
                "controle_tempo_equipe__funcionario__nome",
                "controle_tempo_equipe__mes__month"
            )
            .annotate(total_previstas=Sum(field_name or "total_meta"))
            .order_by("controle_tempo_equipe__funcionario__nome", "controle_tempo_equipe__mes__month")
        )
        resultado = {}
        for it in qs:
            dev = it["controle_tempo_equipe__funcionario__nome"]
            mes = it["controle_tempo_equipe__mes__month"]
            val = it["total_previstas"] or 0
            resultado.setdefault(dev, {})[mes] = float(val)
        return resultado

    if source == 'tempo_gasto':
        qs = (
            TempoGastoEquipe.objects
            .filter(mes__year=ano)
            .values("funcionario__nome", "mes__month")
            .annotate(total_previstas=Sum(field_name or "tempo_gasto"))
            .order_by("funcionario__nome", "mes__month")
        )
        resultado = {}
        for it in qs:
            dev = it["funcionario__nome"]
            mes = it["mes__month"]
            val = it["total_previstas"] or 0
            resultado.setdefault(dev, {})[mes] = float(val)
        return resultado

    raise RuntimeError("Fonte inválida para soma_horas_previstas_por_dev_mes. Use 'tempo_controle_valores' ou 'tempo_gasto'.")

def totais_anuais_e_diferenca(ano):
    realizados = soma_horas_por_dev_mes(ano)
    previstos = soma_horas_previstas_por_dev_mes(ano)
    devs = set(list(realizados.keys()) + list(previstos.keys()))
    resumo = {}
    for dev in devs:
        total_real = sum(realizados.get(dev, {}).values()) if realizados.get(dev) else 0.0
        total_prev = sum(previstos.get(dev, {}).values()) if previstos.get(dev) else 0.0
        resumo[dev] = {
            'total_previsto': float(total_prev),
            'total_realizado': float(total_real),
            'diferenca': float(total_prev - total_real),
        }
    return resumo