# Aldra Pilates

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

## Producción

El comando predeterminado de la imagen ejecuta Gunicorn. `docker-compose.yml` lo reemplaza por el servidor de desarrollo de Django únicamente para trabajo local.
