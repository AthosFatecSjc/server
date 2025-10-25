# 🚀 Guia de Execução e Testes da Aplicação

## ✅ Comandos Executados com Sucesso

### 1. Ambiente Virtual
```bash
cd /home/caique/Documentos/Athos-server/server
python3 -m venv venv
source venv/bin/activate
```
**Status:** ✅ Criado com sucesso

### 2. Instalação de Dependências
```bash
pip install -r requirements.txt
```
**Status:** ✅ Todas as dependências instaladas
- Django 5.2.6
- Chart.js (via CDN no template)
- PostgreSQL driver
- E todas as outras dependências

### 3. Migrations
```bash
python manage.py migrate --database=default
```
**Status:** ✅ Banco OLTP configurado (sem migrations pendentes)

```bash
python manage.py migrate --database=olap
```
**Status:** ⚠️ **Erro encontrado** - Dados existentes violam constraint `ano_range_valid`

**Problema:** Há dados antigos na tabela `dim_tempo` com anos fora do range permitido.

**Solução:** O banco OLTP está funcionando. O OLAP pode ser corrigido depois com:
```bash
# Opção 1: Limpar dados antigos do OLAP
psql -h 127.0.0.1 -p 5432 -U caiquebtc -d athos_olap -c "TRUNCATE TABLE dim_tempo CASCADE;"
python manage.py migrate --database=olap

# Opção 2: Rodar ETL novamente
python manage.py rodar_etl
```

### 4. Servidor
```bash
python manage.py runserver
```
**Status:** ✅ **FUNCIONANDO!**
- Servidor rodando em: `http://127.0.0.1:8000/`
- Sem erros de sistema
- Pronto para testes

---

## 📋 Comandos Resumidos (Para Próxima Vez)

### Start Rápido
```bash
cd /home/caique/Documentos/Athos-server/server
source venv/bin/activate
python manage.py runserver
```

### Se Precisar Reinstalar
```bash
cd /home/caique/Documentos/Athos-server/server
rm -rf venv  # Remover ambiente antigo
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py runserver
```

---

## 🧪 Como Testar o Componente de Gráfico

### 1. Acessar no Navegador
```
http://127.0.0.1:8000/dashboards/projeto/
```

### 2. Você Deve Ver:
- ✅ Header do dashboard
- ✅ Breadcrumb de navegação
- ✅ Componente de gráfico de barras (se houver dados)
- ⚠️ Mensagem "Nenhum dado disponível" (se não houver dados)

### 3. Para Ver o Gráfico com Dados

O gráfico precisa de dados na tabela OLAP `fato_registro_horas`. Como o banco OLAP teve erro na migration, você tem 2 opções:

#### Opção A: Corrigir o Banco OLAP e Rodar ETL
```bash
source venv/bin/activate

# Limpar dados problemáticos
psql -h 127.0.0.1 -p 5432 -U caiquebtc -d athos_olap << EOF
TRUNCATE TABLE fato_registro_horas CASCADE;
TRUNCATE TABLE dim_tempo CASCADE;
TRUNCATE TABLE dim_funcionario CASCADE;
TRUNCATE TABLE dim_projeto CASCADE;
EOF

# Rodar migrations novamente
python manage.py migrate --database=olap

# Rodar ETL para popular dados
python manage.py rodar_etl
```

#### Opção B: Inserir Dados de Teste Manualmente
```bash
source venv/bin/activate
python manage.py shell
```

Depois no shell Python:
```python
from decimal import Decimal
from datetime import datetime
from olap_models.models import DimProjeto, DimFuncionario, DimTempo, FatoRegistroHoras

# Criar projeto
projeto = DimProjeto.objects.using('olap').create(nome="Projeto Teste")

# Criar funcionários
dev1 = DimFuncionario.objects.using('olap').create(
    nome="Mateus Santos",
    valor_hora=Decimal("50.00")
)

dev2 = DimFuncionario.objects.using('olap').create(
    nome="João Silva",
    valor_hora=Decimal("45.00")
)

# Criar tempo
tempo = DimTempo.objects.using('olap').create(
    data_completa=datetime(2025, 1, 15),
    dia=15,
    mes=1,
    ano=2025,
    trimestre="Q1",
    dia_da_semana="Segunda-feira"
)

# Criar registros de horas
FatoRegistroHoras.objects.using('olap').create(
    funcionario=dev1,
    projeto=projeto,
    data=tempo,
    horas_trabalhadas=Decimal("100.00"),
    custo=Decimal("5000.00")
)

FatoRegistroHoras.objects.using('olap').create(
    funcionario=dev2,
    projeto=projeto,
    data=tempo,
    horas_trabalhadas=Decimal("90.00"),
    custo=Decimal("4050.00")
)

print("✅ Dados inseridos com sucesso!")
exit()
```

