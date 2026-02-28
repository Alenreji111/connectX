from django.shortcuts import render, redirect , get_object_or_404
from django.http import JsonResponse, HttpResponseForbidden, Http404, FileResponse, HttpResponseBadRequest
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from .models import Room, Message , UserStatus ,Contact , GroupMember
from django.contrib.auth.models import User
from .utils import get_private_room
from django.db.models import Prefetch, Q, OuterRef, Subquery
from django.utils import timezone
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
import mimetypes
from django.urls import reverse
from accounts.models import Block


# Create your views here
class StyledUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("first_name", "last_name", "username", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            placeholder = field.label or ""
            field.widget.attrs.update({
                "class": (
                    "w-full rounded-xl border border-gray-200 bg-white px-4 py-3 "
                    "text-gray-900 placeholder-gray-400 shadow-sm outline-none "
                    "transition focus:border-indigo-400 focus:ring-4 focus:ring-indigo-100"
                ),
                "placeholder": placeholder,
                "autocomplete": (
                    "given-name" if name == "first_name" else
                    "family-name" if name == "last_name" else
                    "username" if name == "username" else
                    "new-password"
                ),
            })

    def save(self, commit=True):
        user = super().save(commit=False)
        user.first_name = self.cleaned_data.get("first_name", "")
        user.last_name = self.cleaned_data.get("last_name", "")
        if commit:
            user.save()
        return user
def signup(request):
    if request.method == "POST":
        form = StyledUserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("login")
    else:
        form = StyledUserCreationForm()

    return render(request, "signup.html", {"form": form})


class StyledAuthenticationForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            placeholder = field.label or ""
            field.widget.attrs.update({
                "class": (
                    "w-full rounded-xl border border-gray-200 bg-white px-4 py-3 "
                    "text-gray-900 placeholder-gray-400 shadow-sm outline-none "
                    "transition focus:border-indigo-400 focus:ring-4 focus:ring-indigo-100"
                ),
                "placeholder": placeholder,
                "autocomplete": "username" if name == "username" else "current-password",
            })


class RedirectAuthenticatedLoginView(LoginView):
    redirect_authenticated_user = True
    form_class = StyledAuthenticationForm


@login_required
def home(request):

    last_message_qs = (
        Message.objects
        .filter(room=OuterRef("pk"))
        .order_by("-timestamp")
        .values("content")[:1]
    )

    rooms = Room.objects.filter(
        users=request.user
    ).prefetch_related('users__profile').annotate(
        last_message=Subquery(last_message_qs)
    ).order_by("-last_activity" , "-created_at")

    filtered_rooms = []

    for room in rooms:

        # Always allow groups
        if not room.is_private:
            filtered_rooms.append(room)
            continue

        # find the other user
        other_user = room.users.exclude(id=request.user.id).first()
        if not other_user:
            continue

        room.other_user = other_user
        filtered_rooms.append(room)

    return render(request, "chat/index.html", {
        "rooms": filtered_rooms
    })

@login_required
def user_list(request):
    contacts = Contact.objects.filter(owner=request.user).select_related("contact")
    user_data = []

    for c in contacts:
        unread = unread_count(request.user, c.contact)
        user_data.append({
            "user": c.contact,
            "unread": unread
        })
    template = "chat/user_list.html"
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        template = "chat/partials/contacts_list.html"
    return render(request, template, {"user_data": user_data})

@login_required
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
    is_contact = Contact.objects.filter(
        owner=request.user,
        contact=other_user
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
        "is_blocked": is_blocked,
        "is_contact": is_contact
    })

@login_required
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

@login_required
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

@login_required
def my_groups(request):
    groups = Room.objects.filter(
        is_group=True,
        users=request.user
    )

    return render(request, "chat/my_groups.html", {
        "groups": groups
    })

@login_required
def search_users(request):
    q = request.GET.get("q", "")
    base_users = User.objects.exclude(id=request.user.id).exclude(
        username__iexact="admin"
    ).exclude(is_superuser=True)

    if q.strip():
        term = q.strip()
        users = base_users.filter(
            Q(username__icontains=term) |
            Q(first_name__icontains=term) |
            Q(last_name__icontains=term) |
            Q(email__icontains=term)
        )
    else:
        contact_ids = Contact.objects.filter(
            owner=request.user
        ).values_list("contact_id", flat=True)
        users = base_users.filter(id__in=contact_ids)

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
    template = "chat/search.html"
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        template = "chat/partials/search_results.html"
    return render(request, template, {
        "user_data": user_data,
        "query": q
    })

