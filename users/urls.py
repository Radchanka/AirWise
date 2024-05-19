from django.contrib.auth.views import LogoutView
from django.urls import path
from users.views import UserLoginView, UserRegistrationView, ActivateUserView

app_name = "users"

urlpatterns = [
    path("login/", UserLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(next_page='/'), name='logout'),
    path("registration/", UserRegistrationView.as_view(), name="registration"),
    path("activate/<str:uuid64>/<str:token>/", ActivateUserView.as_view(), name="activate"),
]
