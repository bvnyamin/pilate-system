from django.db import IntegrityError, transaction
from django.test import TestCase

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
