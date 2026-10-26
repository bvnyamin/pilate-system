/**
 * Puente privado de notificaciones Aledra -> Gmail.
 * Copiar al proyecto Apps Script ya asociado a la hoja de respuestas.
 * Configurar ALEDRA_EMAIL_SECRET y ALEDRA_EMAIL_RECIPIENTS en Propiedades
 * del script antes de publicar como aplicación web.
 */
function doPost(e) {
  try {
    var properties = PropertiesService.getScriptProperties();
    var expectedSecret = properties.getProperty('ALEDRA_EMAIL_SECRET') || '';
    var allowedRecipients = (properties.getProperty('ALEDRA_EMAIL_RECIPIENTS') || '')
      .split(',')
      .map(function (email) { return email.trim().toLowerCase(); })
      .filter(Boolean);

    if (!expectedSecret || allowedRecipients.length === 0) {
      return aledraJson_({ ok: false, error: 'not_configured' });
    }

    var rawBody = e && e.postData && e.postData.contents;
    if (!rawBody || rawBody.length > 50000) {
      return aledraJson_({ ok: false, error: 'invalid_request' });
    }

    var payload = JSON.parse(rawBody);
    if (typeof payload.secret !== 'string' || payload.secret !== expectedSecret) {
      return aledraJson_({ ok: false, error: 'unauthorized' });
    }

    var requestedRecipients = Array.isArray(payload.to) ? payload.to : [payload.to];
    requestedRecipients = requestedRecipients
      .map(function (email) { return String(email || '').trim().toLowerCase(); })
      .filter(Boolean);
    if (
      requestedRecipients.length === 0 ||
      requestedRecipients.some(function (email) { return allowedRecipients.indexOf(email) === -1; })
    ) {
      return aledraJson_({ ok: false, error: 'recipient_not_allowed' });
    }

    var subject = String(payload.subject || '').trim();
    var body = String(payload.body || '');
    var htmlBody = String(payload.htmlBody || '');
    if (!subject || subject.length > 250 || body.length > 15000 || htmlBody.length > 30000) {
      return aledraJson_({ ok: false, error: 'invalid_message' });
    }

    var emailOptions = { name: 'Aledra Pilates' };
    if (htmlBody) emailOptions.htmlBody = htmlBody;
    GmailApp.sendEmail(requestedRecipients.join(','), subject, body, emailOptions);
    return aledraJson_({ ok: true });
  } catch (error) {
    console.error('Aledra email relay failed: ' + error.message);
    return aledraJson_({ ok: false, error: 'send_failed' });
  }
}

function aledraJson_(value) {
  return ContentService.createTextOutput(JSON.stringify(value))
    .setMimeType(ContentService.MimeType.JSON);
}

/** Run once from the editor to authorize Gmail before deploying the web app. */
function autorizarEnvioAledra() {
  GmailApp.getAliases();
}
