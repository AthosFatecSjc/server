from decimal import Decimal
from types import SimpleNamespace
from unittest import mock

from django.test import TestCase

from apps.relatorios.models import (
    Funcionario,
    Issue,
    MetaProdutividade,
    Projeto,
    RegistroProdutividade,
)
from apps.relatorios.produtividade import services


class ListarMesesDisponiveisTests(TestCase):
    def test_usa_datas_das_issues(self):
        func = Funcionario.objects.create(nome="Alice")
        projeto = Projeto.objects.create(nome="Projeto Teste")
        Issue.objects.create(
            jira_id=1,
            jira_key="PROJ-1",
            projeto=projeto,
            titulo="Item",
            funcionario=func,
            criado_em="2025-07-10T12:00:00Z",
        )
        Issue.objects.create(
            jira_id=2,
            jira_key="PROJ-2",
            projeto=projeto,
            titulo="Outro",
            funcionario=func,
            criado_em="2025-07-12T12:00:00Z",
        )

        meses = services.listar_meses_disponiveis()
        self.assertEqual(meses[0]["mes"], 7)
        self.assertEqual(meses[0]["ano"], 2025)
        self.assertEqual(len(meses), 1)


class CalcularSpendsTests(TestCase):
    @mock.patch("apps.relatorios.produtividade.services._buscar_fontes_horas")
    @mock.patch(
        "apps.relatorios.produtividade.services._listar_dias_mes",
        return_value=[1, 2, 3],
    )
    @mock.patch("apps.relatorios.produtividade.services._buscar_funcionarios")
    def test_agrega_registros_e_horas(self, mock_func, mock_dias, mock_fontes):
        funcionario = Funcionario.objects.create(nome="Alice", contrato="CLT")
        mock_func.return_value = [funcionario]
        MetaProdutividade.objects.create(
            funcionario=funcionario, ano=2025, mes=7, meta_horas=200
        )
        func_id = funcionario.id
        mock_fontes.return_value = (
            {(func_id, 1): Decimal("8")},
            {(func_id, 2): Decimal("2")},
            {(func_id, 3): Decimal("3")},
        )

        data = services.calcular_spends_por_dev_com_legendas(7, 2025)

        resultado = data["resultados"][0]
        self.assertEqual(resultado["real"], 13.0)
        self.assertEqual(resultado["dias"][1], 8.0)
        self.assertEqual(resultado["dias"][2], 2.0)
        self.assertEqual(resultado["dias"][3], 3.0)
        self.assertEqual(resultado["meta"], 200.0)
        self.assertAlmostEqual(resultado["percentual"], round(13 / 200 * 100, 1))
        self.assertIn("REALIZADO", data["resultados"][-1]["funcionario"])

    @mock.patch(
        "apps.relatorios.produtividade.services._possui_horas_fato", return_value=False
    )
    def test_atualiza_registro_com_legenda(self, mock_horas):
        func = Funcionario.objects.create(nome="Alice")
        sucesso, error = services.atualizar_multiplos_dias(func.id, 7, 2025, [1], "FE")
        self.assertTrue(sucesso)
        self.assertIsNone(error)
        registro = RegistroProdutividade.objects.get(funcionario=func)
        self.assertEqual(registro.valor, Decimal("-1"))
        mock_horas.assert_called_once()

    @mock.patch(
        "apps.relatorios.produtividade.services._possui_horas_fato", return_value=True
    )
    def test_atualiza_registro_bloqueia_quando_ha_horas(self, mock_horas):
        func = Funcionario.objects.create(nome="Alice")
        sucesso, error = services.atualizar_multiplos_dias(func.id, 7, 2025, [1], "FE")
        self.assertFalse(sucesso)
        self.assertIn("horas", error.lower())

    @mock.patch(
        "apps.relatorios.produtividade.services._dias_uteis_no_mes", return_value=20
    )
    def test_meta_padrao_usa_contrato(self, mock_dias):
        func = Funcionario.objects.create(nome="Alice", contrato="ESTAGIARIO")
        valor = services.obter_meta_funcionario(func, 7, 2025)
        self.assertEqual(valor, 120.0)

    @mock.patch(
        "apps.relatorios.produtividade.services._dias_uteis_no_mes", return_value=20
    )
    def test_meta_persistida_tem_prioridade(self, mock_dias):
        func = Funcionario.objects.create(nome="Alice")
        MetaProdutividade.objects.create(
            funcionario=func, ano=2025, mes=7, meta_horas=200
        )
        valor = services.obter_meta_funcionario(func, 7, 2025)
        self.assertEqual(valor, 200.0)
