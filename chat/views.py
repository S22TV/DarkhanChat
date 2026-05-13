from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Max
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DetailView, TemplateView
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from datetime import timedelta

from accounts.models import CustomUser
from .forms import ChatRoomForm, GroupImageForm, GroupMembersForm, MessageForm
from .models import ChatRoom, Friend, FriendRequest, Message, MessageRead


def unread_counts_for(user, rooms):
    room_ids = [room.id for room in rooms]
    reads = {
        item.room_id: item.last_read_at
        for item in MessageRead.objects.filter(user=user, room_id__in=room_ids)
    }
    counts = {}
    for room in rooms:
        unread = Message.objects.filter(room=room).exclude(sender=user)
        if room.id in reads:
            unread = unread.filter(timestamp__gt=reads[room.id])
        counts[room.id] = unread.count()
    return counts


def avatar_url_for(user):
    if getattr(user, 'has_profile_picture', False):
        return user.profile_picture.url
    return ''


def notify_user(user_id, event, **payload):
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f'user_{user_id}',
        {
            'type': 'notify',
            'event': event,
            **payload,
        },
    )


class ChatHomeView(LoginRequiredMixin, TemplateView):
    template_name = 'chat/home.html'
    login_url = 'login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        public_room = ChatRoom.objects.filter(chat_type=ChatRoom.PUBLIC).order_by('id').first()
        if public_room is None:
            public_room = ChatRoom.objects.create(
                chat_type=ChatRoom.PUBLIC,
                name='Нийтийн чат',
                created_by=user,
            )
        if public_room.name == 'Public Chat':
            public_room.name = 'Нийтийн чат'
            public_room.save(update_fields=['name'])
        public_room.members.add(user)

        friends = Friend.objects.filter(user=user).select_related('friend')
        friend_ids = list(friends.values_list('friend_id', flat=True))
        incoming_requests = (
            FriendRequest.objects
            .filter(receiver=user, status=FriendRequest.PENDING)
            .select_related('sender')
        )
        outgoing_requests = FriendRequest.objects.filter(sender=user, status=FriendRequest.PENDING)
        incoming_ids = list(incoming_requests.values_list('sender_id', flat=True))
        outgoing_ids = list(outgoing_requests.values_list('receiver_id', flat=True))

        people = (
            CustomUser.objects
            .exclude(id=user.id)
            .exclude(id__in=friend_ids)
            .exclude(id__in=incoming_ids)
            .exclude(id__in=outgoing_ids)
            .order_by('username')
        )
        online_time = timezone.now() - timedelta(minutes=5)
        online_friends = friends.filter(friend__last_seen__gte=online_time)
        online_friend_ids = list(online_friends.values_list('friend_id', flat=True))

        search_text = self.request.GET.get('q', '').strip()
        search_results = CustomUser.objects.none()
        if search_text:
            search_results = (
                CustomUser.objects
                .filter(username__icontains=search_text)
                .exclude(id=user.id)
                .order_by('username')[:12]
            )

        group_chats = (
            ChatRoom.objects.filter(chat_type=ChatRoom.GROUP, members=user)
            .prefetch_related('members', 'messages')
            .annotate(last_message_at=Max('messages__timestamp'))
            .order_by('-last_message_at', '-created_at')
        )
        direct_rooms = (
            ChatRoom.objects
            .filter(chat_type=ChatRoom.DIRECT, members=user)
            .prefetch_related('members')
            .annotate(last_message_at=Max('messages__timestamp'))
            .order_by('-last_message_at', '-created_at')
        )
        recent_chats = []
        seen_friend_ids = set()
        for room in direct_rooms:
            other = room.get_other_member(user)
            if other and other.id not in seen_friend_ids:
                recent_chats.append({'room': room, 'friend': other})
                seen_friend_ids.add(other.id)
        unread_counts = unread_counts_for(
            user,
            list(group_chats) + [item['room'] for item in recent_chats],
        )
        for item in recent_chats:
            item['unread_count'] = unread_counts.get(item['room'].id, 0)

        context.update({
            'public_room': public_room,
            'friends': friends,
            'online_friends': online_friends,
            'online_friend_ids': online_friend_ids,
            'people': people,
            'incoming_requests': incoming_requests,
            'outgoing_requests': outgoing_requests.select_related('receiver'),
            'incoming_ids': incoming_ids,
            'outgoing_ids': outgoing_ids,
            'friend_ids': friend_ids,
            'search_text': search_text,
            'search_results': search_results,
            'recent_chats': recent_chats,
            'group_chats': [
                {
                    'room': room,
                    'title': room.title_for(user),
                    'unread_count': unread_counts.get(room.id, 0),
                }
                for room in group_chats
            ],
            'unread_counts': unread_counts,
        })
        return context


