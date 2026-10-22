/**
 * Install this as a spreadsheet "On form submit" trigger.
 * Store ALEDRA_WEBHOOK_URL and ALEDRA_WEBHOOK_SECRET in Script Properties.
 */
function aledraMedicalFormSubmitted(e) {
  if (!e || !e.range || !e.values) {
    throw new Error("Este manejador debe ejecutarse con el activador de envío del formulario.");
  }

  const properties = PropertiesService.getScriptProperties();
  const endpoint = properties.getProperty("ALEDRA_WEBHOOK_URL");
  const secret = properties.getProperty("ALEDRA_WEBHOOK_SECRET");
  if (!endpoint || !secret) {
    throw new Error("Configura ALEDRA_WEBHOOK_URL y ALEDRA_WEBHOOK_SECRET en Propiedades del script.");
  }

  const sheet = e.range.getSheet();
  const headers = sheet.getRange(1, 1, 1, e.values.length).getDisplayValues()[0];
  const values = e.values.map(value => String(value == null ? "" : value));
  const timestamp = sheet.getRange(e.range.getRow(), 1).getValue();
  if (timestamp instanceof Date && !isNaN(timestamp.getTime())) {
    values[0] = timestamp.toISOString();
  }

  const response = UrlFetchApp.fetch(endpoint, {
    method: "post",
    contentType: "application/json",
    headers: { "X-Aledra-Forms-Secret": secret },
    payload: JSON.stringify({ headers: headers, values: values }),
    muteHttpExceptions: true
  });
  const status = response.getResponseCode();
  if (status < 200 || status >= 300) {
    // Do not log the form answers; they may contain sensitive health information.
    throw new Error("Aledra no aceptó la respuesta (HTTP " + status + "). Revisa la configuración del webhook.");
  }
}
