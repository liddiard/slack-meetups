#!/bin/sh
# Docker script to set up and run the Django app

# Load environment variables from .env file, stripping comments
if [ -f .env ]; then
  export $(cat .env | grep -v '^#' | xargs)
fi

# Run Django management commands
python manage.py collectstatic --noinput
python manage.py makemigrations matcher
python manage.py migrate
python manage.py createsuperuser --no-input

# Start the cron service
service cron start

# Start Gunicorn server
exec gunicorn meetups.wsgi:application --bind 0.0.0.0:$PORT
