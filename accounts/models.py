from django.db import models
from django.contrib.auth.models import User


class Profile(models.Model):

    user = models.OneToOneField(User, on_delete=models.CASCADE)

    avatar = models.ImageField(
        upload_to="avatars/",
        default="avatars/default.png"
    )

    bio = models.CharField(max_length=120, blank=True)

    def __str__(self):
        return self.user.username


