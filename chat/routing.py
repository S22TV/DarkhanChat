from django.urls import path

from .consumers import ChatConsumer, UserNotificationConsumer

websocket_urlpatterns = [
    path('ws/chat/<int:room_id>/', ChatConsumer.as_asgi(), name='ws_chat'),
    path('ws/notifications/', UserNotificationConsumer.as_asgi(), name='ws_notifications'),
]
