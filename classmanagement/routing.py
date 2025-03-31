from django.urls import re_path
from classmanagement.consumers import QueryConsumer

websocket_urlpatterns = [
    re_path(r"ws/query/(?P<room_name>\w+)/$", QueryConsumer.as_asgi()),
]
