import json
from channels.generic.websocket import AsyncWebsocketConsumer
from .models import QueryMessage
from django.contrib.auth import get_user_model
from channels.db import database_sync_to_async

User = get_user_model()

class QueryConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_group_name = f'chat_{self.room_name}'
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        # Get the message and sender_id from the received WebSocket message
        data = json.loads(text_data)
        message = data['message']
        sender_id = data['sender_id']
        
        # Save the message to the database
        await self.save_message(self.room_name, sender_id, message)

        # Send the message to the WebSocket group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': message,
                'sender_id': sender_id  # Send sender_id back to the group
            }
        )

    async def chat_message(self, event):
        # Send the message to WebSocket client
        await self.send(text_data=json.dumps({
            'message': event['message'],
            'sender_id': event['sender_id']
        }))

    @database_sync_to_async
    def save_message(self, room_name, sender_id, message):
        # Use the correct custom user model
        User = get_user_model()
        sender = User.objects.get(id=sender_id)
        # Save the message in the database (QueryMessage model)
        return QueryMessage.objects.create(
            room_name=room_name,
            sender=sender,
            content=message
        )


import json
from channels.generic.websocket import AsyncWebsocketConsumer
from django.utils.timezone import now
from django.contrib.auth.models import User
from .models import PrivateMessage, TeacherProfile, StudentProfile

class PrivateChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.teacher_id = self.scope['url_route']['kwargs']['teacher_id']
        self.student_id = self.scope['url_route']['kwargs']['student_id']
        self.room_group_name = f"private_chat_{self.teacher_id}_{self.student_id}"
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        message = data['message']
        sender = self.scope["user"]

        # Get teacher and student objects
        teacher = await self.get_user_by_profile(TeacherProfile, self.teacher_id)
        student = await self.get_user_by_profile(StudentProfile, self.student_id)

        receiver = teacher if sender.id == student.id else student

        # Save message to DB
        PrivateMessage.objects.create(
            sender=sender,
            receiver=receiver,
            message=message,
            timestamp=now()
        )

        # Send message to group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat_message",
                "message": message,
                "sender": sender.first_name,
            }
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            "message": event["message"],
            "sender": event["sender"],
        }))

    @staticmethod
    async def get_user_by_profile(profile_model, user_id):
        try:
            profile = await profile_model.objects.select_related("teacher" if profile_model == TeacherProfile else "student").aget(pk=user_id)
            return profile.teacher if profile_model == TeacherProfile else profile.student
        except:
            return None
