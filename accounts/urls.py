from django.urls import path
from . import views

app_name = "accounts"

urlpatterns = [
    path("profile/", views.profile, name="profile"),
    path("block/<str:username>/", views.toggle_block, name="toggle_block"),
    path("profile/<int:user_id>/", views.get_user_profile),

]
