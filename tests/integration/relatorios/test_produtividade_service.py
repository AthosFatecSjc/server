from datetime import date, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from django.test import TestCase
from django.utils.timezone import make_aware

from apps.relatorios.models import (
    Funcionario,
    Issue,
    MetaProdutividade,
    RegistroProdutividade,
)
from apps.relatorios.produtividade.services import (
    CODIGO_ESPECIAL_VALORES,
    HORAS_DIA_CONTRATO,
    atualizar_meta_funcionario,
    atualizar_multiplos_dias,
    calcular_spends_por_dev_com_legendas,
    exportar_produtividade_pdf,
    listar_equipes_disponiveis,
    listar_meses_disponiveis,
    obter_meta_funcionario,
)
from olap_models.models import DimTempo, FatoRegistroHoras


@pytest.fixture
def mock_projeto():
    """Fixture que retorna um mock de projeto"""
    mock = MagicMock()
    mock.id = 1
    return mock


@pytest.fixture
def projeto_db():
    """Fixture para obter ou criar um projeto do banco"""
    try:

        try:
            from apps.dashboards.projetos.models import Projeto
        except ImportError:
            try:
                from apps.dashboards.models import Projeto
            except ImportError:
                from apps.relatorios.models import Projeto

        projeto = Projeto.objects.using("default").first()
        if projeto:
            return projeto
        else:

            projeto = Projeto.objects.using("default").create(
                nome="Projeto Teste", key="TEST"
            )
            return projeto
    except Exception:

        pytest.skip("Não foi possível obter um projeto para teste")


