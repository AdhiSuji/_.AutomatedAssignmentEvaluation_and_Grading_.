import json
from channels.generic.websocket import AsyncWebsocketConsumer
from .models import QueryMessage
from django.contrib.auth.models import User

class QueryConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.class_id = self.scope['url_route']['kwargs']['class_id']
        self.room_group_name = f"query_{self.class_id}"
        
        # Join room group
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        # Load past messages
        messages = await self.get_past_messages()
        await self.send(text_data=json.dumps({"past_messages": messages}))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        sender_id = data["sender_id"]
        message = data["message"]

        sender = await self.get_user(sender_id)

        # Save to database
        chat_message = QueryMessage.objects.create(
            classroom_id=self.class_id,
            sender=sender,
            message=message
        )

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat_message",
                "sender": sender.first_name,
                "message": message
            }
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            "sender": event["sender"],
            "message": event["message"]
        }))

    async def get_past_messages(self):
        messages = QueryMessage.objects.filter(classroom_id=self.class_id).order_by("timestamp")
        return [{"sender": msg.sender.first_name, "message": msg.message} for msg in messages]

    async def get_user(self, user_id):
        return await User.objects.aget(id=user_id)

