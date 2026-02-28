import json
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from .models import Room, Message , UserStatus , Reaction, GroupMember
from django.utils import timezone
from django.db.models import Count
from django.conf import settings
from datetime import timedelta
from accounts.models import Block


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

        is_blocked = await sync_to_async(
            Block.objects.filter(blocker=receiver, blocked=sender).exists
        )()

        if is_blocked:
            return


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
            self.room.users.all()
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

            await self.channel_layer.group_send(
                f"user_{user.id}",
                {
                    "type": "last_message",
                    "room_id": self.room.id,
                    "preview": msg.content
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
            "audio_url": event.get("audio_url"),
        }))

    # ⭐ MARK AS DELIVERED INSTANTLY
        user = self.scope["user"]

        msg = await sync_to_async(Message.objects.get)(id=event["message_id"])

        if msg.sender_id != user.id:
            # Receiver is currently in this room, so mark read immediately
            await sync_to_async(Message.objects.filter(id=msg.id).update)(
                is_delivered=True,
                is_read=True
            )

            # notify sender: read (blue tick)
            await self.channel_layer.group_send(
                f"user_{msg.sender_id}",
                {
                    "type": "message_read",
                    "message_id": msg.id,
                    "room_id": msg.room_id
                }
            )

            # clear unread badge for receiver
            await self.channel_layer.group_send(
                f"user_{user.id}",
                {
                    "type": "unread_notify",
                    "room_id": msg.room_id,
                    "count": 0
                }
            )
        else:
            # Sender side: nothing to update
            return
        
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
        
        if data.get("action") == "add_member":

            target_id = data.get("user_id")
            user = self.scope["user"]
        
            try:
                membership = await sync_to_async(GroupMember.objects.get)(
                    room=self.room,
                    user=user
                )
            except GroupMember.DoesNotExist:
                return
        
            # Only creator/admin can add
            if membership.role not in ["creator", "admin"]:
                return
        
            # Prevent duplicate
            exists = await sync_to_async(
                GroupMember.objects.filter(
                    room=self.room,
                    user__id=target_id
                ).exists
            )()
        
            if exists:
                return
        
            # Add new member
            await sync_to_async(GroupMember.objects.create)(
                room=self.room,
                user_id=target_id,
                role="member"
            )
        
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "member_added",
                    "user_id": target_id
                }
            )
            return

        if data.get("action") == "change_role":

            target_id = data.get("user_id")
            new_role = data.get("role")
            user = self.scope["user"]
        
            # Get current user's role
            current_member = await sync_to_async(GroupMember.objects.get)(
                room=self.room,
                user=user
            )
        
            # Only creator can demote admin
            if current_member.role not in ["creator", "admin"]:
                return
        
            try:
                target_member = await sync_to_async(GroupMember.objects.get)(
                    room=self.room,
                    user_id=target_id
                )
            except GroupMember.DoesNotExist:
                return
        
            # Creator rules
            if current_member.role == "creator":
                target_member.role = new_role
        
            # Admin rules
            elif current_member.role == "admin":
                if target_member.role == "member" and new_role == "admin":
                    target_member.role = "admin"
                else:
                    return
        
            await sync_to_async(target_member.save)()
        
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "role_updated"
                }
            )
        
            return
        
        if data.get("action") == "remove_member":

            target_id = data.get("user_id")
            user = self.scope["user"]
        
            role = await sync_to_async(GroupMember.objects.get)(
                room=self.room,
                user=user
            )
        
            if role.role not in ["creator", "admin"]:
                return
        
            await sync_to_async(GroupMember.objects.filter(
                room=self.room,
                user_id=target_id
            ).delete)()
        
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "member_removed",
                    "user_id": target_id
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



        member = await sync_to_async(GroupMember.objects.get)(
             room=self.room,
             user=msg.sender
        )


        await self.channel_layer.group_send(
            self.room_group_name,
            {
            "type": "group_message",
            "message": msg.content,
            "username": msg.sender.username,
            "sender_display": f"{msg.sender.first_name} {msg.sender.last_name}".strip() or msg.sender.username,
            "role": member.role,
            "sender_id": msg.sender.id,
            "message_id": msg.id,  
            "reply_to": {
                "id": reply_message.id,
                "content": reply_message.content,
                "username": reply_message.sender.username
                } if reply_message else None,
            }
        )

        group_users = await sync_to_async(list)(
            self.room.users.all()
        )

        for user in group_users:
            await self.channel_layer.group_send(
                f"user_{user.id}",
                {
                    "type": "last_message",
                    "room_id": self.room.id,
                    "preview": msg.content
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

    async def member_added(self, event):
        await self.send(text_data=json.dumps({
            "type": "member_added",
            "user_id": event["user_id"]
        }))

    async def role_updated(self, event):
        await self.send(text_data=json.dumps({
            "type": "role_updated"
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

    async def last_message(self, event):
        await self.send(text_data=json.dumps({
            "type": "last_message",
            "room_id": event["room_id"],
            "preview": event["preview"]
        }))



    
