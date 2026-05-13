from datetime import timedelta

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


def default_profile_pic():
    return 'default.jpg'


class CustomUser(AbstractUser):
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=15, blank=True, null=True, unique=True)
    profile_picture = models.ImageField(
        upload_to='profile_pics/',
        default=default_profile_pic,
        blank=True,
        null=True,
        verbose_name="Профайл зураг",
    )
    last_seen = models.DateTimeField(blank=True, null=True)

    def is_online(self):
        if not self.last_seen:
            return False
        return self.last_seen >= timezone.now() - timedelta(minutes=5)

    def has_profile_picture(self):
        return bool(self.profile_picture and self.profile_picture.name != 'default.jpg')

    def __str__(self):
        return self.username
