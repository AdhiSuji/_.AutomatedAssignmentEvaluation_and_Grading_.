from django.urls import path
from .consumers import QueryConsumer  # Create this later

websocket_urlpatterns = [
    path("ws/classroom/<int:classroom_id>/", QueryConsumer.as_asgi()),
]
