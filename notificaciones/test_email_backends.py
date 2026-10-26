import json
from unittest.mock import MagicMock, patch

from django.core.mail import EmailMultiAlternatives
from django.test import SimpleTestCase, override_settings

from .email_backends.apps_script import GoogleAppsScriptEmailBackend


class GoogleAppsScriptEmailBackendTests(SimpleTestCase):
    @override_settings(
        GOOGLE_APPS_SCRIPT_EMAIL_URL="https://script.google.com/macros/s/test/exec",
        GOOGLE_APPS_SCRIPT_EMAIL_SECRET="test-secret",
    )
    @patch("notificaciones.email_backends.apps_script.urlopen")
    def test_relay_sends_text_and_branded_html_alternative(self, urlopen):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b'{"ok":true}'
        urlopen.return_value = response
        message = EmailMultiAlternatives(
            subject="Aledra Pilates: prueba",
            body="Versión de texto",
            from_email="Aledra <avisos@example.test>",
            to=["admin@example.test"],
        )
        message.attach_alternative("<h1>Correo bonito</h1>", "text/html")

        sent = GoogleAppsScriptEmailBackend().send_messages([message])

        payload = json.loads(urlopen.call_args.args[0].data.decode("utf-8"))
        self.assertEqual(sent, 1)
        self.assertEqual(payload["body"], "Versión de texto")
        self.assertEqual(payload["htmlBody"], "<h1>Correo bonito</h1>")
