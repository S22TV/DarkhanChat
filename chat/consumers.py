import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.utils import timezone

from .models import ChatRoom, Message, MessageRead


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
        await self.mark_room_read()
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return

        if data.get('type') == 'read':
            await self.mark_room_read()
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
                'room_id': self.room_id,
                'timestamp': message.timestamp.strftime('%Y-%m-%d %H:%M'),
            },
        )
        await self.notify_room_members(message)

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'message',
            'message': event['message'],
            'username': event['username'],
            'user_id': event['user_id'],
            'room_id': event['room_id'],
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
        message = Message.objects.create(room=room, sender=self.user, content=content)
        MessageRead.objects.update_or_create(
            room=room,
            user=self.user,
            defaults={'last_read_at': timezone.now()},
        )
        return message

    @database_sync_to_async
    def mark_room_read(self):
        room = ChatRoom.objects.filter(id=self.room_id).first()
        if room is None:
            return
        if room.is_public or room.members.filter(id=self.user.id).exists():
            MessageRead.objects.update_or_create(
                room=room,
                user=self.user,
                defaults={'last_read_at': timezone.now()},
            )

    @database_sync_to_async
    def get_room_notification_payloads(self, message):
        room = message.room
        if room.chat_type == ChatRoom.PUBLIC:
            return []

        payloads = []
        for member in room.members.exclude(id=self.user.id):
            read_state = MessageRead.objects.filter(room=room, user=member).first()
            unread_messages = Message.objects.filter(room=room).exclude(sender=member)
            if read_state:
                unread_messages = unread_messages.filter(timestamp__gt=read_state.last_read_at)
            unread_count = unread_messages.count()

            title = room.title_for(member)
            avatar_text = title[:1].upper() if title else '#'
            avatar_url = ''
            other = room.get_other_member(member)
            if other and getattr(other, 'has_profile_picture', False):
                avatar_url = other.profile_picture.url
            elif room.image:
                avatar_url = room.image.url

            payloads.append({
                'user_id': member.id,
                'room_id': room.id,
                'chat_type': room.chat_type,
                'room_url': f'/chat/room/{room.id}/',
                'title': title,
                'subtitle': 'Шинэ зурвас',
                'avatar_text': avatar_text,
                'avatar_url': avatar_url,
                'unread_count': unread_count,
            })
        return payloads

    async def notify_room_members(self, message):
        payloads = await self.get_room_notification_payloads(message)
        for payload in payloads:
            await self.channel_layer.group_send(
                f'user_{payload["user_id"]}',
                {
                    'type': 'notify',
                    'event': 'chat_update',
                    **payload,
                },
            )


class UserNotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope['user']
        if not self.user.is_authenticated:
            await self.close()
            return

        self.user_group_name = f'user_{self.user.id}'
        await self.channel_layer.group_add(self.user_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'user_group_name'):
            await self.channel_layer.group_discard(self.user_group_name, self.channel_name)

    async def notify(self, event):
        payload = dict(event)
        payload.pop('type', None)
        await self.send(text_data=json.dumps(payload))
