"""
ASGI config for connectx project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/asgi/
"""


import os

# 1️⃣ Set settings FIRST (nothing above this)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "connectx.settings")

# 2️⃣ Now safely import Django ASGI
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

# 3️⃣ Initialize Django
django_asgi_app = get_asgi_application()

# 4️⃣ Import routing ONLY AFTER Django is ready
import chat.routing

# 5️⃣ ASGI application
application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AuthMiddlewareStack(
        URLRouter(chat.routing.websocket_urlpatterns)
    ),
})
