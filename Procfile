release: python manage.py migrate
web: gunicorn core.wsgi --bind 0.0.0.0:$PORT
