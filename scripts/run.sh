#!/bin/sh
set -e

echo "Waiting for PostgreSQL..."
python manage.py wait_for_db

echo "Collecting static files..."
python manage.py collectstatic --noinput

if [ "${DJANGO_MAKE_MIGRATIONS:-False}" = "True" ]; then
    echo "Creating migrations..."
    python manage.py makemigrations --noinput
fi

echo "Applying database migrations..."
python manage.py migrate --noinput

echo "Starting Django local development server..."
DJANGO_RUN_LOCAL_WEB_SERVER=${DJANGO_RUN_LOCAL_WEB_SERVER:-True}

if [ "$DJANGO_RUN_LOCAL_WEB_SERVER" = "False" ]; then
    uwsgi --socket :8000 --workers 4 --master --enable-threads --module config.wsgi --buffer-size=32768
else
    uwsgi --http :8000 --workers 4 --master --enable-threads --module config.wsgi --buffer-size=32768
fi
