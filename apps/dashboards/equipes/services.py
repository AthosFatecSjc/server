from datetime import datetime, timedelta

from django.db.models import Sum
from django.utils import timezone

from olap_models.models import DimFuncionario, DimProjeto, FatoRegistroHoras


class DashboardEquipesService:

    @staticmethod
    def get_dev_color(index):
        """Retorna cores consistentes para os desenvolvedores"""
        colors = [
            "#0057B8",
            "#f59e0b",
            "#10b981",
            "#8b5cf6",
            "#ef4444",
            "#8b5cf6",
            "#06b6d4",
            "#84cc16",
        ]
        return colors[index % len(colors)]

    @staticmethod
    def get_desenvolvedores_dropdown(desenvolvedores_ids=None):
        """Retorna lista de desenvolvedores para o dropdown"""
        desenvolvedores_unicos = DimFuncionario.objects.all()

        return [
            {
                "name": dev.nome,
                "color": DashboardEquipesService.get_dev_color(i),
                "selected": (
                    dev.nome in desenvolvedores_ids if desenvolvedores_ids else True
                ),
            }
            for i, dev in enumerate(desenvolvedores_unicos)
        ]

    @staticmethod
    def get_projetos():
        """Retorna todos os projetos"""
        return DimProjeto.objects.all()

    @staticmethod
    def get_datas_padrao():
        """Retorna datas padrão para o filtro (últimos 30 dias)"""
        data_fim_dt = timezone.now()
        data_inicio_dt = data_fim_dt - timedelta(days=30)
        return data_inicio_dt, data_fim_dt

    @staticmethod
    def processar_filtros(request):
        """Processa e valida os filtros da requisição"""
        projeto_id = request.GET.get("projeto", "")
        data_inicio = request.GET.get("data_inicio", "")
        data_fim = request.GET.get("data_fim", "")
        desenvolvedores_ids = request.GET.getlist("desenvolvedores", [])

        return projeto_id, data_inicio, data_fim, desenvolvedores_ids

    @staticmethod
    def aplicar_filtros_horas(projeto_id, data_inicio, data_fim, desenvolvedores_ids):
        """Aplica filtros na query de horas trabalhadas"""
        registros_horas = FatoRegistroHoras.objects.select_related(
            "funcionario", "projeto", "data"
        )

        if projeto_id:
            registros_horas = registros_horas.filter(projeto_id=projeto_id)

        if data_inicio and data_fim:
            try:
                data_inicio_dt = datetime.strptime(data_inicio, "%Y-%m-%d")
                data_fim_dt = datetime.strptime(data_fim, "%Y-%m-%d")
                registros_horas = registros_horas.filter(
                    data__data_completa__range=[data_inicio_dt, data_fim_dt]
                )
            except ValueError:
                data_inicio_dt, data_fim_dt = DashboardEquipesService.get_datas_padrao()
                registros_horas = registros_horas.filter(
                    data__data_completa__range=[data_inicio_dt, data_fim_dt]
                )
        else:
            data_inicio_dt, data_fim_dt = DashboardEquipesService.get_datas_padrao()
            registros_horas = registros_horas.filter(
                data__data_completa__range=[data_inicio_dt, data_fim_dt]
            )

        if desenvolvedores_ids:
            registros_horas = registros_horas.filter(
                funcionario__nome__in=desenvolvedores_ids
            )

        return registros_horas, data_inicio_dt, data_fim_dt

    @staticmethod
    def gerar_dados_grafico_horas(registros_horas):
        """Gera dados estruturados para o gráfico de horas por dia"""
        horas_por_dia_dev = (
            registros_horas.values(
                "data__data_completa", "funcionario__nome", "funcionario_id"
            )
            .annotate(total_horas=Sum("horas_trabalhadas"))
            .order_by("data__data_completa")
        )

        datas_unicas = sorted(
            set(
                [
                    item["data__data_completa"].strftime("%d/%m")
                    for item in horas_por_dia_dev
                ]
            )
        )
        desenvolvedores_unicos = DimFuncionario.objects.all()

        dados_grafico = []
        for data_str in datas_unicas:
            dados_dia = {"data": data_str}

            for dev in desenvolvedores_unicos:
                horas_dev = next(
                    (
                        item["total_horas"]
                        for item in horas_por_dia_dev
                        if item["data__data_completa"].strftime("%d/%m") == data_str
                        and item["funcionario__nome"] == dev.nome
                    ),
                    0,
                )

                dados_dia[dev.nome] = float(horas_dev) if horas_dev else 0.0

            dados_grafico.append(dados_dia)

        return dados_grafico

    @staticmethod
    def contar_desenvolvedores_selecionados(desenvolvedores_dropdown):
        """Conta quantos desenvolvedores estão selecionados"""
        return len([dev for dev in desenvolvedores_dropdown if dev["selected"]])

    @staticmethod
    def get_header_context():
        """Retorna o contexto do header"""
        return {
            "title": "Dashboard de Equipes",
            "subtitle": "Análise de horas por desenvolvedor",
            "breadcrumb": "Dashboard de Equipes",
        }
