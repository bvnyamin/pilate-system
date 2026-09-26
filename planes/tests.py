from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Plan


class PlanViewsTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="duena",
            email="duena@example.test",
            password="test-password-only",
        )
        self.client.force_login(self.usuario)
        self.plan = Plan.objects.get(nombre="FLUYE")

    def formulario_plan(self, **overrides):
        data = {
            "nombre": "ESENCIAL",
            "clases_por_mes": 6,
            "precio_lista_clp": 58000,
            "descripcion": "Clases para avanzar a tu ritmo.",
            "estado": Plan.Estado.ACTIVO,
        }
        data.update(overrides)
        return data

    def test_all_plan_routes_require_authentication(self):
        self.client.logout()
        routes = [
            reverse("planes:list"),
            reverse("planes:create"),
            reverse("planes:update", kwargs={"pk": self.plan.pk}),
            reverse("planes:set_status", kwargs={"pk": self.plan.pk}),
        ]

        for route in routes:
            with self.subTest(route=route):
                response = self.client.get(route)
                self.assertRedirects(response, f"{reverse('login')}?next={route}")

    def test_list_search_and_status_filter(self):
        response = self.client.get(reverse("planes:list"), {"q": "FLUYE", "estado": "activo"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "$69.000")
        self.assertContains(response, "8 clases mensuales")
        self.assertEqual(response.context["total_planes"], 1)

        inactive_response = self.client.get(reverse("planes:list"), {"estado": "inactivo"})
        self.assertEqual(inactive_response.context["total_planes"], 0)

    def test_create_plan(self):
        response = self.client.post(reverse("planes:create"), self.formulario_plan())

        plan = Plan.objects.get(nombre="ESENCIAL")
        self.assertRedirects(response, reverse("planes:list"))
        self.assertEqual(plan.clases_por_mes, 6)
        self.assertEqual(plan.precio_lista_clp, 58000)

    def test_create_rejects_non_positive_values(self):
        response = self.client.post(
            reverse("planes:create"),
            self.formulario_plan(clases_por_mes=0, precio_lista_clp=0),
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Plan.objects.filter(nombre="ESENCIAL").exists())

    def test_update_plan(self):
        response = self.client.post(
            reverse("planes:update", kwargs={"pk": self.plan.pk}),
            self.formulario_plan(
                nombre="FLUYE",
                clases_por_mes=9,
                precio_lista_clp=75000,
                descripcion="Actualizado",
            ),
        )

        self.plan.refresh_from_db()
        self.assertRedirects(response, reverse("planes:list"))
        self.assertEqual(self.plan.clases_por_mes, 9)
        self.assertEqual(self.plan.precio_lista_clp, 75000)

    def test_status_is_post_only_and_keeps_plan(self):
        route = reverse("planes:set_status", kwargs={"pk": self.plan.pk})

        self.assertEqual(self.client.get(route).status_code, 405)
        response = self.client.post(route, {"estado": Plan.Estado.INACTIVO})

        self.plan.refresh_from_db()
        self.assertRedirects(response, reverse("planes:list"))
        self.assertEqual(self.plan.estado, Plan.Estado.INACTIVO)
        self.assertTrue(Plan.objects.filter(pk=self.plan.pk).exists())

        invalid_response = self.client.post(route, {"estado": "eliminado"})
        self.assertEqual(invalid_response.status_code, 400)
