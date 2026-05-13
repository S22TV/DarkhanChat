import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from .models import ChatRoom, Message


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group_name = f'chat_room_{self.room_id}'
        self.user = self.scope['user']

        if not self.user.is_authenticated:
            await self.close()
            return

        can_join = await self.user_can_join()
        if not can_join:
            await self.close()
            return

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return

        message_content = data.get('message', '').strip()
        if not message_content:
            return

        message = await self.save_message(message_content)
        if message is None:
            return

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': message_content,
                'username': self.user.username,
                'user_id': self.user.id,
                'timestamp': message.timestamp.strftime('%Y-%m-%d %H:%M'),
            },
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'message',
            'message': event['message'],
            'username': event['username'],
            'user_id': event['user_id'],
            'timestamp': event['timestamp'],
        }))

    @database_sync_to_async
    def user_can_join(self):
        room = ChatRoom.objects.filter(id=self.room_id).first()
        if room is None:
            return False
        if room.is_public:
            room.members.add(self.user)
            return True
        return room.members.filter(id=self.user.id).exists()

    @database_sync_to_async
    def save_message(self, content):
        room = ChatRoom.objects.filter(id=self.room_id).first()
        if room is None:
            return None
        if not room.is_public and not room.members.filter(id=self.user.id).exists():
            return None
        room.members.add(self.user)
        return Message.objects.create(room=room, sender=self.user, content=content)
