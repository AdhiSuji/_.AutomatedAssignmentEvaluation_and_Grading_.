# classmanagement/routing.py

from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/query/(?P<class_id>\d+)/$', consumers.QueryClassroomConsumer.as_asgi()),
    re_path(r'ws/query_1to1/(?P<teacher_id>\d+)/(?P<student_id>\d+)/$', consumers.Query1to1Consumer.as_asgi()),
]
