FROM python:3.11-slim

# Timezone
ENV TZ=America/Sao_Paulo

# Instala pacotes do sistema e configura timezone em uma única camada
RUN apt-get update && \
    apt-get install -y --no-install-recommends cron procps tzdata && \
    ln -snf "/usr/share/zoneinfo/$TZ" /etc/localtime && echo "$TZ" > /etc/timezone && \
    rm -rf /var/lib/apt/lists/*

# Diretório de trabalho
WORKDIR /app

# Instala dependências Python
COPY requirements.txt ./
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copia o código da aplicação
COPY apps/ ./apps/
COPY config/ ./config/
COPY static/ ./static/
COPY templates/ ./templates/
COPY olap_models/ ./olap_models/
COPY banco/ ./banco/
COPY manage.py ./

# Cria usuário de execução
RUN addgroup --system appgroup && \
    adduser --system --ingroup appgroup --home /home/appuser --shell /bin/bash appuser && \
    mkdir -p /app/staticfiles /app/log && \
    chown -R appuser:appgroup /app/staticfiles /app/log

USER appuser
EXPOSE 8000

CMD ["gunicorn", "config.wsgi:application", "--workers", "4", "--bind", "0.0.0.0:8000"]