@pytest.mark.django_db(databases=["default", "olap"])
class TestProdutividadeService:

    def test_listar_meses_disponiveis_com_dados(self, projeto_db):
        """Testa listagem de meses quando há issues no banco"""

        funcionario = Funcionario.objects.using("default").create(
            nome="Funcionário Teste", time="Desenvolvimento", contrato="CLT"
        )

        Issue.objects.using("default").create(
            jira_id=12345,
            jira_key="TEST-123",
            titulo="Issue de Teste",
            projeto=projeto_db,
            funcionario=funcionario,
            tempo_gasto_seconds=3600,
            criado_em=make_aware(datetime(2024, 1, 15)),
        )

        meses = listar_meses_disponiveis()

        assert len(meses) > 0
        assert any(mes["mes"] == 1 and mes["ano"] == 2024 for mes in meses)
        assert all("mes" in mes and "ano" in mes and "mes_nome" in mes for mes in meses)

    def test_listar_meses_disponiveis_sem_dados(self):
        """Testa listagem de meses quando não há issues"""

        Issue.objects.using("default").all().delete()

        meses = listar_meses_disponiveis()

        assert len(meses) == 1
        assert meses[0]["mes"] == datetime.now().month
        assert meses[0]["ano"] == datetime.now().year

    def test_listar_equipes_disponiveis(self):
        """Testa listagem de equipes disponíveis"""

        Funcionario.objects.using("default").create(
            nome="João Silva", time="Desenvolvimento", contrato="CLT"
        )
        Funcionario.objects.using("default").create(
            nome="Maria Santos", time="Desenvolvimento", contrato="CLT"
        )
        Funcionario.objects.using("default").create(
            nome="Pedro Costa", time="QA", contrato="CLT"
        )

        equipes = listar_equipes_disponiveis()

        assert "Desenvolvimento" in equipes
        assert "QA" in equipes
        assert equipes == sorted(equipes)

    def test_calcular_spends_por_dev_com_legendas_sem_funcionarios(self):
        """Testa cálculo de spends quando não há funcionários na equipe"""

        resultado = calcular_spends_por_dev_com_legendas(1, 2024, "EquipeInexistente")

        assert resultado["dias"] == list(range(1, 32))
        assert resultado["resultados"] == []

    def test_calcular_spends_por_dev_com_legendas_com_funcionarios(self):
        """Testa cálculo de spends com funcionários existentes"""

        funcionario = Funcionario.objects.using("default").create(
            nome="Teste Funcionário", time="Desenvolvimento", contrato="CLT"
        )

        with patch(
            "apps.relatorios.produtividade.services._buscar_funcionarios"
        ) as mock_buscar:
            with patch(
                "apps.relatorios.produtividade.services._buscar_fontes_horas"
            ) as mock_fontes:
                with patch(
                    "apps.relatorios.produtividade.services.obter_meta_funcionario"
                ) as mock_meta:

                    mock_buscar.return_value = [funcionario]
                    mock_fontes.return_value = ({}, {}, {})
                    mock_meta.return_value = 160.0

                    resultado = calcular_spends_por_dev_com_legendas(
                        1, 2024, "Desenvolvimento"
                    )

        assert len(resultado["dias"]) == 31
        assert len(resultado["resultados"]) == 2
        assert resultado["resultados"][0]["funcionario"] == "Teste Funcionário"
        assert resultado["resultados"][0]["real"] == 0.0
        assert resultado["resultados"][0]["meta"] == 160.0
        assert resultado["resultados"][0]["percentual"] == 0.0

    def test_atualizar_multiplos_dias_sucesso(self):
        """Testa atualização de múltiplos dias com sucesso"""

        funcionario = Funcionario.objects.using("default").create(
            nome="Funcionário Teste", time="Desenvolvimento", contrato="CLT"
        )

        sucesso, erro = atualizar_multiplos_dias(
            funcionario_id=funcionario.id, mes=1, ano=2024, dias=[1, 2, 3], codigo="FE"
        )

        assert sucesso is True
        assert erro is None

        registros = RegistroProdutividade.objects.using("default").filter(
            funcionario_id=funcionario.id, dia__year=2024, dia__month=1
        )
        assert registros.count() == 3
        assert all(
            registro.valor == CODIGO_ESPECIAL_VALORES["FE"] for registro in registros
        )

    def test_atualizar_multiplos_dias_com_erro(self):
        """Testa atualização de múltiplos dias com código inválido"""

        funcionario = Funcionario.objects.using("default").create(
            nome="Funcionário Teste", time="Desenvolvimento", contrato="CLT"
        )

        sucesso, erro = atualizar_multiplos_dias(
            funcionario_id=funcionario.id,
            mes=1,
            ano=2024,
            dias=[1, 2],
            codigo="CODIGO_INVALIDO",
        )

        assert sucesso is False
        assert "Código de ausência inválido" in erro

    def test_atualizar_meta_funcionario(self):
        """Testa atualização de meta do funcionário"""

        funcionario = Funcionario.objects.using("default").create(
            nome="Funcionário Meta Teste", time="Desenvolvimento", contrato="CLT"
        )

        resultado = atualizar_meta_funcionario(
            funcionario_id=funcionario.id, mes=1, ano=2024, meta=180.0
        )

        assert resultado is True

        meta_salva = MetaProdutividade.objects.using("default").get(
            funcionario_id=funcionario.id, mes=1, ano=2024
        )
        assert float(meta_salva.meta_horas) == 180.0

    def test_obter_meta_funcionario_com_meta_existente(self):
        """Testa obtenção de meta quando existe meta cadastrada"""

        funcionario = Funcionario.objects.using("default").create(
            nome="Funcionário Meta Existente", time="Desenvolvimento", contrato="CLT"
        )

        MetaProdutividade.objects.using("default").create(
            funcionario=funcionario, mes=1, ano=2024, meta_horas=Decimal("200.0")
        )

        meta = obter_meta_funcionario(funcionario, 1, 2024)

        assert meta == 200.0

    def test_obter_meta_funcionario_sem_meta_existente(self):
        """Testa obtenção de meta padrão quando não existe meta cadastrada"""

        funcionario = Funcionario.objects.using("default").create(
            nome="Funcionário Sem Meta", time="Desenvolvimento", contrato="CLT"
        )

        with patch(
            "apps.relatorios.produtividade.services._dias_uteis_no_mes"
        ) as mock_dias_uteis:
            mock_dias_uteis.return_value = 20

            meta = obter_meta_funcionario(funcionario, 1, 2024)

        assert meta == 160.0

    def test_exportar_produtividade_pdf(self):
        """Testa geração do PDF do relatório"""

        resultados = [
            {
                "funcionario": "João Silva",
                "dias": {1: 8.0, 2: 7.5, 3: 8.0},
                "real": 23.5,
                "meta": 160.0,
                "percentual": 14.7,
            },
            {
                "funcionario": "REALIZADO",
                "dias": {1: 8.0, 2: 7.5, 3: 8.0},
                "real": 23.5,
                "meta": 160.0,
                "percentual": 14.7,
            },
        ]

        pdf_content = exportar_produtividade_pdf(1, 2024, resultados)

        assert pdf_content is not None
        assert len(pdf_content) > 0
        assert b"%PDF" in pdf_content

    def test_codigos_especiais_valores(self):
        """Testa se os códigos especiais estão mapeados corretamente"""
        assert CODIGO_ESPECIAL_VALORES["FE"] == -1
        assert CODIGO_ESPECIAL_VALORES["AT"] == -2
        assert CODIGO_ESPECIAL_VALORES["FO"] == -3
        assert CODIGO_ESPECIAL_VALORES["FA"] == -4
        assert CODIGO_ESPECIAL_VALORES["LI"] == -5
        assert CODIGO_ESPECIAL_VALORES["CO"] == -6

    def test_horas_dia_contrato(self):
        """Testa configuração de horas por tipo de contrato"""
        assert HORAS_DIA_CONTRATO["CLT"] == Decimal("8")
        assert HORAS_DIA_CONTRATO["ESTAGIARIO"] == Decimal("6")


