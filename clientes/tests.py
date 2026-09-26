from django.core.exceptions import ValidationError
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .admin import ClienteAdmin
from .models import Cliente
from .validators import normalize_rut


class RutChilenoTests(TestCase):
    def test_normalizes_rut_with_points_and_spaces(self):
        self.assertEqual(normalize_rut(" 12.345.678-5 "), "12345678-5")

    def test_accepts_valid_k_check_digit(self):
        self.assertEqual(normalize_rut("76.595.582-3"), "76595582-3")

    def test_rejects_invalid_check_digit(self):
        with self.assertRaises(ValidationError):
            normalize_rut("12.345.678-9")

    def test_rejects_malformed_rut(self):
        with self.assertRaises(ValidationError):
            normalize_rut("12345678")


class ClienteModelTests(TestCase):
    def cliente_data(self, **overrides):
        data = {
            "nombres": "María",
            "apellidos": "Soto",
            "rut": "12.345.678-5",
        }
        data.update(overrides)
        return data

    def test_saves_rut_in_canonical_form(self):
        cliente = Cliente.objects.create(**self.cliente_data())

        self.assertEqual(cliente.rut, "12345678-5")

    def test_rejects_invalid_rut_when_saving_model(self):
        with self.assertRaises(ValidationError) as error:
            Cliente.objects.create(**self.cliente_data(rut="12.345.678-9"))

        self.assertIn("rut", error.exception.message_dict)
        self.assertEqual(Cliente.objects.count(), 0)

    def test_rejects_duplicate_normalized_rut(self):
        Cliente.objects.create(**self.cliente_data())

        with self.assertRaises(ValidationError):
            Cliente.objects.create(
                **self.cliente_data(
                    nombres="Otra",
                    rut="12345678-5",
                )
            )

        self.assertEqual(Cliente.objects.count(), 1)

    def test_defaults_to_active_and_orders_by_name(self):
        cliente = Cliente.objects.create(**self.cliente_data())

        self.assertEqual(cliente.estado, Cliente.Estado.ACTIVA)
        self.assertEqual(str(cliente), "María Soto")

    def test_admin_is_registered_with_search_and_filters(self):
        self.assertIsInstance(admin.site._registry[Cliente], ClienteAdmin)
        self.assertEqual(ClienteAdmin.search_fields, ("nombres", "apellidos", "rut", "email", "telefono"))
        self.assertIn("estado", ClienteAdmin.list_filter)


class ClienteViewsTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="duena",
            email="duena@example.test",
            password="test-password-only",
        )
        self.client.force_login(self.usuario)

    def crear_cliente(self, **overrides):
        data = {
            "nombres": "María",
            "apellidos": "Soto",
            "rut": "12.345.678-5",
        }
        data.update(overrides)
        return Cliente.objects.create(**data)

    def formulario_cliente(self, **overrides):
        data = {
            "nombres": "María",
            "apellidos": "Soto",
            "rut": "12.345.678-5",
            "fecha_incorporacion": timezone.localdate().isoformat(),
            "estado": Cliente.Estado.ACTIVA,
        }
        data.update(overrides)
        return data

    def test_all_client_routes_require_authentication(self):
        cliente = self.crear_cliente()
        self.client.logout()
        routes = [
            reverse("clientes:list"),
            reverse("clientes:create"),
            reverse("clientes:detail", kwargs={"pk": cliente.pk}),
            reverse("clientes:update", kwargs={"pk": cliente.pk}),
            reverse("clientes:set_status", kwargs={"pk": cliente.pk}),
        ]

        for route in routes:
            with self.subTest(route=route):
                self.assertRedirects(
                    self.client.get(route),
                    f"{reverse('login')}?next={route}",
                )

    def test_list_search_and_status_filter(self):
        active = self.crear_cliente()
        self.crear_cliente(
            nombres="Carolina",
            apellidos="Pérez",
            rut="9.876.543-3",
            estado=Cliente.Estado.INACTIVA,
        )

        response = self.client.get(reverse("clientes:list"), {"q": "María", "estado": "activa"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, str(active))
        self.assertNotContains(response, "Carolina")
        self.assertEqual(response.context["total_clientes"], 1)

        rut_response = self.client.get(reverse("clientes:list"), {"q": "12.345.678-5"})
        self.assertContains(rut_response, "María")

    def test_create_client_normalizes_rut(self):
        response = self.client.post(reverse("clientes:create"), self.formulario_cliente())

        cliente = Cliente.objects.get()
        self.assertRedirects(response, reverse("clientes:detail", kwargs={"pk": cliente.pk}))
        self.assertEqual(cliente.rut, "12345678-5")

    def test_create_rejects_invalid_rut(self):
        response = self.client.post(
            reverse("clientes:create"),
            self.formulario_cliente(rut="12.345.678-9"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "dígito verificador")
        self.assertEqual(Cliente.objects.count(), 0)

    def test_edit_updates_existing_client(self):
        cliente = self.crear_cliente()
        response = self.client.post(
            reverse("clientes:update", kwargs={"pk": cliente.pk}),
            self.formulario_cliente(telefono="+56 9 1234 5678", email="maria@example.test"),
        )

        cliente.refresh_from_db()
        self.assertRedirects(response, reverse("clientes:detail", kwargs={"pk": cliente.pk}))
        self.assertEqual(cliente.telefono, "+56 9 1234 5678")
        self.assertEqual(cliente.email, "maria@example.test")

    def test_detail_shows_profile_and_future_sections_as_unavailable(self):
        cliente = self.crear_cliente()

        response = self.client.get(reverse("clientes:detail", kwargs={"pk": cliente.pk}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Información personal")
        self.assertContains(response, "Disponible al implementar mensualidades")

    def test_status_change_is_post_only_and_preserves_record(self):
        cliente = self.crear_cliente()
        route = reverse("clientes:set_status", kwargs={"pk": cliente.pk})

        self.assertEqual(self.client.get(route).status_code, 405)
        response = self.client.post(route, {"estado": Cliente.Estado.INACTIVA})

        cliente.refresh_from_db()
        self.assertRedirects(response, reverse("clientes:detail", kwargs={"pk": cliente.pk}))
        self.assertEqual(cliente.estado, Cliente.Estado.INACTIVA)
        self.assertEqual(Cliente.objects.count(), 1)

        invalid_response = self.client.post(route, {"estado": "eliminada"})
        self.assertEqual(invalid_response.status_code, 400)
        self.assertEqual(Cliente.objects.count(), 1)
