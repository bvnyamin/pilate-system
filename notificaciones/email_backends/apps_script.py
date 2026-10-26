"""Send Django email through an authenticated Google Apps Script web app."""

import json
import logging
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)


class GoogleAppsScriptEmailBackend(BaseEmailBackend):
    """Relay plain-text notifications to Gmail through Apps Script over HTTPS."""

    timeout = 20

    def send_messages(self, email_messages):
        messages = list(email_messages)
        if not messages:
            return 0

        endpoint = settings.GOOGLE_APPS_SCRIPT_EMAIL_URL
        secret = settings.GOOGLE_APPS_SCRIPT_EMAIL_SECRET
        parsed_endpoint = urlsplit(endpoint)
        if (
            not endpoint
            or parsed_endpoint.scheme != "https"
            or parsed_endpoint.hostname != "script.google.com"
            or not parsed_endpoint.path.endswith("/exec")
        ):
            raise ImproperlyConfigured(
                "GOOGLE_APPS_SCRIPT_EMAIL_URL debe ser la URL HTTPS /exec de Apps Script."
            )
        if not secret:
            raise ImproperlyConfigured("Falta GOOGLE_APPS_SCRIPT_EMAIL_SECRET.")

        sent = 0
        for message in messages:
            recipients = message.recipients()
            if not recipients:
                continue

            payload = {
                "secret": secret,
                "to": recipients,
                "subject": message.subject or "",
                "body": message.body or "",
                "htmlBody": next(
                    (
                        content
                        for content, mimetype in (message.alternatives or [])
                        if mimetype == "text/html"
                    ),
                    "",
                ),
            }
            request = Request(
                endpoint,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json; charset=utf-8"},
                method="POST",
            )

            try:
                with urlopen(request, timeout=self.timeout) as response:
                    result = json.loads(response.read().decode("utf-8"))
                if result.get("ok") is not True:
                    raise RuntimeError("Apps Script rechazó el envío del correo.")
            except (
                HTTPError,
                URLError,
                TimeoutError,
                OSError,
                UnicodeDecodeError,
                json.JSONDecodeError,
                RuntimeError,
                AttributeError,
            ):
                logger.exception("No se pudo enviar un correo mediante Google Apps Script.")
                if not self.fail_silently:
                    raise
                continue

            sent += 1

        return sent
