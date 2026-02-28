from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Room(models.Model):
    name = models.CharField(max_length=255)
    users = models.ManyToManyField(
        User,
        through="GroupMember",
        related_name="rooms"
    )
    is_private = models.BooleanField(default=False)
    is_group = models.BooleanField(default=False)
    avatar = models.ImageField(
        upload_to="room_avatars/",
        null=True,
        blank=True
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="created_groups",
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    last_activity = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    


class Message(models.Model):
    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="sent_messages"
    )
    receiver = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="received_messages",
        null=True,
        blank=True
    )
    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    content = models.TextField()
    audio = models.FileField(upload_to="chat_audio/", null=True, blank=True)
    reply_to = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="replies"
    )
    is_deleted = models.BooleanField(default=False)
    deleted_for = models.ManyToManyField(User, related_name="deleted_messages", blank=True)
    is_edited = models.BooleanField(default=False)
    edited_at = models.DateTimeField(null=True, blank=True)
    is_delivered = models.BooleanField(default=False)
    is_read = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)


    def __str__(self):
        return f"{self.sender.username}: {self.content[:20]}"

class UserStatus(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    is_online = models.BooleanField(default=False)
    last_seen = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.user.username

class Contact(models.Model):
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="contacts"
    )
    contact = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="added_by"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("owner", "contact")

    def __str__(self):
        return f"{self.owner} -> {self.contact}"

class Reaction(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.ForeignKey("Message", on_delete=models.CASCADE, related_name="reactions")
    emoji = models.CharField(max_length=10)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'message']


class GroupMember(models.Model):

    ROLE_CHOICES = (
        ("creator", "Creator"),
        ("admin", "Admin"),
        ("member", "Member"),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    room = models.ForeignKey(Room, on_delete=models.CASCADE)

    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default="member")

    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "room")

    def __str__(self):
        return f"{self.user.username} - {self.role}"
