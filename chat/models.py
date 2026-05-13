from django.db import models
from django.db.models import Count

from accounts.models import CustomUser


class Friend(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='my_friends')
    friend = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='friends_of')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'friend')
        ordering = ['friend__username']

    def __str__(self):
        return f"{self.user.username} - {self.friend.username}"


class FriendRequest(models.Model):
    PENDING = 'pending'
    ACCEPTED = 'accepted'
    REJECTED = 'rejected'

    STATUS_CHOICES = [
        (PENDING, 'Pending'),
        (ACCEPTED, 'Accepted'),
        (REJECTED, 'Rejected'),
    ]

    sender = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='sent_friend_requests')
    receiver = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='received_friend_requests')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('sender', 'receiver')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.sender.username} -> {self.receiver.username} ({self.status})"


class ChatRoom(models.Model):
    PUBLIC = 'public'
    DIRECT = 'direct'
    GROUP = 'group'

    CHAT_TYPE_CHOICES = [
        (PUBLIC, 'Public chat'),
        (DIRECT, 'Private chat'),
        (GROUP, 'Group chat'),
    ]

    name = models.CharField(max_length=100, blank=True, null=True)
    image = models.ImageField(upload_to='group_pics/', blank=True, null=True)
    chat_type = models.CharField(max_length=10, choices=CHAT_TYPE_CHOICES, default=PUBLIC)
    members = models.ManyToManyField(CustomUser, related_name='chat_rooms', blank=True)
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        related_name='created_chat_rooms',
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    @property
    def is_public(self):
        return self.chat_type == self.PUBLIC

    @property
    def is_group(self):
        return self.chat_type == self.GROUP

    def get_other_member(self, user):
        if self.chat_type != self.DIRECT:
            return None
        return self.members.exclude(id=user.id).first()

    def title_for(self, user):
        if self.chat_type == self.PUBLIC:
            if self.name and self.name != 'Public Chat':
                return self.name
            return 'Нийтийн чат'
        if self.chat_type == self.DIRECT:
            other = self.get_other_member(user)
            return other.username if other else 'Хувийн чат'
        return self.name or 'Групп чат'

    @classmethod
    def get_direct_room(cls, user, friend):
        return (
            cls.objects.filter(chat_type=cls.DIRECT, members=user)
            .filter(members=friend)
            .annotate(member_count=Count('members'))
            .filter(member_count=2)
            .first()
        )

    def __str__(self):
        return self.name or f"{self.get_chat_type_display()} #{self.id}"


class Message(models.Model):
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='sent_messages')
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"{self.sender.username}: {self.content[:30]}"