class ChatRoomDetailView(LoginRequiredMixin, DetailView):
    model = ChatRoom
    template_name = 'chat/room.html'
    context_object_name = 'room'
    login_url = 'login'

    def dispatch(self, request, *args, **kwargs):
        room = get_object_or_404(ChatRoom, pk=kwargs['pk'])
        user = request.user

        if room.is_public:
            room.members.add(user)
        elif not room.members.filter(id=user.id).exists():
            messages.error(request, 'Та энэ чат руу хандах эрхгүй байна.')
            return redirect('chat_home')

        MessageRead.objects.update_or_create(
            room=room,
            user=user,
            defaults={'last_read_at': timezone.now()},
        )
        self.object = room
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        return self.object

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        room = self.object
        user = self.request.user
        online_time = timezone.now() - timedelta(minutes=5)
        online_user_ids = list(
            room.members
            .filter(last_seen__gte=online_time)
            .values_list('id', flat=True)
        )
        friends = Friend.objects.filter(user=user).select_related('friend')
        online_friends = friends.filter(friend__last_seen__gte=online_time)
        context.update({
            'messages': room.messages.select_related('sender'),
            'message_form': MessageForm(),
            'room_title': room.title_for(user),
            'other_member': room.get_other_member(user),
            'is_member': room.members.filter(id=user.id).exists(),
            'online_user_ids': online_user_ids,
            'friends': friends,
            'online_friends': online_friends,
        })
        if room.is_group:
            context['group_image_form'] = GroupImageForm(instance=room)
            context['group_members_form'] = GroupMembersForm(user=user, room=room, instance=room)
        return context


class CreateGroupChatView(LoginRequiredMixin, CreateView):
    model = ChatRoom
    form_class = ChatRoomForm
    template_name = 'chat/create_group.html'
    success_url = reverse_lazy('chat_home')
    login_url = 'login'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.chat_type = ChatRoom.GROUP
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        self.object.members.add(self.request.user)
        self.object.members.add(*form.cleaned_data['members'])
        messages.success(self.request, 'Групп чат үүслээ.')
        return response


@require_POST
def send_friend_request(request, user_id):
    if not request.user.is_authenticated:
        return redirect('login')

    receiver = get_object_or_404(CustomUser, id=user_id)
    if receiver == request.user:
        return redirect('chat_home')

    if Friend.objects.filter(user=request.user, friend=receiver).exists():
        messages.info(request, 'Та хоёр аль хэдийн найзууд байна.')
        return redirect('chat_home')

    reverse_request = FriendRequest.objects.filter(
        sender=receiver,
        receiver=request.user,
        status=FriendRequest.PENDING,
    ).first()
    if reverse_request:
        return accept_friend_request(request, reverse_request.id)

    request_obj, created = FriendRequest.objects.get_or_create(
        sender=request.user,
        receiver=receiver,
        defaults={'status': FriendRequest.PENDING},
    )
    if not created and request_obj.status != FriendRequest.PENDING:
        request_obj.status = FriendRequest.PENDING
        request_obj.save(update_fields=['status', 'updated_at'])

    notify_user(
        receiver.id,
        'friend_request',
        request_id=request_obj.id,
        sender_id=request.user.id,
        username=request.user.username,
        avatar_text=request.user.username[:1].upper(),
        avatar_url=avatar_url_for(request.user),
        accept_url=f'/chat/friend/request/{request_obj.id}/accept/',
        reject_url=f'/chat/friend/request/{request_obj.id}/reject/',
    )
    messages.success(request, f'{receiver.username} руу найзын хүсэлт илгээлээ.')
    return redirect('chat_home')


