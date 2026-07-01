"""
ASGI config for sns_project project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application

# ASGI application entrypoint
# - ASGI サーバーはこの callable を使って Django アプリを起動します。
# - 非同期対応の WebSocket や HTTP リクエストの受け口になります。
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sns_project.settings')

application = get_asgi_application()
