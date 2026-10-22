from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import HttpResponseForbidden

from allauth.account.adapter import DefaultAccountAdapter
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter


class ClosedAccountAdapter(DefaultAccountAdapter):
    """Do not allow account creation through allauth endpoints."""

    def is_open_for_signup(self, request):
        return False


class AdminGoogleSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Allow Google login only for an existing, active staff account on the allowlist."""

    def is_open_for_signup(self, request, sociallogin):
        return False

    def can_authenticate_by_email(self, login, email):
        if login.account.provider != "google":
            return False

        normalized_email = (email or "").strip().lower()
        if normalized_email not in settings.GOOGLE_LOGIN_ALLOWED_EMAILS:
            return False

        user_model = get_user_model()
        return user_model.objects.filter(
            email__iexact=normalized_email,
            is_active=True,
            is_staff=True,
        ).exists()

    def pre_social_login(self, request, sociallogin):
        if sociallogin.account.provider != "google":
            raise ImmediateHttpResponse(
                HttpResponseForbidden("Este proveedor de acceso no está habilitado.")
            )

        user = sociallogin.user
        email = (user.email or "").strip().lower()
        if (
            email not in settings.GOOGLE_LOGIN_ALLOWED_EMAILS
            or not user.is_active
            or not user.is_staff
        ):
            raise ImmediateHttpResponse(
                HttpResponseForbidden("La cuenta Google no tiene acceso administrativo.")
            )
