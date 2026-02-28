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
    path("groups/", views.my_groups, name="my_groups"),
    path("search/", views.search_users, name="search_users"),
    path("add-contact/<int:user_id>/", views.add_contact, name="add_contact"),
    path("load-chat/<str:username>/", views.load_private_chat),


]
