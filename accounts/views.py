from django.shortcuts import render, redirect
from .models import Profile
from django.contrib.auth.decorators import login_required


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
