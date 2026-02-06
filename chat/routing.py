from django.urls import re_path
from .consumers import ChatConsumer,PrivateChatConsumer ,GroupChatConsumer , UserNotificationConsumer

websocket_urlpatterns = [
    re_path(r'ws/chat/$', ChatConsumer.as_asgi()),
    re_path(r'ws/private/(?P<room_name>\w+)/$', PrivateChatConsumer.as_asgi()),
    re_path(r'ws/group/(?P<room_id>\d+)/$', GroupChatConsumer.as_asgi()),
    re_path(r'ws/notify/$', UserNotificationConsumer.as_asgi()),


]
