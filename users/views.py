from django.contrib.auth import login, get_user_model
from django.contrib.auth.views import LoginView
from django.http import HttpResponse
from django.urls import reverse, reverse_lazy
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.views.generic import CreateView, RedirectView, TemplateView

from users.forms import UserRegistrationForm
from users.services.emails import send_registration_email
from users.utils.token_generators import TokenGenerator


class UserLoginView(LoginView):
    """
    View for user login.
    """

    def get_default_redirect_url(self):
        """
        Returns the default redirect URL after login.
        """
        return reverse("customer_interface:home")


class UserRegistrationView(CreateView):
    """
    View for user registration.
    """
    template_name = "registration/registration.html"
    form_class = UserRegistrationForm
    success_url = reverse_lazy("customer_interface:home")

    def form_valid(self, form):
        """
        Validates the registration form and saves the new user.

        Args:
            form (UserRegistrationForm): The registration form.

        Returns:
            HttpResponse: The HTTP response.
        """
        self.object = form.save(commit=False)
        self.object.is_active = False
        self.object.save()
        # send email or sms notification
        send_registration_email(
            request=self.request,
            user_instance=self.object
        )
        return super().form_valid(form)


class ActivateUserView(RedirectView):
    """
    View for activating user accounts.
    """
    url = reverse_lazy('customer_interface:home')

    def get(self, request, uuid64, token, *args, **kwargs):
        """
        Activates the user account based on the provided token.

        Args:
            request (HttpRequest): The HTTP request object.
            uuid64 (str): The base64-encoded user ID.
            token (str): The activation token.
            args: Additional positional arguments.
            kwargs: Additional keyword arguments.

        Returns:
            HttpResponse: The HTTP response.
        """
        try:
            pk = force_str(urlsafe_base64_decode(uuid64))
            current_user = get_user_model().objects.get(pk=pk)
        except (get_user_model().DoesNotExist, TypeError, ValueError):
            return HttpResponse("Wrong data")

        if current_user and TokenGenerator().check_token(current_user, token):
            current_user.is_active = True
            current_user.save()

            login(request, current_user, backend='django.contrib.auth.backends.ModelBackend')
            return super().get(request, *args, **kwargs)

        return HttpResponse("Wrong data")
