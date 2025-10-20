FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends cron procps \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY apps/ ./apps/
COPY config/ ./config/
COPY static/ ./static/
COPY templates/ ./templates/
COPY olap_models/ ./olap_models/
COPY banco/ ./banco/
COPY manage.py ./

# Cria usuário, pasta de estáticos, e dá permissão
RUN addgroup --system appgroup \
    && adduser --system --ingroup appgroup --home /home/appuser --shell /bin/bash appuser \
    && mkdir -p /app/staticfiles \
    && chown -R appuser:appgroup /app/staticfiles

USER appuser

EXPOSE 8000

CMD ["gunicorn", "config.wsgi:application", "--workers", "4", "--bind", "0.0.0.0:8000"]
