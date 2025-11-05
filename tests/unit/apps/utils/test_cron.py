import tempfile
from pathlib import Path
from unittest.mock import call, patch

from django.test import SimpleTestCase, override_settings

from apps.utils import cron


class CronLogTests(SimpleTestCase):
    def test_escrever_log_cria_arquivo_e_contem_mensagem(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            with override_settings(BASE_DIR=tmp_dir):
                cron.escrever_log("Mensagem de teste", {"foo": "bar"})

                log_file = Path(tmp_dir) / "log" / "cron_buscar_dados_api.log"
                self.assertTrue(log_file.exists())

                log_content = log_file.read_text(encoding="utf-8")
                self.assertIn("Mensagem de teste", log_content)
                self.assertIn("{'foo': 'bar'}", log_content)


class CronJobsTests(SimpleTestCase):
    @patch("apps.utils.cron.SimpleCache.set")
    @patch("apps.utils.cron.call_command")
    @patch("apps.utils.cron.escrever_log")
    @patch("apps.utils.cron.JiraService")
    def test_buscar_dados_api_sincroniza_e_atualiza_cache(
        self, mock_jira_service, mock_escrever_log, mock_call_command, mock_simple_cache
    ):
        mock_instance = mock_jira_service.return_value
        mock_instance.get_all_tasks_data.return_value = [
            {"tasks": [{"id": 1}, {"id": 2}]},
            {"tasks": [{"id": 3}]},
        ]

        cron.buscar_dados_api()

        mock_jira_service.assert_called_once()
        mock_instance.get_all_tasks_data.assert_called_once()
        self.assertEqual(
            mock_call_command.call_args_list,
            [call("sync_jira_users"), call("sync_jira_projects")],
        )
        mock_simple_cache.assert_called_once()

        context, *_ = mock_simple_cache.call_args[0]
        self.assertEqual(context["total_projetos"], 2)
        self.assertEqual(context["total_tasks_geral"], 3)
        self.assertIn("timestamp", context)
        self.assertGreater(len(mock_escrever_log.call_args_list), 0)

    @patch("apps.utils.cron.SimpleCache.set")
    @patch("apps.utils.cron.call_command")
    @patch("apps.utils.cron.escrever_log")
    @patch("apps.utils.cron.JiraService")
    def test_buscar_dados_com_etl_executa_etapas_e_atualiza_cache(
        self, mock_jira_service, mock_escrever_log, mock_call_command, mock_simple_cache
    ):
        mock_instance = mock_jira_service.return_value
        mock_instance.get_all_tasks_data.return_value = [
            {"tasks": [{"id": 1}]},
        ]

        cron.buscar_dados_com_etl()

        mock_jira_service.assert_called_once()
        mock_instance.get_all_tasks_data.assert_called_once()
        self.assertEqual(
            mock_call_command.call_args_list,
            [
                call("sync_jira_users"),
                call("sync_jira_projects"),
                call("rodar_etl"),
            ],
        )
        mock_simple_cache.assert_called_once()
        context, *_ = mock_simple_cache.call_args[0]
        self.assertEqual(context["total_projetos"], 1)
        self.assertEqual(context["total_tasks_geral"], 1)
        self.assertIn("timestamp", context)
        self.assertGreater(len(mock_escrever_log.call_args_list), 0)

    @patch("apps.utils.cron.SimpleCache.set")
    @patch("apps.utils.cron.call_command")
    @patch("apps.utils.cron.escrever_log")
    @patch("apps.utils.cron.JiraService")
    def test_buscar_dados_com_etl_sem_resposta_nao_atualiza_cache(
        self,
        mock_jira_service,
        _mock_escrever_log,
        mock_call_command,
        mock_simple_cache,
    ):
        mock_instance = mock_jira_service.return_value
        mock_instance.get_all_tasks_data.return_value = []

        cron.buscar_dados_com_etl()

        self.assertEqual(
            mock_call_command.call_args_list,
            [
                call("sync_jira_users"),
                call("sync_jira_projects"),
                call("rodar_etl"),
            ],
        )
        mock_simple_cache.assert_not_called()

    @patch("apps.utils.cron.SimpleCache.set")
    @patch("apps.utils.cron.call_command")
    @patch("apps.utils.cron.escrever_log")
    @patch("apps.utils.cron.JiraService")
    def test_buscar_dados_api_registra_erros_de_sincronizacao(
        self, mock_jira_service, mock_escrever_log, mock_call_command, mock_simple_cache
    ):
        mock_instance = mock_jira_service.return_value
        mock_instance.get_all_tasks_data.return_value = []
        mock_call_command.side_effect = [
            Exception("users fail"),
            Exception("projects fail"),
        ]

        cron.buscar_dados_api()

        messages = [args[0] for args, _ in mock_escrever_log.call_args_list]
        self.assertTrue(
            any("ERRO na sincronização de usuários" in msg for msg in messages)
        )
        self.assertTrue(
            any("ERRO na sincronização de projetos" in msg for msg in messages)
        )
        mock_simple_cache.assert_called_once()

    @patch("apps.utils.cron.SimpleCache.set")
    @patch("apps.utils.cron.call_command")
    @patch("apps.utils.cron.escrever_log")
    @patch("apps.utils.cron.JiraService")
    def test_buscar_dados_api_registra_erro_geral(
        self, mock_jira_service, mock_escrever_log, mock_call_command, mock_simple_cache
    ):
        mock_instance = mock_jira_service.return_value
        mock_instance.get_all_tasks_data.side_effect = RuntimeError("boom")

        with self.assertRaises(RuntimeError):
            cron.buscar_dados_api()

        messages = [args[0] for args, _ in mock_escrever_log.call_args_list]
        self.assertTrue(any("Erro no cron:" in msg for msg in messages))
        mock_simple_cache.assert_not_called()

    @patch("apps.utils.cron.call_command")
    @patch("apps.utils.cron.escrever_log")
    @patch("apps.utils.cron.JiraService")
    def test_buscar_dados_com_etl_registra_erro(
        self, mock_jira_service, mock_escrever_log, mock_call_command
    ):
        mock_jira_service.return_value.get_all_tasks_data.return_value = []
        mock_call_command.side_effect = Exception("falha no ETL")

        with self.assertRaises(Exception):
            cron.buscar_dados_com_etl()

        self.assertTrue(
            any(
                "Erro no cron completo" in args[0]
                for args, _ in mock_escrever_log.call_args_list
            )
        )
