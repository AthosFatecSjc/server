set -e

echo 'Rodando collectstatic...'
python manage.py collectstatic --noinput

echo 'Atualizando crontab...'
python manage.py crontab remove
python manage.py crontab add

echo 'Iniciando cron daemon em background...'
cron

echo 'Iniciando processo principal (gunicorn)...'

exec "$@"