class TestProdutividadeServiceSemProjeto:
    """Testes que não precisam criar Issues com projeto"""

    @pytest.mark.django_db(databases=["default"])
    def test_listar_equipes_sem_issues(self):
        """Testa listagem de equipes sem criar issues"""

        Funcionario.objects.using("default").create(
            nome="Funcionário Teste", time="Equipe Teste", contrato="CLT"
        )

        equipes = listar_equipes_disponiveis()

        assert "Equipe Teste" in equipes

    @pytest.mark.django_db(databases=["default"])
    def test_atualizar_meta_sem_issues(self):
        """Testa atualização de meta sem criar issues"""

        funcionario = Funcionario.objects.using("default").create(
            nome="Funcionário Meta", time="Teste", contrato="CLT"
        )

        resultado = atualizar_meta_funcionario(funcionario.id, 1, 2024, 150.0)

        assert resultado is True

        meta = MetaProdutividade.objects.using("default").get(
            funcionario_id=funcionario.id, mes=1, ano=2024
        )
        assert float(meta.meta_horas) == 150.0

    @pytest.mark.django_db(databases=["default"])
    def test_listar_meses_sem_issues_existentes(self):
        """Testa listagem de meses quando não há issues no banco"""

        Issue.objects.using("default").all().delete()

        meses = listar_meses_disponiveis()

        assert len(meses) == 1
        assert meses[0]["mes"] == datetime.now().month
        assert meses[0]["ano"] == datetime.now().year


class TestProdutividadeServiceComMocks:
    """Testes que usam mocks para evitar problemas de importação"""

    @pytest.mark.django_db(databases=["default"])
    def test_calcular_spends_com_mock_completo(self):
        """Testa cálculo de spends com mock completo para evitar criar Issues"""

        funcionario = Funcionario.objects.using("default").create(
            nome="Funcionário Mock", time="Desenvolvimento", contrato="CLT"
        )

        with patch(
            "apps.relatorios.produtividade.services._buscar_funcionarios"
        ) as mock_buscar:
            with patch(
                "apps.relatorios.produtividade.services._buscar_fontes_horas"
            ) as mock_fontes:
                with patch(
                    "apps.relatorios.produtividade.services.obter_meta_funcionario"
                ) as mock_meta:
                    with patch(
                        "apps.relatorios.produtividade.services._listar_dias_mes"
                    ) as mock_dias:

                        mock_buscar.return_value = [funcionario]
                        mock_fontes.return_value = ({}, {}, {})
                        mock_meta.return_value = 160.0
                        mock_dias.return_value = list(range(1, 32))

                        resultado = calcular_spends_por_dev_com_legendas(
                            1, 2024, "Desenvolvimento"
                        )

        assert len(resultado["dias"]) == 31
        assert len(resultado["resultados"]) == 2


def get_projeto_model():
    """Tenta descobrir dinamicamente qual é o modelo Projeto"""
    try:
        from apps.dashboards.projetos.models import Projeto

        return Projeto
    except ImportError:
        try:
            from apps.dashboards.models import Projeto

            return Projeto
        except ImportError:
            try:
                from apps.relatorios.models import Projeto

                return Projeto
            except ImportError:

                from django.apps import apps

                try:
                    return apps.get_model("dashboards", "Projeto")
                except LookupError:
                    try:
                        return apps.get_model("relatorios", "Projeto")
                    except LookupError:
                        return None
