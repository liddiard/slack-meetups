#!/bin/sh
# Docker script to set up and run the Django app

# Run Django management commands
python manage.py collectstatic --noinput
python manage.py makemigrations matcher
python manage.py migrate
python manage.py createsuperuser --no-input

# Start supercronic
supercronic /app/cron-jobs

# Start Gunicorn server
exec gunicorn meetups.wsgi:application --bind 0.0.0.0:$PORT
