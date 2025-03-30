import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.layers import get_channel_layer  # ✅ Fix: Import required for channel layer
from django.contrib.auth import get_user_model

User = get_user_model()


class PrivateQueryConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.teacher_id = self.scope['url_route']['kwargs']['teacher_id']
        self.student_id = self.scope['url_route']['kwargs']['student_id']
        self.room_group_name = f"query_1to1_{self.teacher_id}_{self.student_id}"

        self.channel_layer = get_channel_layer()  # ✅ Fix: Define channel layer
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def receive(self, text_data):
        data = json.loads(text_data)
        message = data["message"]
        sender = self.scope["user"]

        await self.channel_layer.group_send(
            self.room_group_name,
            {"type": "chat_message", "message": message, "sender": sender.first_name}
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({"sender": event["sender"], "message": event["message"]}))


class ClassQueryConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.class_id = self.scope['url_route']['kwargs']['class_id']
        self.room_group_name = f"query_class_{self.class_id}"

        self.channel_layer = get_channel_layer()  # ✅ Fix: Define channel layer
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def receive(self, text_data):
        data = json.loads(text_data)
        message = data["message"]
        sender = self.scope["user"]

        await self.channel_layer.group_send(
            self.room_group_name,
            {"type": "chat_message", "message": message, "sender": sender.first_name}
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({"sender": event["sender"], "message": event["message"]}))
