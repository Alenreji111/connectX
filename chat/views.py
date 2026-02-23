from django.shortcuts import render, redirect , get_object_or_404
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required
from .models import Room, Message , UserStatus ,Contact , GroupMember
from django.contrib.auth.models import User
from .utils import get_private_room
from django.db.models import Prefetch
from accounts.models import Block


# Create your views here
class StyledUserCreationForm(UserCreationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({
                "class": "w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
            })
def signup(request):
    if request.method == "POST":
        form = StyledUserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("login")
    else:
        form = StyledUserCreationForm()

    return render(request, "signup.html", {"form": form})


def home(request):

    rooms = Room.objects.filter(
        users=request.user
    ).prefetch_related('users__profile').order_by("-last_activity" , "-created_at")

    filtered_rooms = []

    for room in rooms:

        # Always allow groups
        if not room.is_private:
            filtered_rooms.append(room)
            continue

        # find the other user
        other_user = room.users.exclude(id=request.user.id).first()

        # allow ONLY if contact exists
        if Contact.objects.filter(
            owner=request.user,
            contact=other_user
        ).exists():

            room.other_user = other_user
            filtered_rooms.append(room)

    return render(request, "chat/index.html", {
        "rooms": filtered_rooms
    })


def user_list(request):
    contacts = Contact.objects.filter(owner=request.user).select_related("contact")
    user_data = []

    for c in contacts:
        unread = unread_count(request.user, c.contact)
        user_data.append({
            "user": c.contact,
            "unread": unread
        })
    return render(request, "chat/user_list.html", {"user_data":user_data})


def private_chat(request, user_id):
    if request.user.id==user_id:
        return render(request, "chat/error.html", {
          "message": "You cannot start a chat with yourself."
        })

    contacts = Contact.objects.filter(owner=request.user)


    other_user = get_object_or_404(User, id=user_id)
    room = get_private_room(request.user, other_user)

    if room is None:
        return HttpResponseForbidden("Invalid private chat.")

    is_blocked = Block.objects.filter(
        blocker=request.user,
        blocked=other_user
    ).exists()

    messages= Message.objects.filter(room=room).order_by("timestamp")
    status, _ = UserStatus.objects.get_or_create(user=other_user)

    return render(request, "chat/private_chat.html", {
        "room": room,
        "room_name": room.name,
        "other_user": other_user,
        "messages":messages,
        "status":status,
        "contacts": contacts,
        "is_blocked": is_blocked
    })

def create_group(request):
    if request.method == "POST":
        group_name = request.POST.get("group_name")
        member_ids = request.POST.getlist("members")

        room = Room.objects.create(
            name=group_name,
            is_group=True,
            created_by=request.user
        )

        GroupMember.objects.create(
            user=request.user,
            room=room,
            role="creator"
        )

        for user_id in member_ids:
            GroupMember.objects.create(
                user_id=user_id,
                room=room,
                role="member"
            )

        return redirect("home")

    users = User.objects.exclude(id=request.user.id)
    return render(request, "chat/create_group.html", {"users": users})


def group_chat(request, room_id):
    room = get_object_or_404(Room, id=room_id, is_group=True)

    try:
        membership = GroupMember.objects.get(
            room=room,
            user=request.user
        )
    except GroupMember.DoesNotExist:
        return HttpResponseForbidden("Not allowed")

    messages = (
        Message.objects
            .filter(room=room)
            .exclude(deleted_for=request.user)
            .select_related("sender", "reply_to__sender")
            .order_by("timestamp")
    )

    existing_member_ids = GroupMember.objects.filter(
        room=room
    ).values_list("user_id", flat=True)

    available_contacts = request.user.contacts.exclude(
        contact__id__in=existing_member_ids
    )

    return render(request, "chat/group_chat.html", {
        "room": room,
        "messages": messages,
        "user_role": membership.role,
        "available_contacts": available_contacts
    })

def unread_count(user ,other_user):
    room = get_private_room(user , other_user)
    if room is None:
        return 0

    return Message.objects.filter(
        room = room ,
        is_read=False
    ).exclude(sender=user).count()

def my_groups(request):
    groups = Room.objects.filter(
        is_group=True,
        users=request.user
    )

    return render(request, "chat/my_groups.html", {
        "groups": groups
    })

def search_users(request):
    q = request.GET.get("q", "")
    users = User.objects.filter(
        username__icontains=q
    ).exclude(id=request.user.id)

    user_data = []

    for user in users:
        is_added = Contact.objects.filter(
            owner=request.user,
            contact=user
        ).exists()

        user_data.append({
            "user": user,
            "is_added": is_added
        })

    return render(request, "chat/search.html", {
        "user_data": user_data
    })

def add_contact(request, user_id):
    user = get_object_or_404(User, id=user_id)

    Contact.objects.get_or_create(
        owner=request.user,
        contact=user
    )

    return redirect("home")

def load_private_chat(request, username):
    other_user = User.objects.get(username=username)

    messages = (
        Message.objects
            .filter(
                Q(sender=request.user, receiver=other_user) |
                Q(sender=other_user, receiver=request.user)
            )
            .prefetch_related("reactions")   # 🔥 ADD THIS
            .order_by("timestamp")
    )

    return render(request, "chat/private_chat.html", {
        "messages": messages,
        "other_user": other_user
    })