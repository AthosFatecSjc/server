"""Cron jobs para a aplicação."""

from pathlib import Path
import datetime
from django.conf import settings

def escrever_log(mensagem: str):
    """Escreve uma mensagem em um arquivo de log."""
    log_dir = Path(settings.BASE_DIR) / "log"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "cron_buscar_dados_api.log"
    agora = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{agora}] {mensagem}\n")


def buscar_dados_api():
    """
    Tarefa executada periodicamente para buscar dados em uma API,
    processá-los e salvar no banco de dados.
    """
    escrever_log("Início do cron: buscando dados na API.")
