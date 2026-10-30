# Security and deployment

MiPizarra is designed for personal use on a private network. If you expose it to the Internet,
this defense-in-depth setup is recommended.

## Authentication architecture

```
Internet ──HTTPS──▶ Reverse proxy (auth) ──HTTP──▶ frontend ──HTTP + X-Internal-Secret──▶ api
```

- **Reverse proxy with authentication** (Basic Auth, SSO, etc.): prevents reaching the frontend
  without credentials. Configure it in whatever proxy you use (Nginx, Traefik, Caddy...).
- **`X-Internal-Secret`**: the API rejects any request without this header with `401`, so nobody
  can use it by bypassing the frontend (e.g. by hitting the API port directly from the local network).
- **Rate limiting** per endpoint in the API.

## 1. Generate the secret

```bash
echo "MIPIZARRA_INTERNAL_SECRET=$(openssl rand -hex 32)" >> .env
docker compose up -d api frontend
```

`.env` is in `.gitignore`. `docker-compose.yml` passes the value to the API and the frontend; the
frontend adds it to every call to the API.

Check:

```bash
# Without the header → 401
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8090/generar \
  -H "Content-Type: application/json" -d '{"objetivo":"test"}'

# With the right header → 200 (or 429 if the rate limit is exceeded)
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8090/generar \
  -H "Content-Type: application/json" \
  -H "X-Internal-Secret: $(grep MIPIZARRA_INTERNAL_SECRET .env | cut -d= -f2)" \
  -d '{"objetivo":"test"}'
```

## 2. Configure the frontend

In `.env`:

- `DJANGO_SECRET_KEY`: generate your own value (do not use the example one).
- `DJANGO_DEBUG=False` in any deployment reachable from outside.
- `DJANGO_ALLOWED_HOSTS`: your domain and any local hosts you need.

## 3. (Optional) Do not expose the ports to the local network

By default the API and the frontend listen on `BIND_IP`. To let only the reverse proxy reach them,
publish the ports on `127.0.0.1` only (or put the proxy on the same Docker network and publish no ports):

```yaml
api:
  ports:
    - "127.0.0.1:8090:8090"
frontend:
  ports:
    - "127.0.0.1:8501:8000"
```

## Rotating the secret

```bash
sed -i "s/MIPIZARRA_INTERNAL_SECRET=.*/MIPIZARRA_INTERNAL_SECRET=$(openssl rand -hex 32)/" .env
docker compose up -d api frontend
```

## Files involved

| File | Purpose |
|---|---|
| `api/main.py` (`InternalSecretMiddleware`) | Rejects with 401 if `X-Internal-Secret` is missing |
| `frontend/` | Adds the header to every call to the API |
| `docker-compose.yml` | Passes the secret from `.env` to both containers |
| `.env` (not versioned) | Holds secrets and local configuration |

> `/docs`, `/openapi.json` and `/redoc` of the API are reachable without the secret.
> If you do not want to expose the API schema, apply step 3.

## Hardening and other controls

- **Per-account API limits:** the frontend sends `X-Usuario` (the account id) and the API counts the
  `slowapi` limits by it; the header is only trusted when `INTERNAL_SECRET` is active
  (`_clave_de_limite` in `api/main.py`).
- **CSP:** `script-src 'self'` (no `'unsafe-inline'`): no template carries inline JS (a test checks it).
- **Containers:** `api` and `frontend` run with `cap_drop: [ALL]` and `no-new-privileges`;
  `data/frontend` is mode 700 and `db.sqlite3` mode 600 (it holds the hashed passwords).
- **Admin routes:** `/admin/fichas` and `/admin/diagrama/vista` of the API are behind the same
  internal secret; the administrator permission is checked by the web app. See
  [Exercise administration](docs/administracion-fichas.md).
- **Backups:** `tools/backup_data.py` (accounts database, `exercises.json` as edited from the web,
  its history, sessions) with rotation; you need to schedule it (cron) and ship it off the server.
- **Dependencies:** check with `pip-audit` (`pipx run pip-audit -r <requirements>`) when rebuilding the images.

## Reporting a vulnerability

Please do not open a public issue for security problems. Use GitHub's private vulnerability
reporting ("Security" tab → "Report a vulnerability") on this repository.
