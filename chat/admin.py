from django.contrib import admin

from .models import ChatRoom, Friend, Message


@admin.register(Friend)
class FriendAdmin(admin.ModelAdmin):
    list_display = ('user', 'friend', 'created_at')
    search_fields = ('user__username', 'friend__username')


@admin.register(ChatRoom)
class ChatRoomAdmin(admin.ModelAdmin):
    list_display = ('name', 'chat_type', 'created_by', 'created_at')
    list_filter = ('chat_type', 'created_at')
    search_fields = ('name', 'members__username')
    filter_horizontal = ('members',)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('sender', 'room', 'timestamp')
    search_fields = ('sender__username', 'content')
    list_filter = ('timestamp',)
