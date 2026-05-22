# Seguridad — MiPizarra

> Objetivo: que **solo Nacho** pueda acceder a `mipizarra.polacabezon.com` con
> autenticación. Estrategia: Basic Auth en Nginx Proxy Manager + secret compartido
> entre NPM y la API como defensa en profundidad.

## Arquitectura de la auth

```
Internet ──HTTPS──▶ NPM (BasicAuth) ──HTTP + X-Internal-Secret──▶ mipizarra-frontend
                                                                       │
                                                                       ▼ (red Docker)
                                                                  mipizarra-api
                                                       (rechaza si falta X-Internal-Secret)
```

Doble candado:
- **NPM Basic Auth** evita que nadie llegue al frontend sin usuario/contraseña.
- **`X-Internal-Secret`** evita que alguien que se salte NPM (acceso directo al
  puerto `8090` por la LAN, por ejemplo) pueda usar la API.

---

## Paso 1 — Generar el secret y guardarlo en `.env`

En el host del servidor (LXC Proxmox), dentro de `~/docker/mipizarra/`:

```bash
# Generar un secret aleatorio de 64 chars
SECRET=$(openssl rand -hex 32)

# Añadirlo al .env del proyecto (créalo si no existe)
echo "MIPIZARRA_INTERNAL_SECRET=${SECRET}" >> .env

# Verifica que se ha guardado
cat .env | grep MIPIZARRA_INTERNAL_SECRET
```

> El `.env` está ya en tu `.gitignore`, así que el secret NO se sube a git.
> El `docker-compose.yml` lo lee como `${MIPIZARRA_INTERNAL_SECRET:-}`.

Recarga los contenedores para que cojan la nueva env var:

```bash
docker compose up -d api frontend
```

Verifica que la API ya exige el secret:

```bash
# Sin header → 401
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://192.168.1.72:8090/generar \
  -H "Content-Type: application/json" -d '{"objetivo":"test"}'
# → 401

# Con header correcto → 200/429 (según rate limit)
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://192.168.1.72:8090/generar \
  -H "Content-Type: application/json" -H "X-Internal-Secret: ${SECRET}" \
  -d '{"objetivo":"test"}'
# → 200
```

---

## Paso 2 — Configurar Basic Auth en NPM

Entra a NPM: <http://192.168.1.72:81>.

### 2.1 — Crear la Access List

1. Menú lateral → **Access Lists** → **Add Access List**.
2. Pestaña **Details**:
   - Name: `mipizarra-only-nacho`
   - Satisfy: **Any** (basta con que cumpla autenticación O IP allow)
   - Pass Auth to Host: **No** (NPM ya valida, no hace falta reenviar)
3. Pestaña **Authorization**: añade una fila:
   - Username: `nacho` (o el que prefieras)
   - Password: una contraseña fuerte (≥16 chars). Recomendación: usa Vaultwarden.
4. Pestaña **Access** (opcional, allowlist de IPs sin password):
   - Si quieres que tu LAN entre sin password: añade `192.168.1.0/24` con **Allow**.
   - Si NO quieres allowlist y pedir siempre password: déjalo vacío.
5. **Save**.

### 2.2 — Asignar la Access List al proxy host

1. **Hosts** → **Proxy Hosts** → busca `mipizarra.polacabezon.com` → ✏️ Edit.
2. Pestaña **Access List**: selecciona `mipizarra-only-nacho`.
3. Pestaña **Advanced** — pega esto para que NPM añada el secret a cada request
   que reenvía al backend (sustituye `PEGA_AQUI_TU_SECRET` por el valor real
   del `.env`):

   ```nginx
   proxy_set_header X-Internal-Secret "PEGA_AQUI_TU_SECRET";
   ```

   **Nota**: NPM también necesita el secret aquí porque el frontend (Django)
   y el backend (FastAPI) son contenedores separados; cuando NPM proxy
   directamente al backend, debe añadir el header. Si NPM solo proxy al
   frontend (y el frontend internamente llama a la API), el frontend ya
   tiene el secret en su env var y lo añade — pero igualmente conviene
   ponerlo aquí por si en el futuro NPM expone también la API.

4. **Save**.

### 2.3 — Verifica desde fuera

Abre `https://mipizarra.polacabezon.com` en una ventana de incógnito. Debe
salir el cuadro nativo del navegador pidiendo usuario y contraseña. Sin
credenciales no se pasa.