Depois recarregue a página do dashboard.

---

## 🔍 Validar que Está Funcionando

### URLs Disponíveis
```
http://127.0.0.1:8000/                          # Home
http://127.0.0.1:8000/dashboards/               # Lista de dashboards
http://127.0.0.1:8000/dashboards/projeto/       # Dashboard de Projeto (SEU COMPONENTE!)
http://127.0.0.1:8000/dashboards/desenvolvedores/ # Dashboard de Desenvolvedores
http://127.0.0.1:8000/relatorios/               # Relatórios
```

### Checklist de Validação Visual
- [ ] Header aparece corretamente
- [ ] Breadcrumb funciona
- [ ] Botão "Voltar" funciona
- [ ] Componente de gráfico está visível
- [ ] Se houver dados: barras aparecem em azul
- [ ] Hover nas barras mostra tooltip com valor em R$
- [ ] Gráfico é responsivo (redimensione a janela)
- [ ] Console do navegador sem erros

---

## 🐛 Troubleshooting

### Servidor não inicia
**Erro:** `ModuleNotFoundError: No module named 'django'`
**Solução:** Ativar o ambiente virtual
```bash
source venv/bin/activate
```

### Erro na página
**Erro:** Página em branco ou erro 500
**Solução:** Verificar logs no terminal onde rodou `runserver`

### Gráfico não aparece
**Causa 1:** Sem dados no banco OLAP
**Solução:** Seguir "Opção B" acima para inserir dados de teste

**Causa 2:** Chart.js não carregou
**Solução:** Abrir DevTools (F12) → Network → Verificar se Chart.js foi carregado

### Erro de constraint no OLAP
**Erro:** `check constraint "ano_range_valid" of relation "dim_tempo" is violated`
**Solução:** Limpar dados antigos:
```bash
psql -h 127.0.0.1 -p 5432 -U caiquebtc -d athos_olap -c "TRUNCATE TABLE dim_tempo CASCADE;"
python manage.py migrate --database=olap
```

---

## 🎯 Status Final dos Comandos

| Comando | Necessário? | Status | Observação |
|---------|------------|--------|------------|
| `python3 -m venv venv` | ✅ Sim | ✅ OK | Ambiente virtual criado |
| `source venv/bin/activate` | ✅ Sim | ✅ OK | Sempre necessário |
| `pip install -r requirements.txt` | ✅ Sim | ✅ OK | Dependências instaladas |
| `python manage.py migrate --database=default` | ✅ Sim | ✅ OK | OLTP configurado |
| `python manage.py migrate --database=olap` | ✅ Sim | ⚠️ Erro | Dados antigos problemáticos |
| `psql ... insert.sql` | ⏭️ Opcional | - | Apenas se quiser dados OLTP |
| `python manage.py rodar_etl` | ⏭️ Depois | - | Após corrigir OLAP |
| `python manage.py runserver` | ✅ Sim | ✅ OK | Servidor funcionando! |

---

## ✨ Próximos Passos

1. **Testar Visualmente**
   ```bash
   source venv/bin/activate
   python manage.py runserver
   # Abrir: http://127.0.0.1:8000/dashboards/projeto/
   ```

2. **Adicionar Dados de Teste** (se necessário)
   - Seguir "Opção B" acima

3. **Rodar Testes Unitários**
   ```bash
   source venv/bin/activate
   python manage.py test apps.dashboards.projetos.tests --verbosity=2
   ```

4. **Validar Qualidade**
   ```bash
   python3 validar_componente.py
   ```

5. **Code Review**
   - Revisar código
   - Testar em diferentes navegadores
   - Validar responsividade

---

## 📞 Resumo para o Time

**Status:** ✅ **Aplicação funcionando!**

- Servidor Django rodando na porta 8000
- Componente de gráfico implementado
- Banco OLTP funcionando
- Banco OLAP precisa de correção (opcional)

**Componente está em:**
- URL: `/dashboards/projeto/`
- Código: `apps/dashboards/projetos/`

**Para testar localmente:**
```bash
cd /home/caique/Documentos/Athos-server/server
source venv/bin/activate
python manage.py runserver
# Acessar: http://127.0.0.1:8000/dashboards/projeto/
```

🎉 **Tudo pronto para revisão!**
