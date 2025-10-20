FROM python:3.11-slim

# Instalar dependências do cron e ps
RUN apt-get update && apt-get install -y --no-install-recommends cron procps && rm -rf /var/lib/apt/lists/*

# Cria diretório de trabalho
WORKDIR /app

# Copia e instala dependências
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copia os diretórios necessários
COPY apps/ ./apps/
COPY config/ ./config/
COPY static/ ./static/
COPY templates/ ./templates/
COPY olap_models/ ./olap_models/
COPY banco/ ./banco/
COPY manage.py .

# Cria usuário, pasta de estáticos, e dá permissão
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser
RUN mkdir -p /app/staticfiles

# Troca para o usuário não-root
USER appuser

# Expõe a porta
EXPOSE 8000

# Comando para coletar arquivos estáticos
CMD ["gunicorn", "config.wsgi:application", "--workers", "4", "--bind", "0.0.0.0:8000"]
