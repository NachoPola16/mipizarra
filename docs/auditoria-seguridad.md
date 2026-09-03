# Auditoría de seguridad — MiPizarra

Auditoría de seguridad con Parrot OS (VM en pve2) / `curl` desde `pve2`,
apuntando al staging (`api` en `192.168.1.74:8090`, `frontend` en
`192.168.1.74:8090:8501`, LXC `docker-host` en pve2), no a producción. Ver
`SEGURIDAD.md` para el diseño de autenticación ya documentado (Basic Auth en
NPM + `X-Internal-Secret` compartido).

**Solo se desplegó `api` y `frontend`, sin `ollama`** (petición explícita:
auditar la superficie web/API, no hacía falta el modelo cargado — tampoco hay
GPU en pve2). Los endpoints que dependen de generación real fallan con 500
genérico cuando se llaman con autenticación correcta, comportamiento esperado
y sin fuga de información (ver hallazgo #4).

## Hallazgos (3 de septiembre de 2026)

| # | Hallazgo | Severidad | Estado |
|---|---|---|---|
| 1 | `InternalSecretMiddleware` funciona correctamente: `/generar` sin `X-Internal-Secret` → 401; con secret incorrecto → 401; con secret correcto → pasa el middleware (500 por falta de Ollama, esperado en este staging). | — | Verificado, correcto |
| 2 | **Sin el secret, cualquier ruta (exista o no) devuelve el mismo 401** — comprobado con `gobuster`, que no pudo distinguir rutas reales de inventadas porque la respuesta es idéntica. Buen comportamiento: no se puede enumerar el API sin autenticación. | — | Verificado, correcto |
| 3 | `PUT`/`DELETE` en `/` → **405**, solo `GET` permitido según `OPTIONS`. | Ninguna | Cerrado |
| 4 | Con secret correcto, `/generar` sin Ollama disponible responde `{"detail":"No se pudo generar la sesión"}` — mensaje genérico, sin traceback ni rutas internas filtradas. | — | Verificado, correcto |
| 5 | `/docs`, `/openapi.json`, `/redoc` son accesibles **sin** `X-Internal-Secret` (están en `PUBLIC_PATHS` a propósito, ver `main.py`). Exponen el esquema completo de la API a quien llegue directo al puerto `8090` sin pasar por NPM. Confirmado con `BIND_IP=192.168.1.72` en producción (no aplicado el "Paso 3" opcional de `SEGURIDAD.md` que cerraría el puerto a solo NPM) que esto es alcanzable desde cualquier dispositivo de la LAN — pero es la misma superficie que el propio `SEGURIDAD.md` ya documenta como aceptada ("si haces dev habitualmente, déjalo abierto a LAN"), no un hallazgo nuevo. | Baja (ya documentado y aceptado) | Sin acción — coincide con la decisión ya tomada |
| 6 | `gobuster` autenticado (con el secret) sobre `api`: solo aparece `/docs`, nada más expuesto del wordlist genérico (los endpoints reales como `/generar`, `/ejercicios` no están en un diccionario de rutas web comunes, es esperado que no aparezcan así). | Ninguna | Cerrado — limpio |
| 7 | `gobuster` sobre `frontend`: `/feedback` y `/pdf` (con barra final por `APPEND_SLASH`) — ambas rutas reales de la app, devuelven 405 a `GET` (solo aceptan `POST`), nada expuesto. | Ninguna | Cerrado — limpio |
| 8 | `nikto` sobre `api`: cabeceras de seguridad tipo navegador (CSP, `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy`) ausentes — esperado en una API JSON pura sin HTML, impacto bajo. El resto de "hallazgos" de Nikto (Tomcat, Exchange, Netware, Active Directory CS...) son ruido: misma causa que en las webs Django — al devolver 401 uniforme para cualquier ruta sin secret, la detección de línea base de Nikto se confunde y marca casi cualquier cosa como "encontrada". | Baja (cabeceras, API sin HTML) | Sin acción — no es HTML servido al navegador |
| 9 | `nikto` sobre `frontend`: mismos falsos positivos ya conocidos (HSTS ausente por HTTP, `X-Content-Type-Options` confirmado presente por `curl`). `csrftoken` sin `HttpOnly` — correcto y esperado (Django necesita que JS lo lea para las cabeceras AJAX). `Access-Control-Allow-Origin: *` solo en `/static/...` (favicon), no en el resto de la web — comportamiento estándar de WhiteNoise para assets estáticos (fuentes/imágenes), sin riesgo. | Ninguna | Cerrado — sin acción |
| 10 | Cabeceras de `GET /` en `frontend` — CSP, `Permissions-Policy`, `X-Content-Type-Options`, `Referrer-Policy` — todas presentes y correctas, mismo nivel que las 3 webs Django/Wagtail. | Ninguna | Verificado, correcto |

## Estado de MiPizarra

**Auditoría de seguridad cerrada, sin hallazgos que requieran cambios.** El
diseño de defensa en profundidad (`X-Internal-Secret` + Basic Auth de NPM +
rate limiting por endpoint) funciona como está documentado en `SEGURIDAD.md`.
