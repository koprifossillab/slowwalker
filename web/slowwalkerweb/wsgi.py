"""WSGI 입구. gunicorn 이 `slowwalkerweb.wsgi:application` 으로 부른다."""
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "slowwalkerweb.settings")

application = get_wsgi_application()
