"""Cron jobs para a aplicação."""

import datetime
from pathlib import Path

from django.conf import settings

from apps.dashboards.services import JiraService
from apps.utils.simple_cache import SimpleCache


def escrever_log(mensagem: str, obj: dict = None):
    """Escreve uma mensagem em um arquivo de log."""

    log_dir = Path(settings.BASE_DIR) / "log"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "cron_buscar_dados_api.log"
    agora = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{agora}] {mensagem}\n")
        if obj:
            f.write(f"{obj}\n")


def buscar_dados_api():
    """
    Tarefa executada periodicamente para buscar dados em uma API,
    processá-los e salvar no cache.
    """

    jira_service = JiraService()
    escrever_log("Início do cron: buscando dados na API.")

    try:
        context = jira_service.get_dashboard_context(include_timestamp=True)

        SimpleCache.set(context)

        obj = {'status': 'sucesso',
               'total_projetos': context['total_projetos']}

        escrever_log(
            f"Fim do cron: Processados {context['total_projetos']} projetos "
            f"com {context['total_tasks_geral']} tasks total. Dados salvos no cache.",
            obj=obj
        )

    except Exception as e:
        escrever_log(
            f"Erro no cron: {str(e)}",
            obj={'status': 'erro', 'erro': str(e)}
        )
        raise