@require_POST
def accept_friend_request(request, request_id):
    if not request.user.is_authenticated:
        return redirect('login')

    friend_request = get_object_or_404(
        FriendRequest,
        id=request_id,
        receiver=request.user,
        status=FriendRequest.PENDING,
    )
    Friend.objects.get_or_create(user=request.user, friend=friend_request.sender)
    Friend.objects.get_or_create(user=friend_request.sender, friend=request.user)
    friend_request.status = FriendRequest.ACCEPTED
    friend_request.save(update_fields=['status', 'updated_at'])
    notify_user(
        friend_request.sender_id,
        'friend_request_resolved',
        request_id=friend_request.id,
        status=FriendRequest.ACCEPTED,
        friend_id=request.user.id,
        username=request.user.username,
        avatar_text=request.user.username[:1].upper(),
        avatar_url=avatar_url_for(request.user),
        chat_url=f'/chat/direct/{request.user.id}/',
    )
    notify_user(request.user.id, 'friend_request_removed', request_id=friend_request.id)
    messages.success(request, f'{friend_request.sender.username} таны найз боллоо.')
    return redirect('chat_home')


@require_POST
def reject_friend_request(request, request_id):
    if not request.user.is_authenticated:
        return redirect('login')

    friend_request = get_object_or_404(
        FriendRequest,
        id=request_id,
        receiver=request.user,
        status=FriendRequest.PENDING,
    )
    friend_request.status = FriendRequest.REJECTED
    friend_request.save(update_fields=['status', 'updated_at'])
    notify_user(
        friend_request.sender_id,
        'friend_request_resolved',
        request_id=friend_request.id,
        status=FriendRequest.REJECTED,
        friend_id=request.user.id,
        username=request.user.username,
    )
    notify_user(request.user.id, 'friend_request_removed', request_id=friend_request.id)
    messages.info(request, 'Найзын хүсэлтийг татгалзлаа.')
    return redirect('chat_home')


@require_POST
def update_group_image(request, pk):
    if not request.user.is_authenticated:
        return redirect('login')

    room = get_object_or_404(ChatRoom, pk=pk, chat_type=ChatRoom.GROUP, members=request.user)
    form = GroupImageForm(request.POST, request.FILES, instance=room)
    if form.is_valid():
        form.save()
        messages.success(request, 'Группийн зураг шинэчлэгдлээ.')
    else:
        messages.error(request, 'Зураг шинэчлэхэд алдаа гарлаа.')
    return redirect('chat_room', pk=room.pk)


@require_POST
def add_group_members(request, pk):
    if not request.user.is_authenticated:
        return redirect('login')

    room = get_object_or_404(ChatRoom, pk=pk, chat_type=ChatRoom.GROUP, members=request.user)
    form = GroupMembersForm(request.POST, user=request.user, room=room, instance=room)
    if form.is_valid():
        members = form.cleaned_data['members']
        if members:
            room.members.add(*members)
            messages.success(request, 'Группт шинэ гишүүн нэмлээ.')
        else:
            messages.info(request, 'Нэмэх найз сонгоогүй байна.')
    else:
        messages.error(request, 'Гишүүн нэмэхэд алдаа гарлаа.')
    return redirect('chat_room', pk=room.pk)


def start_direct_chat(request, friend_id):
    if not request.user.is_authenticated:
        return redirect('login')

    friend_relation = get_object_or_404(Friend, user=request.user, friend_id=friend_id)
    friend = friend_relation.friend

    room = ChatRoom.get_direct_room(request.user, friend)
    if room is None:
        room = ChatRoom.objects.create(
            chat_type=ChatRoom.DIRECT,
            created_by=request.user,
            name=f'{request.user.username} & {friend.username}',
        )
        room.members.add(request.user, friend)

    return redirect('chat_room', pk=room.pk)