---

## Paso 3 — (Opcional) Cerrar el puerto a LAN

Por defecto la API y el frontend escuchan en `192.168.1.72:8090` y `:8501`.
Eso significa que **cualquier dispositivo de tu LAN** puede llamar
directamente a esos puertos. El secret de NPM ya bloquea los abusos contra
la API, pero el frontend queda accesible.

Si quieres que **solo NPM** pueda acceder (defensa total):

1. Edita `~/docker/mipizarra/docker-compose.yml`:
   ```yaml
   api:
     ports:
       - "127.0.0.1:8090:8090"      # solo localhost
   frontend:
     ports:
       - "127.0.0.1:8501:8000"      # solo localhost
   ```
2. Para que NPM (que corre en contenedor) llegue al host, en NPM Advanced
   del proxy host cambia el destino a `host.docker.internal:8501`.
3. Edita el `docker-compose.yml` de NPM y añade:
   ```yaml
   extra_hosts:
     - "host.docker.internal:host-gateway"
   ```
4. Reinicia ambos:
   ```bash
   docker compose -f ~/docker/nginx-proxy-manager/docker-compose.yml up -d
   docker compose -f ~/docker/mipizarra/docker-compose.yml up -d
   ```

**Trade-off**: pierdes acceso directo desde tu portátil en la LAN a
`http://192.168.1.72:8501` (Streamlit dev). Solo puedes entrar por el
dominio público. Si haces dev habitualmente, déjalo abierto a LAN.

---

## Paso 4 — Comprobaciones finales

```bash
# 1. API directa sin secret → 401
curl -s -o /dev/null -w "API sin secret: %{http_code}\n" \
  -X POST http://192.168.1.72:8090/generar \
  -H "Content-Type: application/json" -d '{"objetivo":"x"}'

# 2. API directa con secret correcto → 200/429
curl -s -o /dev/null -w "API con secret: %{http_code}\n" \
  -X POST http://192.168.1.72:8090/generar \
  -H "Content-Type: application/json" \
  -H "X-Internal-Secret: $(grep MIPIZARRA_INTERNAL_SECRET ~/docker/mipizarra/.env | cut -d= -f2)" \
  -d '{"objetivo":"x"}'

# 3. Dominio público sin auth → 401 Unauthorized de NPM
curl -s -o /dev/null -w "Dominio sin auth: %{http_code}\n" \
  https://mipizarra.polacabezon.com/

# 4. Dominio público con auth → 200
curl -s -o /dev/null -w "Dominio con auth: %{http_code}\n" \
  -u "nacho:TU_PASSWORD" https://mipizarra.polacabezon.com/

# 5. Frontend en LAN sin proxy → 200 si no cerraste el puerto (paso 3 opcional)
curl -s -o /dev/null -w "Frontend LAN directo: %{http_code}\n" \
  http://192.168.1.72:8501/
```

Resultado esperado:
```
API sin secret: 401
API con secret: 200    (o 429 si superas el rate limit)
Dominio sin auth: 401
Dominio con auth: 200
Frontend LAN directo: 200    (si no aplicaste el paso 3 opcional)
```

---

## Rotar el secret

Si crees que se ha filtrado:

```bash
cd ~/docker/mipizarra
NEW_SECRET=$(openssl rand -hex 32)
sed -i "s/MIPIZARRA_INTERNAL_SECRET=.*/MIPIZARRA_INTERNAL_SECRET=${NEW_SECRET}/" .env
docker compose up -d api frontend
echo "Nuevo secret: ${NEW_SECRET}"
# Y actualízalo en NPM → Proxy Host → Advanced → proxy_set_header
```

---

## Resumen de qué archivos están involucrados

| Archivo                                    | Para qué |
|--------------------------------------------|----------|
| `api/main.py` (InternalSecretMiddleware)   | Rechaza con 401 si falta `X-Internal-Secret` |
| `frontend/app.py` (api_headers)            | Añade el header en cada llamada frontend→API |
| `docker-compose.yml`                       | Propaga `INTERNAL_SECRET` desde `.env` a ambos contenedores |
| `.env` (no en git)                         | Guarda el secret en el host |
| NPM panel — Access List                    | Basic Auth para Nacho |
| NPM panel — Proxy Host → Advanced          | Añade `proxy_set_header X-Internal-Secret` |
