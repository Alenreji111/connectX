from django.urls import path
from .views import home, signup
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path("", home, name="home"),
    path("signup/", signup, name="signup"),
    path("login/", views.RedirectAuthenticatedLoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("users/", views.user_list, name="user_list"),
    path("private-chat/<int:user_id>/", views.private_chat, name="private_chat"),
    path("group/create/", views.create_group, name="create_group"),
    path("group/<int:room_id>/", views.group_chat, name="group_chat"), 
    path("group/<int:room_id>/audio/", views.upload_group_audio, name="group_audio"),
    path("group/<int:room_id>/media/", views.upload_group_media, name="group_media"),
    path("group/<int:room_id>/avatar/", views.update_group_avatar, name="group_avatar"),
    path("groups/", views.my_groups, name="my_groups"),
    path("search/", views.search_users, name="search_users"),
    path("add-contact/<int:user_id>/", views.add_contact, name="add_contact"),
    path("private-audio/<int:user_id>/", views.upload_private_audio, name="private_audio"),
    path("private-media/<int:user_id>/", views.upload_private_media, name="private_media"),
    path("message-audio/<int:message_id>/", views.message_audio, name="message_audio"),
    path("message-image/<int:message_id>/", views.message_image, name="message_image"),
    path("message-video/<int:message_id>/", views.message_video, name="message_video"),
    path("remove-contact/<int:user_id>/", views.remove_contact, name="remove_contact"),
    path("load-chat/<str:username>/", views.load_private_chat),


]