@login_required
def add_contact(request, user_id):
    user = get_object_or_404(User, id=user_id)

    Contact.objects.get_or_create(
        owner=request.user,
        contact=user
    )

    get_private_room(request.user, user)

    return redirect("home")

@login_required
def remove_contact(request, user_id):
    if request.method != "POST":
        return redirect("home")

    Contact.objects.filter(
        owner=request.user,
        contact_id=user_id
    ).delete()

    return redirect(request.META.get("HTTP_REFERER", "home"))

@login_required
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

@login_required
def message_audio(request, message_id):
    msg = get_object_or_404(Message, id=message_id)
    if not msg.audio:
        raise Http404("Audio not found")

    is_member = msg.room.users.filter(id=request.user.id).exists()
    if not is_member:
        return HttpResponseForbidden("Not allowed")

    content_type, _ = mimetypes.guess_type(msg.audio.name)
    return FileResponse(msg.audio.open("rb"), content_type=content_type or "application/octet-stream")

@login_required
def upload_private_audio(request, user_id):
    if request.method != "POST":
        return HttpResponseBadRequest("Invalid request")

    audio_file = request.FILES.get("audio")
    if not audio_file:
        return HttpResponseBadRequest("No audio file")

    other_user = get_object_or_404(User, id=user_id)
    room = get_private_room(request.user, other_user)
    if room is None:
        return HttpResponseForbidden("Invalid private chat")

    is_blocked = Block.objects.filter(blocker=other_user, blocked=request.user).exists()
    if is_blocked:
        return HttpResponseForbidden("Blocked")

    msg = Message.objects.create(
        sender=request.user,
        receiver=other_user,
        room=room,
        content="🎤 Audio",
        audio=audio_file,
        is_read=False,
        is_delivered=False
    )

    Room.objects.filter(id=room.id).update(last_activity=timezone.now())

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"room_{room.id}",
        {
            "type": "private_message",
            "message": msg.content,
            "audio_url": request.build_absolute_uri(
                reverse("message_audio", args=[msg.id])
            ),
            "username": request.user.username,
            "message_id": msg.id,
            "reply_to": None,
        }
    )

    for user in room.users.all():
        unread_count = Message.objects.filter(
            room=room,
            is_read=False
        ).exclude(sender=user).count()

        async_to_sync(channel_layer.group_send)(
            f"user_{user.id}",
            {
                "type": "unread_notify",
                "room_id": room.id,
                "count": unread_count
            }
        )
        async_to_sync(channel_layer.group_send)(
            f"user_{user.id}",
            {
                "type": "last_message",
                "room_id": room.id,
                "preview": msg.content
            }
        )

    return JsonResponse({"status": "ok", "message_id": msg.id})

@login_required
def upload_group_audio(request, room_id):
    if request.method != "POST":
        return HttpResponseBadRequest("Invalid request")

    audio_file = request.FILES.get("audio")
    if not audio_file:
        return HttpResponseBadRequest("No audio file")

    room = get_object_or_404(Room, id=room_id, is_group=True)
    is_member = room.users.filter(id=request.user.id).exists()
    if not is_member:
        return HttpResponseForbidden("Not allowed")

    msg = Message.objects.create(
        sender=request.user,
        room=room,
        content="🎤 Audio",
        audio=audio_file
    )

    Room.objects.filter(id=room.id).update(last_activity=timezone.now())

    membership = GroupMember.objects.filter(room=room, user=request.user).first()
    role = membership.role if membership else "member"

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"group_{room.id}",
        {
            "type": "group_message",
            "message": msg.content,
            "audio_url": request.build_absolute_uri(
                reverse("message_audio", args=[msg.id])
            ),
            "username": request.user.username,
            "sender_display": f"{request.user.first_name} {request.user.last_name}".strip() or request.user.username,
            "role": role,
            "sender_id": request.user.id,
            "message_id": msg.id,
            "reply_to": None,
        }
    )

    for user in room.users.all():
        async_to_sync(channel_layer.group_send)(
            f"user_{user.id}",
            {
                "type": "last_message",
                "room_id": room.id,
                "preview": msg.content
            }
        )

    return JsonResponse({"status": "ok", "message_id": msg.id})
