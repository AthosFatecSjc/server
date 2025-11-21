from datetime import datetime, timedelta

from django.db.models import Sum
from django.utils import timezone

from olap_models.models import DimFuncionario, DimProjeto, FatoRegistroHoras


class DashboardEquipesService:

    @staticmethod
    def get_dev_color(index):
        """Retorna cores consistentes para os desenvolvedores (pelo índice)."""
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
    def get_colors_by_dev():
        """Mapa determinístico nome -> cor, usando ordenação estável por nome."""
        devs = list(
            DimFuncionario.objects.order_by("nome").values_list("nome", flat=True)
        )
        return {
            name: DashboardEquipesService.get_dev_color(idx)
            for idx, name in enumerate(devs)
        }

    @staticmethod
    def get_desenvolvedores_dropdown(
        projeto_id=None, data_inicio_dt=None, data_fim_dt=None, desenvolvedores_ids=None
    ):
        """
        Retorna desenvolvedores filtrados por projeto (quando informado) e marca selecionados:
        - Se o usuário enviou a lista, respeita apenas esses nomes.
        - Caso contrário, seleciona todos do projeto (com horas registradas alguma vez naquele projeto).
        """
        registros_base = FatoRegistroHoras.objects.all()
        if projeto_id:
            registros_base = registros_base.filter(projeto_id=projeto_id)

        ids_devs_projeto = registros_base.values_list("funcionario_id", flat=True)
        base_devs = (
            DimFuncionario.objects.filter(id__in=ids_devs_projeto).distinct()
            if projeto_id
            else DimFuncionario.objects.all()
        )
        if not base_devs.exists():
            base_devs = DimFuncionario.objects.all()

        color_map = DashboardEquipesService.get_colors_by_dev()

        desenvolvedores_dropdown = []
        for dev in base_devs.order_by("nome"):
            selecionado = (
                True if not desenvolvedores_ids else dev.nome in desenvolvedores_ids
            )
            desenvolvedores_dropdown.append(
                {
                    "name": dev.nome,
                    "color": color_map.get(
                        dev.nome, DashboardEquipesService.get_dev_color(0)
                    ),
                    "selected": selecionado,
                }
            )

        return desenvolvedores_dropdown

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
    def _parse_date(date_str):
        """Tenta converter datas nos formatos ISO (YYYY-MM-DD) ou BR (DD/MM/YYYY)."""
        for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        return None

    @staticmethod
    def aplicar_filtros_horas(projeto_id, data_inicio, data_fim, desenvolvedores_ids):
        """Aplica filtros na query de horas trabalhadas"""
        registros_horas = FatoRegistroHoras.objects.select_related(
            "funcionario", "projeto", "data"
        )

        if projeto_id:
            registros_horas = registros_horas.filter(projeto_id=projeto_id)

        if data_inicio and data_fim:
            data_inicio_dt = DashboardEquipesService._parse_date(data_inicio)
            data_fim_dt = DashboardEquipesService._parse_date(data_fim)

            if data_inicio_dt and data_fim_dt:
                registros_horas = registros_horas.filter(
                    data__data_completa__range=[data_inicio_dt, data_fim_dt]
                )
            else:
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
            {item["data__data_completa"] for item in horas_por_dia_dev}
        )
        desenvolvedores_unicos = DimFuncionario.objects.all()

        dados_grafico = []
        for data_dt in datas_unicas:
            data_str = data_dt.strftime("%d/%m")
            data_iso = data_dt.strftime("%Y-%m-%d")

            dados_dia = {"data": data_str, "data_iso": data_iso}

            for dev in desenvolvedores_unicos:
                horas_dev = next(
                    (
                        item["total_horas"]
                        for item in horas_por_dia_dev
                        if item["data__data_completa"] == data_dt
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
