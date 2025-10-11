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
        projetos_com_tasks = jira_service.get_all_tasks_data()

        total_projetos = len(projetos_com_tasks)
        total_tasks_geral = sum(proj['total_tasks']
                                for proj in projetos_com_tasks)

        context = {
            'projetos_com_tasks': projetos_com_tasks,
            'total_projetos': total_projetos,
            'total_tasks_geral': total_tasks_geral,
            'ultima_atualizacao': datetime.datetime.now().isoformat()
        }

        SimpleCache.set(context)

        escrever_log(
            f"Fim do cron: Processados {total_projetos} projetos "
            f"com {total_tasks_geral} tasks total. Dados salvos no cache.",
            obj={'status': 'sucesso', 'total_projetos': total_projetos}
        )

    except Exception as e:
        escrever_log(
            f"Erro no cron: {str(e)}",
            obj={'status': 'erro', 'erro': str(e)}
        )
        raise
