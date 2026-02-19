from django.urls import path
from . import views

app_name = "accounts"

urlpatterns = [
    path("profile/", views.profile, name="profile"),
    path("block/<str:username>/", views.toggle_block, name="toggle_block"),

]
