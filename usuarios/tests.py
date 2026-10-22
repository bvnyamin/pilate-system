from types import SimpleNamespace

from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse

from .adapters import AdminGoogleSocialAccountAdapter, ClosedAccountAdapter

from .models import Usuario


class UsuarioModelTests(TestCase):
    def test_superuser_has_administrative_permissions(self):
        usuario = Usuario.objects.create_superuser(
            username="administradora",
            email="admin@example.test",
            password="test-password-only",
        )

        self.assertTrue(usuario.is_staff)
        self.assertTrue(usuario.is_superuser)
        self.assertTrue(usuario.is_active)

    def test_email_must_be_unique(self):
        Usuario.objects.create_user(
            username="primera",
            email="duena@example.test",
            password="test-password-only",
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            Usuario.objects.create_user(
                username="segunda",
                email="duena@example.test",
                password="test-password-only",
            )


class GoogleLoginPolicyTests(TestCase):
    @override_settings(GOOGLE_LOGIN_ALLOWED_EMAILS=["admin@example.test"])
    def test_only_allowlisted_existing_staff_user_can_authenticate_by_email(self):
        Usuario.objects.create_user(
            username="administradora",
            email="admin@example.test",
            password="test-password-only",
            is_staff=True,
        )
        adapter = AdminGoogleSocialAccountAdapter()
        login = SimpleNamespace(account=SimpleNamespace(provider="google"))

        self.assertTrue(adapter.can_authenticate_by_email(login, "ADMIN@example.test"))
        self.assertFalse(adapter.can_authenticate_by_email(login, "other@example.test"))

    @override_settings(GOOGLE_LOGIN_ALLOWED_EMAILS=["admin@example.test"])
    def test_non_staff_or_inactive_local_accounts_cannot_use_google_login(self):
        Usuario.objects.create_user(
            username="clienta",
            email="admin@example.test",
            password="test-password-only",
            is_staff=False,
        )
        adapter = AdminGoogleSocialAccountAdapter()
        login = SimpleNamespace(account=SimpleNamespace(provider="google"))

        self.assertFalse(adapter.can_authenticate_by_email(login, "admin@example.test"))

    def test_signups_are_closed(self):
        self.assertFalse(ClosedAccountAdapter().is_open_for_signup(None))
        self.assertFalse(
            AdminGoogleSocialAccountAdapter().is_open_for_signup(None, None)
        )

    @override_settings(
        GOOGLE_LOGIN_ENABLED=True,
        SOCIALACCOUNT_PROVIDERS={
            "google": {
                "APPS": [{"client_id": "test-client", "secret": "test-secret", "key": ""}],
                "EMAIL_AUTHENTICATION": True,
                "VERIFIED_EMAIL": True,
            }
        },
    )
    def test_login_page_offers_google_when_credentials_are_configured(self):
        response = self.client.get(reverse("login"))

        self.assertContains(response, "Continuar con Google")
        self.assertContains(response, "/accounts/google/login/")

    @override_settings(GOOGLE_LOGIN_ENABLED=False)
    def test_login_page_hides_google_when_credentials_are_missing(self):
        response = self.client.get(reverse("login"))

        self.assertNotContains(response, "Continuar con Google")
