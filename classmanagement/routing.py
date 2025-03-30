from django.urls import path
from .consumers import ClassQueryConsumer, PrivateQueryConsumer  # ✅ Fix: Correct imports

websocket_urlpatterns = [
    path("ws/classroom/<int:class_id>/", ClassQueryConsumer.as_asgi()),  # ✅ Fix: class_id should match consumers.py
    path("ws/private/<int:teacher_id>/<int:student_id>/", PrivateQueryConsumer.as_asgi()),  # ✅ Fix: Private chat
]
