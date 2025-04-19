from django.urls import re_path
from classmanagement.consumers import PrivateChatConsumer

websocket_urlpatterns = [
    re_path(r'ws/query_1to1/(?P<teacher_id>\d+)/(?P<student_id>\d+)/$', PrivateChatConsumer.as_asgi()),
]
