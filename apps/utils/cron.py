import datetime
from pathlib import Path

from django.conf import settings
from django.core.management import call_command

from apps.dashboards.services import JiraService
from apps.utils.simple_cache import SimpleCache


def escrever_log(mensagem: str, obj: dict = None):
    """
    Escreve mensagens de log em um arquivo local.
    """
    log_dir = Path(settings.BASE_DIR) / "log"
    log_dir.mkdir(parents=True, exist_ok=True)
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
    Agora também sincroniza usuários e projetos no banco OLTP.
    """
    jira_service = JiraService()
    escrever_log("Início do cron: buscando dados na API Jira.")

    try:

        escrever_log("Sincronizando usuários do Jira...")
        try:
            call_command("sync_jira_users")
            escrever_log("Sincronização de usuários concluída com sucesso.")
        except Exception as e:
            escrever_log(f"ERRO na sincronização de usuários: {str(e)}")

        escrever_log("Sincronizando projetos do Jira...")
        try:
            call_command("sync_jira_projects")
            escrever_log("Sincronização de projetos concluída com sucesso.")
        except Exception as e:
            escrever_log(f"ERRO na sincronização de projetos: {str(e)}")

        escrever_log("Buscando dados do Jira (listagem de projetos e tasks)...")
        projetos_com_tasks = jira_service.get_all_tasks_data()

        context = {
            "projetos_com_tasks": projetos_com_tasks,
            "total_projetos": len(projetos_com_tasks),
            "total_tasks_geral": sum(
                len(projeto.get("tasks", [])) for projeto in projetos_com_tasks
            ),
            "timestamp": datetime.datetime.now().isoformat(),
        }

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


def buscar_dados_com_etl():
    """
    Cron job completo: sincroniza usuários, projetos, busca dados do Jira
    e executa o ETL.
    """
    jira_service = JiraService()
    escrever_log("Início do cron completo: Jira + ETL")

    try:
        escrever_log("Sincronizando usuários do Jira...")
        call_command("sync_jira_users")
        escrever_log("Sincronização de usuários concluída.")

        escrever_log("Sincronizando projetos do Jira...")
        call_command("sync_jira_projects")
        escrever_log("Sincronização de projetos concluída.")

        escrever_log("Buscando dados do Jira (listagem de projetos e tasks)...")
        projetos_com_tasks = jira_service.get_all_tasks_data()

        if projetos_com_tasks:
            context = {
                "projetos_com_tasks": projetos_com_tasks,
                "total_projetos": len(projetos_com_tasks),
                "total_tasks_geral": sum(
                    len(projeto.get("tasks", [])) for projeto in projetos_com_tasks
                ),
                "timestamp": datetime.datetime.now().isoformat(),
            }
            SimpleCache.set(context)
            escrever_log(f"Cache atualizado: {context['total_projetos']} projetos")

        escrever_log("Executando processo ETL...")
        call_command("rodar_etl")
        escrever_log("ETL concluído com sucesso!")

        escrever_log("Cron completo executado com sucesso!")

    except Exception as e:
        escrever_log(f"Erro no cron completo: {str(e)}")
        raise
