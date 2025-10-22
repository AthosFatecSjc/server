"""Cron jobs para a aplicação."""

import datetime
from pathlib import Path

from django.conf import settings

from apps.dashboards.services import JiraService
from apps.utils.simple_cache import SimpleCache


def escrever_log(mensagem: str, obj: dict = None):
    """
    Escreve uma mensagem no arquivo de log do cron.
    Garante que o diretório de logs exista.
    """
    log_dir = Path(settings.BASE_DIR) / "log"
    log_dir.mkdir(
        parents=True, exist_ok=True
    )  # ✅ cria o diretório, mesmo se não existir
    log_file = log_dir / "cron_buscar_dados_api.log"

    agora = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{agora}] {mensagem}\n")
        if obj:
            f.write(f"{obj}\n")


def buscar_dados_api():
    """
    Cron job executado diariamente às 19h (por padrão).
    Busca dados na API Jira, processa e salva no cache.
    """
    jira_service = JiraService()
    escrever_log("Início do cron: buscando dados na API Jira.")

    try:
        # 🔹 Busca dados e atualiza o cache
        context = jira_service.get_dashboard_context(include_timestamp=True)
        SimpleCache.set(context)

        obj = {
            "status": "sucesso",
            "total_projetos": context.get("total_projetos"),
            "total_tasks_geral": context.get("total_tasks_geral"),
        }

        escrever_log(
            f"Fim do cron: {obj['total_projetos']} projetos e "
            f"{obj['total_tasks_geral']} tasks processadas.",
            obj=obj,
        )

    except Exception as e:
        escrever_log(
            f"Erro no cron: {str(e)}",
            obj={"status": "erro", "erro": str(e)},
        )
        raise
