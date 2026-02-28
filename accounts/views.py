from django.shortcuts import render, redirect
from .models import Profile , Block
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from chat.models import Contact


@login_required
def profile(request):

    profile = request.user.profile

    if request.method == "POST":

        avatar = request.FILES.get("avatar")

        if avatar:
            profile.avatar = avatar

        profile.bio = request.POST.get("bio", "")

        profile.save()

        return redirect("home")

    template = "accounts/profile.html"
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        template = "accounts/partials/profile_panel.html"
    return render(request, template, {
        "profile": profile
    })

def toggle_block(request, username):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request"}, status=400)

    other_user = get_object_or_404(User, username=username)
    user = request.user

    block, created = Block.objects.get_or_create(
        blocker=user,
        blocked=other_user
    )

    if not created:
        block.delete()
        return JsonResponse({"status": "unblocked"})

    return JsonResponse({"status": "blocked"})

def get_user_profile(request, user_id):
    user = User.objects.get(id=user_id)
    profile = Profile.objects.get(user=user)
    is_contact = False
    if request.user.is_authenticated:
        is_contact = Contact.objects.filter(
            owner=request.user,
            contact=user
        ).exists()

    data = {
        "username": user.username,
        "avatar": profile.avatar.url,
        "bio": profile.bio,
        "last_seen": profile.last_seen,
        "is_contact": is_contact,
    }

    return JsonResponse(data)
