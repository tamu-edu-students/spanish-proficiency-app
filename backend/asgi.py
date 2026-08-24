import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.urls import path

# This must be set before anything else imports Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

# Import our voice consumer — handles WebSocket connections
from spanish.consumers import VoiceConsumer

application = ProtocolTypeRouter({
    # Regular HTTP requests — handled by Django normally
    "http": get_asgi_application(),

    # WebSocket voice connections — handled by VoiceConsumer
    "websocket": AuthMiddlewareStack(
        URLRouter([
            path("ws/voice/", VoiceConsumer.as_asgi()),
        ])
    ),
})