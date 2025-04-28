import json
from channels.generic.websocket import AsyncWebsocketConsumer
from django.utils.timezone import now
from django.db import models
from asgiref.sync import sync_to_async

class QueryClassroomConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.class_id = self.scope['url_route']['kwargs']['class_id']
        self.room_group_name = f'classroom_{self.class_id}'

        # Fetch and send old messages
        old_messages = await self.get_old_messages()

        # Send old messages to the WebSocket
        for message in old_messages:
            await self.send(text_data=json.dumps({
                'message': message.message,
                'sender': message.sender.first_name
            }))

        # Join the group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        message = data['message']
        sender_id = self.scope["user"].id
        sender_name = self.scope["user"].first_name

        # Send the message to all group members
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': message,
                'sender': sender_name,
            }
        )

        # Save the message to the database
        await self.save_message(sender_id, message)

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'message': event['message'],
            'sender': event['sender']
        }))

    @sync_to_async
    def save_message(self, sender_id, message):
        try:
            sender = User.objects.get(id=sender_id)
            classroom = Classroom.objects.get(id=self.class_id)

            QueryMessage.objects.create(
                classroom=classroom,
                sender=sender,
                message=message,
                timestamp=now()
            )
        except Exception as e:
            print(f"[ERROR] Failed to save classroom message: {e}")

    @sync_to_async
    def get_old_messages(self):
        try:
            classroom = Classroom.objects.get(id=self.class_id)
            messages = QueryMessage.objects.filter(classroom=classroom).order_by('timestamp')
            return messages
        except Exception as e:
            print(f"[ERROR] Failed to fetch old classroom messages: {e}")
            return []



from .models import PrivateMessage, User
from django.utils.timezone import now
import json

class Query1to1Consumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.teacher_id = self.scope['url_route']['kwargs']['teacher_id']
        self.student_id = self.scope['url_route']['kwargs']['student_id']
        self.room_group_name = f"query1to1_{self.teacher_id}_{self.student_id}"

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        message = data['message']
        sender_id = self.scope["user"].id

        # Send message to group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat_message",
                "message": message,
                "sender": self.scope["user"].first_name
            }
        )

        # ✅ Save the message in the database
        try:
            sender = await sync_to_async(User.objects.get)(id=sender_id)

            if int(sender_id) == int(self.student_id):
                receiver = await sync_to_async(User.objects.get)(id=self.teacher_id)
            else:
                receiver = await sync_to_async(User.objects.get)(id=self.student_id)

            await sync_to_async(PrivateMessage.objects.create)(
                sender=sender,
                receiver=receiver,
                message=message,
                timestamp=now()
            )
        except Exception as e:
            print(f"ERROR saving message: {e}")

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            "message": event["message"],
            "sender": event["sender"]
        }))

