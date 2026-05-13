from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import CustomUser


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True, label="Имэйл")
    phone_number = forms.CharField(max_length=15, required=False, label="Утасны дугаар")
    profile_picture = forms.ImageField(
        required=False,
        label="Профайл зураг",
        widget=forms.FileInput(attrs={'class': 'd-none', 'accept': 'image/*'}),
    )

    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'phone_number', 'profile_picture', 'password1', 'password2']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in self.fields:
            self.fields[field_name].widget.attrs.update({'class': 'form-control'})
        self.fields['profile_picture'].widget.attrs.update({'class': 'd-none', 'accept': 'image/*'})

    def clean_phone_number(self):
        return self.cleaned_data.get('phone_number') or None


class ProfileForm(forms.ModelForm):
    new_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        required=False,
        label="Шинэ нууц үг",
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        required=False,
        label="Нууц үг давтах",
    )

    class Meta:
        model = CustomUser
        fields = ['email', 'phone_number', 'profile_picture']
        widgets = {
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
            'profile_picture': forms.FileInput(attrs={'class': 'd-none', 'accept': 'image/*'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        new_pass = cleaned_data.get("new_password")
        confirm_pass = cleaned_data.get("confirm_password")

        if new_pass and new_pass != confirm_pass:
            raise forms.ValidationError("Нууц үг таарахгүй байна.")
        return cleaned_data

    def clean_phone_number(self):
        return self.cleaned_data.get('phone_number') or None


class CustomLoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in self.fields:
            self.fields[field_name].widget.attrs.update({'class': 'form-control'})
