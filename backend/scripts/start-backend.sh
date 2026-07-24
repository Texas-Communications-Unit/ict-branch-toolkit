#!/bin/sh
set -eu

python manage.py migrate --noinput
python manage.py ensure_admin
python manage.py import_bundled_nifog \
  --apply \
  --if-approved \
  --username "$DJANGO_SUPERUSER_USERNAME"
python manage.py collectstatic --noinput
exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 2 --timeout 60
