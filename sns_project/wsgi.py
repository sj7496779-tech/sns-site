"""
WSGI config for sns_project project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

# WSGI application entrypoint
# - WSGI サーバー（gunicorn, uWSGI など）はこの callable を使います。
# - 通常の同期 HTTP リクエストを処理するためのエントリポイントです。
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sns_project.settings')

application = get_wsgi_application()
