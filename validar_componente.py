"""
Script para validar a implementação do componente de gráfico de barras.
Executa validações estáticas sem necessidade de rodar os testes Django.
"""

import os
import sys

# Adicionar o diretório do projeto ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def validar_estrutura_arquivos():
    """Valida se todos os arquivos necessários foram criados."""
    print("🔍 Validando estrutura de arquivos...")
    
    arquivos_necessarios = [
        "apps/dashboards/projetos/services.py",
        "apps/dashboards/projetos/views.py",
        "apps/dashboards/projetos/tests.py",
        "apps/dashboards/projetos/templates/projeto/index.html",
        "apps/dashboards/projetos/templates/projeto/components/_grafico_barras.html",
        "apps/dashboards/projetos/README.md",
    ]
    
    todos_presentes = True
    for arquivo in arquivos_necessarios:
        caminho = os.path.join(os.path.dirname(__file__), arquivo)
        if os.path.exists(caminho):
            print(f"  ✅ {arquivo}")
        else:
            print(f"  ❌ {arquivo} - NÃO ENCONTRADO")
            todos_presentes = False
    
    return todos_presentes


def validar_imports():
    """Valida se os imports estão corretos."""
    print("\n🔍 Validando imports do service...")
    
    try:
        # Ler o arquivo de service
        with open("apps/dashboards/projetos/services.py", "r", encoding="utf-8") as f:
            conteudo = f.read()
        
        imports_necessarios = [
            "from decimal import Decimal",
            "from typing import Any",
            "from django.db.models import F, Sum",
            "from olap_models.models import DimProjeto, FatoRegistroHoras",
        ]
        
        for imp in imports_necessarios:
            if imp in conteudo:
                print(f"  ✅ {imp}")
            else:
                print(f"  ❌ {imp} - NÃO ENCONTRADO")
                return False
        
        return True
    except Exception as e:
        print(f"  ❌ Erro ao validar: {e}")
        return False


def validar_service_methods():
    """Valida se os métodos do service estão implementados."""
    print("\n🔍 Validando métodos do service...")
    
    try:
        with open("apps/dashboards/projetos/services.py", "r", encoding="utf-8") as f:
            conteudo = f.read()
        
        metodos_necessarios = [
            "class CustoPorDesenvolvedorService:",
            "def obter_custo_por_desenvolvedor",
            "def formatar_para_grafico",
        ]
        
        for metodo in metodos_necessarios:
            if metodo in conteudo:
                print(f"  ✅ {metodo}")
            else:
                print(f"  ❌ {metodo} - NÃO ENCONTRADO")
                return False
        
        return True
    except Exception as e:
        print(f"  ❌ Erro ao validar: {e}")
        return False


def validar_template_component():
    """Valida se o componente de template está correto."""
    print("\n🔍 Validando componente de template...")
    
    try:
        with open("apps/dashboards/projetos/templates/projeto/components/_grafico_barras.html", "r", encoding="utf-8") as f:
            conteudo = f.read()
        
        elementos_necessarios = [
            "{{ titulo }}",
            "{{ subtitulo }}",
            "{{ dados.labels|safe }}",
            "{{ dados.values|safe }}",
            "new Chart(ctx",
            "type: 'bar'",
        ]
        
        for elemento in elementos_necessarios:
            if elemento in conteudo:
                print(f"  ✅ {elemento}")
            else:
                print(f"  ❌ {elemento} - NÃO ENCONTRADO")
                return False
        
        return True
    except Exception as e:
        print(f"  ❌ Erro ao validar: {e}")
        return False


def validar_tests():
    """Valida se os testes estão implementados."""
    print("\n🔍 Validando testes...")
    
    try:
        with open("apps/dashboards/projetos/tests.py", "r", encoding="utf-8") as f:
            conteudo = f.read()
        
        testes_necessarios = [
            "class CustoPorDesenvolvedorServiceTest",
            "def test_obter_custo_por_desenvolvedor_sem_filtro",
            "def test_obter_custo_por_desenvolvedor_com_filtro_projeto",
            "def test_formatar_para_grafico_com_dados",
            "def test_formatar_para_grafico_sem_dados",
        ]
        
        for teste in testes_necessarios:
            if teste in conteudo:
                print(f"  ✅ {teste}")
            else:
                print(f"  ❌ {teste} - NÃO ENCONTRADO")
                return False
        
        return True
    except Exception as e:
        print(f"  ❌ Erro ao validar: {e}")
        return False


def validar_padrao_projeto():
    """Valida se o código segue o padrão do projeto."""
    print("\n🔍 Validando padrões do projeto...")
    
    validacoes = [
        ("Type hints implementados", "def obter_custo_por_desenvolvedor(projeto_id: int = None) -> list[dict[str, Any]]"),
        ("Docstrings presentes", '"""Serviços para o dashboard de projetos."""'),
        ("Clean code - métodos estáticos", "@staticmethod"),
    ]
    
    try:
        with open("apps/dashboards/projetos/services.py", "r", encoding="utf-8") as f:
            conteudo = f.read()
        
        for descricao, padrao in validacoes:
            if padrao in conteudo:
                print(f"  ✅ {descricao}")
            else:
                print(f"  ⚠️  {descricao} - PODE ESTAR FALTANDO")
        
        return True
    except Exception as e:
        print(f"  ❌ Erro ao validar: {e}")
        return False


def main():
    """Executa todas as validações."""
    print("=" * 60)
    print("VALIDAÇÃO DO COMPONENTE DE GRÁFICO DE BARRAS")
    print("=" * 60)
    
    validacoes = [
        validar_estrutura_arquivos(),
        validar_imports(),
        validar_service_methods(),
        validar_template_component(),
        validar_tests(),
        validar_padrao_projeto(),
    ]
    
    print("\n" + "=" * 60)
    if all(validacoes):
        print("✅ TODAS AS VALIDAÇÕES PASSARAM!")
        print("=" * 60)
        print("\n📋 Próximos passos:")
        print("1. Ative o ambiente virtual do projeto")
        print("2. Execute: python manage.py test apps.dashboards.projetos.tests")
        print("3. Verifique o componente em: http://localhost:8000/dashboards/projeto/")
        return 0
    else:
        print("❌ ALGUMAS VALIDAÇÕES FALHARAM")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
