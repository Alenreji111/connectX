import json
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from .models import Room, Message , UserStatus
from django.utils import timezone

class ChatConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        user = self.scope["user"]
        if user.is_anonymous:

            await self.close()
            return

        self.room_name = "global"
        self.room_group_name = "chat_global"

        self.room, _ = await sync_to_async(Room.objects.get_or_create)(
            name=self.room_name
        )
    # ❌ DO NOT CHECK room.users for global chat
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

    async def receive(self, text_data):
        data = json.loads(text_data)
        message = data.get("message")
        if not message:
            return

        user = self.scope["user"]

        await sync_to_async(Message.objects.create)(
            sender=user,
            room=self.room,
            content=message
        )

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat_message",
                "message": message,
                "username": user.username,
            }
        )

        users = await sync_to_async(list)(
        self.room.users.exclude(id=sender.id)
        )

        for user in users:

            unread_count = await sync_to_async(
                Message.objects.filter(
                    room=self.room,
                    is_read=False
                ).exclude(sender=user).count
            )()

            await self.channel_layer.group_send(
                f"user_{user.id}",
                {
                    "type": "unread_notify",
                    "room_id": self.room.id,
                    "count": unread_count
                }
            )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            "message": event["message"],
            "username": event["username"],
        }))

class PrivateChatConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        user = self.scope["user"]
        if user.is_anonymous:
            await self.close()
            return

        
        self.room_name = self.scope["url_route"]["kwargs"]["room_name"]
        self.room_group_name = f"private_{self.room_name}"

        
        try:
            self.room = await sync_to_async(Room.objects.get)(name=self.room_name)
        except Room.DoesNotExist:
            await self.close()
            return

        # security: allow only room members
        is_member = await sync_to_async(
            self.room.users.filter(id=user.id).exists
        )()
        if not is_member:
            await self.close()
            return

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

        await sync_to_async(UserStatus.objects.update_or_create)(
            user=user,
            defaults={
                "is_online": True,
                "last_seen": timezone.now()
            }
        )

        await self.channel_layer.group_add(

            "presence",
            self.channel_name
        )

        await self.channel_layer.group_send(
            "presence",
            {
                "type": "presence_update",
                "user_id": user.id,
                "username": user.username,
                "is_online": True,
                "last_seen": None,
            }
        )
        await self.channel_layer.group_send(
            f"user_{user.id}",
            {
                "type": "unread_notify",
                "room_id": self.room.id,
                "count": 0
            }
        )


    async def disconnect(self, close_code):

        user = self.scope["user"]

        await sync_to_async(UserStatus.objects.update_or_create)(
            user=user,
            defaults={
                "is_online": False,
                "last_seen": timezone.now()
            }
        )  

        await self.channel_layer.group_send(
            "presence",
            {
                "type": "presence_update",
                "user_id": user.id,
                "username": user.username,
                "is_online": False,
                "last_seen": timezone.now().isoformat(),
            }
        )

        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

        await self.channel_layer.group_discard(
            "presence",
            self.channel_name
        )
    
    async def presence_update(self, event):
        await self.send(text_data=json.dumps({
            "type": "presence",
            "user_id": event["user_id"],
            "username": event["username"],
            "is_online": event["is_online"],
            "last_seen": event["last_seen"],
            }
        )
    )

    async def receive(self, text_data):
        data = json.loads(text_data)
        message = data.get("message")
        sender = self.scope["user"]

        if data.get("typing") is not None:
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                "type": "typing_event",
                "username": sender.username,
                "typing": data["typing"],
                }
            )
            return



        if not message:
            return

        

        await sync_to_async(Message.objects.create)(
            sender=sender,
            room=self.room,
            content=message,
            is_read=False
        )

        await sync_to_async(
            Room.objects.filter(id=self.room.id).update
        )(
            last_activity=timezone.now()
        )


        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "private_message",
                "message": message,
                "username": sender.username,
            }
        )
        users = await sync_to_async(list)(
            self.room.users.exclude(id=sender.id)
        )
        
        for user in users:
        
            unread_count = await sync_to_async(
                Message.objects.filter(
                    room=self.room,
                    is_read=False
                ).exclude(sender=user).count
            )()
        
            await self.channel_layer.group_send(
                f"user_{user.id}",
                {
                    "type": "unread_notify",
                    "room_id": self.room.id,
                    "count": unread_count
                }
            )
        
    async def typing_event(self, event):
        await self.send(text_data=json.dumps({
             "type": "typing",
             "username": event["username"],
             "typing": event["typing"],
            }
        ))

    async def private_message(self, event):
        await self.send(text_data=json.dumps({
            "message": event["message"],
            "username": event["username"],
        }))


class GroupChatConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        user = self.scope["user"]
        self.room_id = self.scope["url_route"]["kwargs"]["room_id"]
        self.room_group_name = f"group_{self.room_id}"

        self.room = await sync_to_async(Room.objects.get)(id=self.room_id)

        is_member = await sync_to_async(
            self.room.users.filter(id=user.id).exists
        )()
        if not is_member:
            await self.close()
            return

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

    async def receive(self, text_data):
        data = json.loads(text_data)
        message = data.get("message")

        await sync_to_async(Message.objects.create)(
            sender=self.scope["user"],
            room=self.room,
            content=message
        )

        await sync_to_async(
            Room.objects.filter(id=self.room.id).update
        )(
            last_activity=timezone.now()
        )


        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "group_message",
                "message": message,
                "username": self.scope["user"].username,
                "sender_id": self.scope["user"].id
            }
        )

    async def group_message(self, event):
        await self.send(text_data=json.dumps(event))

class UserNotificationConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        user = self.scope["user"]
        if user.is_anonymous:
            await self.close()
            return

        self.group_name = f"user_{user.id}"

        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        await self.accept()

    async def unread_notify(self, event):
            await self.send(text_data=json.dumps({
                "type": "unread_update",
                "room_id": event["room_id"],
                "count": event["count"]
            }))

    

