from django import forms

from accounts.models import CustomUser
from .models import ChatRoom, Friend, Message


class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ['content']
        widgets = {
            'content': forms.TextInput(attrs={
                'class': 'form-control chat-input',
                'placeholder': 'Зурвас бичих...',
                'autocomplete': 'off',
            })
        }


class ChatRoomForm(forms.ModelForm):
    members = forms.ModelMultipleChoiceField(
        queryset=CustomUser.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        required=True,
        label='Нэмэх найзууд',
    )

    class Meta:
        model = ChatRoom
        fields = ['name', 'members']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Группийн нэрээ бичнэ үү',
            })
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            friend_ids = Friend.objects.filter(user=user).values_list('friend_id', flat=True)
            self.fields['members'].queryset = CustomUser.objects.filter(id__in=friend_ids).order_by('username')

    def clean_members(self):
        members = self.cleaned_data['members']
        if not members.exists():
            raise forms.ValidationError('Дор хаяж нэг найзаа сонгоно уу.')
        return members


class GroupImageForm(forms.ModelForm):
    class Meta:
        model = ChatRoom
        fields = ['image']
        widgets = {
            'image': forms.FileInput(attrs={
                'class': 'd-none',
                'accept': 'image/*',
                'onchange': 'this.form.submit()',
            })
        }


class GroupMembersForm(forms.ModelForm):
    members = forms.ModelMultipleChoiceField(
        queryset=CustomUser.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label='Нэмэх найзууд',
    )

    class Meta:
        model = ChatRoom
        fields = ['members']

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        room = kwargs.pop('room', None)
        super().__init__(*args, **kwargs)
        if user and room:
            friend_ids = Friend.objects.filter(user=user).values_list('friend_id', flat=True)
            member_ids = room.members.values_list('id', flat=True)
            self.fields['members'].queryset = (
                CustomUser.objects
                .filter(id__in=friend_ids)
                .exclude(id__in=member_ids)
                .order_by('username')
            )
