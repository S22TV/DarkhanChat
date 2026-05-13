from django.urls import path

from .views import (
    ChatHomeView,
    ChatRoomDetailView,
    CreateGroupChatView,
    accept_friend_request,
    add_group_members,
    reject_friend_request,
    send_friend_request,
    start_direct_chat,
    update_group_image,
)

urlpatterns = [
    path('', ChatHomeView.as_view(), name='chat_home'),
    path('room/<int:pk>/', ChatRoomDetailView.as_view(), name='chat_room'),
    path('group/new/', CreateGroupChatView.as_view(), name='create_group_chat'),
    path('group/<int:pk>/image/', update_group_image, name='update_group_image'),
    path('group/<int:pk>/members/add/', add_group_members, name='add_group_members'),
    path('friend/request/<int:user_id>/', send_friend_request, name='send_friend_request'),
    path('friend/request/<int:request_id>/accept/', accept_friend_request, name='accept_friend_request'),
    path('friend/request/<int:request_id>/reject/', reject_friend_request, name='reject_friend_request'),
    path('direct/<int:friend_id>/', start_direct_chat, name='start_direct_chat'),
]
