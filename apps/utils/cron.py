"""Cron jobs para a aplicação."""


def buscar_dados_api():
    """
    Tarefa executada a cada 1 hora para buscar dados em uma API,
    processá-los e salvar no banco de dados.

    """
