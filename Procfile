release: python manage.py migrate && python manage.py collectstatic --noinput && python manage.py createsuperuser --noinput --username bango02christopher@gmail.com --email bango02christopher@gmail.com
web: gunicorn mtc_project.wsgi --log-file -
