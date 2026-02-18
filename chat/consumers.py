import json
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from .models import Room, Message , UserStatus , Reaction
from django.utils import timezone
from django.db.models import Count
from django.conf import settings
from datetime import timedelta

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
        self.room.users.exclude(id=user.id)
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
        

        
        try:
            self.room = await sync_to_async(Room.objects.get)(name=self.room_name)
        except Room.DoesNotExist:
            await self.close()
            return

        self.room_group_name = f"room_{self.room.id}"

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

        await sync_to_async(
            Message.objects.filter(
                room=self.room,
                is_delivered=False
            ).exclude(sender=user).update
        )(
            is_delivered=True
        )

        read_messages = await sync_to_async(list)(
            Message.objects.filter(
            room=self.room,
            is_read=False
            ).exclude(sender=user)
        )

        await sync_to_async(
            Message.objects.filter(
                id__in=[msg.id for msg in read_messages]
            ).update
        )(is_read=True)

        for msg in read_messages:
            await self.channel_layer.group_send(
                f"user_{msg.sender_id}",
                {
                    "type": "message_read",
                    "message_id": msg.id,
                    "room_id": self.room.id
                }
            )


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

        undelivered = await sync_to_async(list)(
            Message.objects.filter(
                room=self.room,
                is_delivered=False
            ).exclude(sender=user)
        )

        for msg in undelivered:

            await self.channel_layer.group_send(
                f"user_{msg.sender_id}",
                {
                    "type": "message_delivered",
                    "message_id": msg.id
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
        event_type = data.get("type")

        if event_type == "edit":
            message_id = data.get("message_id")
            new_text = data.get("message")
            user = self.scope["user"]

            try:
                msg = await sync_to_async(Message.objects.get)(id=message_id)
            except Message.DoesNotExist:
                return
        
            if msg.sender_id != user.id:
                return
        
            msg.content = new_text
            await sync_to_async(msg.save)()
        
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "message_edited",
                    "message_id": message_id,
                    "message": new_text
                }
            )
            return

        # DELETE MESSAGE
        if event_type == "delete":

            message_id = data.get("message_id")
            user = self.scope["user"]

            try:
                msg = await sync_to_async(Message.objects.get)(id=message_id)

        # security check (VERY IMPORTANT)
                if msg.sender_id != user.id:
                    return

                await sync_to_async(
                     Message.objects.filter(id=message_id).update
                    )(
                    is_deleted=True,
                    content="This message was deleted"
                )

        # 🔥 broadcast delete to room
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        "type":"message_deleted",
                        "message_id": message_id,
                    }
                )

            except Exception as e:
                print("DELETE ERROR:", e)

            return

        if event_type == "reaction":

            message_id = data.get("message_id")
            emoji = data.get("emoji")
            user = self.scope["user"]


            try:
                msg = await sync_to_async(Message.objects.get)(id=message_id)
        
                # 🔐 SECURITY CHECK (VERY IMPORTANT)
                if msg.room_id != self.room.id:
                    return
        
            except Message.DoesNotExist:
                return

            reaction, created = await sync_to_async(
                Reaction.objects.get_or_create
            )(
                user=user,
                message=msg,
                defaults={"emoji": emoji}
            )

            if not created:
                if reaction.emoji == emoji:
                    await sync_to_async(reaction.delete)()
                    action = "removed"
                else:
                    reaction.emoji = emoji
                    await sync_to_async(reaction.save)()
                    action = "updated"
            else:
                action = "added"
        
            reaction_queryset = await sync_to_async(
                lambda: list(
                    Reaction.objects
                    .filter(message=msg)
                    .select_related("user__profile")
                )
            )()

            reactions = {}
            
            for reaction in reaction_queryset:
                emoji = reaction.emoji
            
                if emoji not in reactions:
                    reactions[emoji] = []
            
                reactions[emoji].append({
                    "username": reaction.user.username,
                    "avatar": reaction.user.profile.avatar.url
                })
            
            print("REACTIONS DATA SENT:", reactions)


            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "reaction_event",
                    "message_id": message_id,
                    "reactions": reactions
                }
            )
        
            return
        
        

        
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
        
        if event_type != "message":
            return

        message = data.get("message")
        if not message:
            return
        reply_id = data.get("reply_to")
        reply_message = None
        
        if reply_id:
            try:
               reply_message = await sync_to_async(
                    lambda: Message.objects.select_related("sender").get(id=reply_id)
                )()
            except Message.DoesNotExist:
                reply_message = None


        


        receiver = await sync_to_async(
            self.room.users.exclude(id=sender.id).first
        )()


        msg = await sync_to_async(Message.objects.create)(
            sender=sender,
            receiver=receiver,
            room=self.room,
            content=message,
            reply_to=reply_message,
            is_read=False,
            is_delivered=False
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
                "message_id": msg.id,
                "reply_to": {
                    "id": reply_message.id,
                    "content": reply_message.content,
                    "username": reply_message.sender.username,
                } if reply_message else None,
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
            "type": "private_message",
            "message": event["message"],
            "username": event["username"],
            "message_id": event["message_id"],
            "reply_to": event.get("reply_to"),
        }))

    # ⭐ MARK AS DELIVERED INSTANTLY
        user = self.scope["user"]

        msg = await sync_to_async(Message.objects.get)(id=event["message_id"])

        if msg.sender_id != user.id:

            msg.is_delivered = True
            await sync_to_async(msg.save)()

        # notify sender
            await self.channel_layer.group_send(
               f"user_{msg.sender_id}",
                {
                    "type": "message_delivered",
                    "message_id": msg.id,
                    "room_id": msg.room_id
                }
            )
        
    async def message_deleted(self, event):
        await self.send(text_data=json.dumps({
            "type": "message_deleted",
            "message_id": event["message_id"]
        }))

    async def message_edited(self, event):
        await self.send(text_data=json.dumps({
            "type": "message_edited",
            "message_id": event["message_id"],
            "message": event["message"]
        }))

    async def reaction_event(self, event):
        await self.send(text_data=json.dumps({
            "type": "reaction_event",
            "message_id": event["message_id"],
            "reactions": event["reactions"],
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
        if data.get("type") == "delete":

            message_id = data.get("message_id")
            mode = data.get("mode")
            user = self.scope["user"]

            try:
                msg = await sync_to_async(Message.objects.get)(id=message_id)
                if mode == "me":
                    await sync_to_async(msg.deleted_for.add)(user)
                
                    await self.send(text_data=json.dumps({
                        "type": "deleted_for_me",
                        "message_id": message_id
                    }))
                    return

                if mode == "everyone":
        # security check (VERY IMPORTANT)
                    if msg.sender_id != user.id:
                        return
    
                    if msg.is_deleted:
                        return
    
                    await sync_to_async(
                            Message.objects.filter(id=message_id).update
                        )(
                        is_deleted=True,
                        content="This message was deleted"
                    )

        # 🔥 broadcast delete to room
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        "type":"message_deleted",
                        "message_id": message_id,
                    }
                )
    
            except Exception as e:
                print("DELETE ERROR:", e)

            return


        if data.get("action") == "edit":
            message_id = data.get("message_id")
            new_text = data.get("message")
            user = self.scope["user"]

            try:
                msg = await sync_to_async(Message.objects.get)(id=message_id)
            except Message.DoesNotExist:
                return
        
            if msg.sender_id != user.id:
                return

            if msg.is_deleted:
                return

            if timezone.now() - msg.timestamp > timedelta(minutes=15):
                return
        
            msg.content = new_text
            msg.is_edited = True
            msg.edited_at = timezone.now()
            await sync_to_async(msg.save)()
        
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "message_edited",
                    "message_id": message_id,
                    "message": new_text,
                    "is_edited": True
                }
            )
            return

        message = data.get("message")

        if not message:
            return

        reply_id = data.get("reply_to")
        reply_message = None
        
        if reply_id:
            try:
                reply_message = await sync_to_async(
                    Message.objects.select_related("sender").get
                )(id=reply_id)
            except Message.DoesNotExist:
                reply_message = None

        msg = await sync_to_async(Message.objects.create)(
            sender=self.scope["user"],
            room=self.room,
            content=message,
            reply_to=reply_message
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
            "message": msg.content,
            "username": msg.sender.username,
            "sender_id": msg.sender.id,
            "message_id": msg.id,  
            "reply_to": {
                "id": reply_message.id,
                "content": reply_message.content,
                "username": reply_message.sender.username
                } if reply_message else None,
            }
        )


    async def group_message(self, event):
        await self.send(text_data=json.dumps(event))

    async def message_deleted(self, event):
        await self.send(text_data=json.dumps({
            "type": "deleted",
            "message_id": event["message_id"]
        }))

    async def message_edited(self, event):
        await self.send(text_data=json.dumps({
            "type": "edited",
            "message_id": event["message_id"],
            "message": event["message"]
        }))
 


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

    async def message_delivered(self, event):
        await self.send(text_data=json.dumps({
            "type": "delivered",
            "message_id": event["message_id"],
            "room_id": event["room_id"]

        }))

    async def message_read(self, event):
        await self.send(text_data=json.dumps({
            "type": "read",
            "message_id": event["message_id"],
            "room_id": event["room_id"]
        }))



    

