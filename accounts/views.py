from django.shortcuts import render, redirect
from .models import Profile , Block
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404


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

    return render(request, "accounts/profile.html", {
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
