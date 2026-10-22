# Aledra Pilates

Aplicación administrativa para un estudio boutique de Pilates, construida como un monolito modular con Django y PostgreSQL.

## Estado

El proyecto se encuentra en su etapa inicial. El material exportado desde Google Stitch se conserva en `stitch_aledra_pilates/` como referencia visual y de experiencia de usuario.

## Configuración

La configuración de Django está separada por entorno:

- `config.settings.development`: desarrollo local.
- `config.settings.production`: despliegues con configuración segura mediante variables de entorno.

## Desarrollo con Docker

1. Copiar `.env.example` como `.env` y reemplazar los valores de ejemplo.
2. Construir e iniciar los servicios:

   ```bash
   docker compose up --build
   ```

3. Abrir `http://localhost:8000/admin/`.

El contenedor de desarrollo aplica las migraciones pendientes antes de iniciar el servidor. Para ejecutar comandos administrativos:

```bash
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py check
```

Para detener los servicios sin eliminar los datos de PostgreSQL:

```bash
docker compose down
```

El servicio PostgreSQL solo está disponible dentro de la red de Docker; no publica su puerto en el host.

## Pagos en cuotas

En **Pagos → Ver cuotas → Programar cuotas**, seleccionar una mensualidad, entre 2 y 12 cuotas y la fecha del primer vencimiento. El sistema divide el saldo pendiente en pesos enteros, agrega el posible resto a la última cuota y programa vencimientos mensuales.

Programar las cuotas no registra ingresos ni reduce el saldo. Cada tarjeta muestra lo recibido, lo pendiente y permite registrar uno o varios abonos para esa cuota. Al completar o anular un abono, los saldos y el número de cuotas pendientes se recalculan. Si la mensualidad tiene un movimiento pendiente anterior, hay que resolverlo o anularlo antes de programar cuotas para evitar duplicar el cobro.

## Aviso de mensualidades pendientes

Desde el día 7 de cada mes, la campana del panel muestra las mensualidades vigentes del período que todavía tienen saldo. La alerta considera pagos confirmados y abonos parciales; no descuenta pagos pendientes o anulados. Para enviar el resumen por correo una vez al mes, configura SMTP y `NOTIFICATION_ADMIN_EMAILS`, y ejecuta `python manage.py enviar_aviso_morosidad` con una tarea programada diaria. En desarrollo, el backend de consola solo escribe el mensaje en los logs.

### Correo y acceso Google

Resend Free puede enviar este resumen agrupado y otros avisos de bajo volumen. En producción configura `EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend`, `EMAIL_HOST=smtp.resend.com`, `EMAIL_PORT=587`, `EMAIL_HOST_USER=resend`, `EMAIL_HOST_PASSWORD` con una API key de Resend y `EMAIL_USE_TLS=True`. El `DEFAULT_FROM_EMAIL` debe usar un dominio verificado en Resend. No guardes claves en Git ni en este archivo.

El acceso Google es opcional y solo se muestra cuando `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` y `GOOGLE_LOGIN_ALLOWED_EMAILS` están configurados. Solo pueden entrar cuentas administrativas (`is_staff`) ya existentes en la base de datos, con correo Google verificado que coincida con la lista permitida; no se crean perfiles al iniciar sesión. En Google Cloud registra `/accounts/google/login/callback/` como URI de redirección autorizada. El login local actual permanece disponible.

En desarrollo local, la URI de redirección es `http://127.0.0.1:8000/accounts/google/login/callback/`. Usa credenciales distintas para desarrollo y producción. Para activar Resend en producción también necesitas acceso DNS al dominio remitente para publicar los registros de verificación que indique Resend.

## Bloques horarios de asistencia

El personal staff puede abrir **Asistencias → Horarios** para cambiar el inicio y término de los bloques matutino y vespertino. Los horarios ofrecidos se generan cada 30 minutos y el término del bloque no se ofrece como hora de inicio. Los bloques deben mantenerse en orden y no superponerse; las sesiones previas no se alteran.

## Producción

El comando predeterminado de la imagen ejecuta Gunicorn. `docker-compose.yml` lo reemplaza por el servidor de desarrollo de Django únicamente para trabajo local.

## Importación de fichas médicas

En **Clientes → Importar fichas médicas**, subir el CSV UTF-8 exportado de Google Forms o Sheets (máximo 2 MB y 2000 respuestas). La importación se revisa antes de asociar las fichas a los perfiles.

- Se compara el correo sin distinguir mayúsculas y el teléfono chileno normalizado. El teléfono de emergencia no participa en la búsqueda.
- Los contactos compartidos, contradictorios o sin coincidencia quedan pendientes. Una asociación manual requiere un motivo.
- Confirmar las asociaciones seleccionadas guarda las fichas. Las pendientes se pueden retomar desde Importaciones recientes.
- Una respuesta idéntica no se importa dos veces. Las respuestas nuevas conservan el historial y la fecha de respuesta determina la ficha vigente.
- Las fichas se consultan en la pestaña **Ficha médica** del perfil. Los usuarios staff tienen acceso; otros usuarios necesitan `clientes.view_fichamedica` para consultar y `clientes.add_fichamedica` para importar. Cada borrador de importación solo es accesible a quien lo subió.

El CSV original no se almacena como archivo público. Las respuestas y las asociaciones quedan en la base de datos. Este flujo no cambia los contactos, el RUT, los pagos o las asistencias de las clientas.

Después de actualizar un entorno ya iniciado, aplicar la migración de clientes:

```bash
docker compose exec web python manage.py migrate
```

## Reportes y gastos del estudio

En **Reportes** se compara por mes lo recaudado con los gastos registrados, con filtro anual, balance simple, asistencias realizadas por clienta y fecha de incorporación más antigua. Los ingresos consideran movimientos pagados y abonos parciales; movimientos pendientes o anulados no cuentan como recaudación. Las asistencias para el ranking consideran Presente y Recuperó.

En **Reportes → Gastos del estudio** se pueden registrar y corregir arriendo, electricidad, agua, gas, internet, aseo e insumos, mantención y otros gastos, con fecha, monto y observaciones. Los gastos no se repiten automáticamente: cada período se registra para conservar trazabilidad. El balance mostrado es informativo (ingresos registrados menos gastos ingresados), no reemplaza contabilidad ni impuestos.

La nueva tabla de gastos se crea con las migraciones estándar:

```bash
docker compose exec web python manage.py migrate
```
