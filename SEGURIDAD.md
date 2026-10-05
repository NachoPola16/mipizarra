# Seguridad y despliegue

MiPizarra está pensado para uso personal en una red propia. Si se expone a
Internet, se recomienda esta configuración de defensa en profundidad.

## Arquitectura de la autenticación

```
Internet ──HTTPS──▶ Reverse proxy (auth) ──HTTP──▶ frontend ──HTTP + X-Internal-Secret──▶ api
```

- **Reverse proxy con autenticación** (Basic Auth, SSO, etc.): impide llegar al
  frontend sin credenciales. Configúralo en el proxy que uses (Nginx, Traefik,
  Caddy...).
- **`X-Internal-Secret`**: la API rechaza con `401` cualquier petición sin este
  header, así que nadie puede usarla saltándose el frontend (p. ej. accediendo
  directamente al puerto de la API desde la red local).
- **Rate limiting** por endpoint en la API.

## 1. Generar el secret

```bash
echo "MIPIZARRA_INTERNAL_SECRET=$(openssl rand -hex 32)" >> .env
docker compose up -d api frontend
```

El `.env` está en `.gitignore`. `docker-compose.yml` propaga el valor a la API
y al frontend; el frontend lo añade en cada llamada a la API.

Comprobación:

```bash
# Sin header → 401
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8090/generar \
  -H "Content-Type: application/json" -d '{"objetivo":"test"}'

# Con header correcto → 200 (o 429 si se supera el rate limit)
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8090/generar \
  -H "Content-Type: application/json" \
  -H "X-Internal-Secret: $(grep MIPIZARRA_INTERNAL_SECRET .env | cut -d= -f2)" \
  -d '{"objetivo":"test"}'
```

## 2. Configurar el frontend

En `.env`:

- `DJANGO_SECRET_KEY`: genera un valor propio (no uses el de ejemplo).
- `DJANGO_DEBUG=False` en cualquier despliegue accesible desde fuera.
- `DJANGO_ALLOWED_HOSTS`: tu dominio y los hosts locales que necesites.

## 3. (Opcional) No exponer los puertos a la red local

Por defecto la API y el frontend escuchan en `BIND_IP`. Para que solo el
reverse proxy pueda llegar a ellos, publica los puertos únicamente en
`127.0.0.1` (o pon el proxy en la misma red Docker y no publiques puertos):

```yaml
api:
  ports:
    - "127.0.0.1:8090:8090"
frontend:
  ports:
    - "127.0.0.1:8501:8000"
```

## Rotar el secret

```bash
sed -i "s/MIPIZARRA_INTERNAL_SECRET=.*/MIPIZARRA_INTERNAL_SECRET=$(openssl rand -hex 32)/" .env
docker compose up -d api frontend
```

## Ficheros involucrados

| Fichero | Para qué |
|---|---|
| `api/main.py` (`InternalSecretMiddleware`) | Rechaza con 401 si falta `X-Internal-Secret` |
| `frontend/` | Añade el header en cada llamada a la API |
| `docker-compose.yml` | Propaga el secret desde `.env` a ambos contenedores |
| `.env` (no versionado) | Guarda secretos y configuración local |

> `/docs`, `/openapi.json` y `/redoc` de la API son accesibles sin secret.
> Si no quieres exponer el esquema de la API, aplica el paso 3.
