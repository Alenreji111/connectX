from .models import Room
from django.contrib.auth.models import User

def get_private_room(user1, user2):
    
    if user1.id==user2.id:
        return none
        
    users = sorted([user1.id, user2.id])
    room_name = f"private_{users[0]}_{users[1]}"

    room, created = Room.objects.get_or_create(
        name=room_name,
        defaults={
            'is_private': True,
            'is_group':False
        
        }
    )

    if created:
        room.users.set([user1, user2])


    # room.users.add(user1, user2)
    return room