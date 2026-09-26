from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class DashboardAuthenticationTests(TestCase):
    def setUp(self):
        self.password = "test-password-only"
        self.usuario = get_user_model().objects.create_user(
            username="duena",
            email="duena@example.test",
            password=self.password,
        )

    def test_dashboard_redirects_anonymous_users_to_login(self):
        response = self.client.get(reverse("dashboard:index"))

        expected_url = f"{reverse('login')}?next={reverse('dashboard:index')}"
        self.assertRedirects(response, expected_url)

    def test_authenticated_user_can_open_dashboard(self):
        self.client.login(username=self.usuario.username, password=self.password)

        response = self.client.get(reverse("dashboard:index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Bienvenida")

    def test_logout_closes_the_session(self):
        self.client.login(username=self.usuario.username, password=self.password)

        response = self.client.post(reverse("logout"))

        self.assertRedirects(response, reverse("login"))
        dashboard_response = self.client.get(reverse("dashboard:index"))
        self.assertEqual(dashboard_response.status_code, 302)
