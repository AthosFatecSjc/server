FROM python:3.11-slim

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
COPY manage.py .

# Cria usuário não-root
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser
USER appuser

# Expõe a porta
EXPOSE 8000

# Comando padrão
CMD ["gunicorn", "config.wsgi:application", "--workers", "4", "--bind", "0.0.0.0:8000"]
