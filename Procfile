release: python manage.py migrate --run-syncdb && python manage.py collectstatic --noinput
web: gunicorn mtc_project.wsgi --log-file -
