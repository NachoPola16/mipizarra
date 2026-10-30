# Administración de fichas (pestaña «Fichas»)

Pestaña solo para la cuenta administradora (`JUGADAS_ADMIN`, por defecto `nacho`; la misma del botón de la biblioteca de
jugadas). Está en `/fichas/` y enseña la pestaña en la cabecera solo a esa cuenta. Permite revisar las fichas una a una y
cambiar **cualquier campo, diagrama incluido**, sin tocar git ni redesplegar.

## Qué se puede hacer

- Lista con buscador (nombre, id, texto), filtros por edad y categoría y «solo modificadas»; Anterior / Siguiente.
- Todos los campos del [esquema](esquema-ejercicios.md): nombre, categoría, subcategoría, espacio, edades, duración,
  intensidad, carga cognitiva, jugadores mínimos, objetivos, descripción, puntos clave, material, consigna, errores,
  qué observar y progresión.
- Diagrama: sin diagrama (la IA dibuja uno al generar), juego libre, uno o varios (con título). La vista previa la dibuja el
  servidor (la misma que verán en las sesiones); se arrastran jugadores, conos y destinos de movimiento sobre ella, hay
  tablas de jugadores/conos/balón/movimientos y un JSON avanzado.
- **Deshacer / rehacer** mientras se edita (botones o Ctrl+Z / Ctrl+Y, como en las jugadas): cada paso es una foto del
  formulario entero (campos y diagrama); lo que se escribe o arrastra seguido cuenta como un paso. Se reinicia al abrir
  otra ficha o al guardar.
- Guardar (botón o Ctrl+S), descartar cambios y «Volver a la versión guardada anterior» (pide pulsar dos veces).

## Dónde se guardan los cambios

**Directamente en `data/exercises.json`** del servidor (el fichero está montado con permiso de escritura en el contenedor
de la API). Valen enseguida para generar sesiones. El orden de las claves se conserva para que el `git diff` sea limpio.

Red de seguridad **temporal** (`api/fichas_edicion.py`), por si algo sale mal; cuando se vea que no hace falta se apaga con
variables de entorno de la API (`FICHAS_COPIAS_MAX=0` y `FICHAS_HISTORIAL_MAX=0`):

- Antes de cada guardado: copia del `exercises.json` entero en `data/cambios/copias/` (se conservan las últimas
  `FICHAS_COPIAS_MAX`, 20 por defecto).
- La versión anterior de la ficha va a `data/cambios/ficha_historial.json` (hasta `FICHAS_HISTORIAL_MAX`, 10 por ficha);
  de ahí sale «Volver a la versión guardada anterior». Sin historial (0) ese botón deja de funcionar.
- `tools/backup_data.py` incluye `exercises.json` y el historial, porque ahora el fichero del servidor puede ir **por delante
  de git**.

### Traer las ediciones a git (importante al desplegar)

**Despliega siempre con `bash tools/desplegar.sh`**: comprueba si el servidor tiene ediciones de fichas sin subir y, si las
hay, se niega a desplegar e imprime los pasos de abajo; si no, hace el `git pull --ff-only`, reinicia la API y reconstruye
el frontend. (Un `git pull` a pelo sin esa comprobación solo avisa si el fichero cambió en los dos sitios.)

El servidor puede tener `exercises.json` distinto del de git. Antes de desplegar (`git pull` en el servidor) hay que subir
esas ediciones, o el `pull` se negará (si ambos tocaron el fichero) o dejará el fichero del servidor como estaba:

```bash
# 1. ¿hay ediciones sin subir? (en el servidor: cd /root/docker/mipizarra; git status --short data/exercises.json)
# 2. traer el fichero, revisar y subir
ssh proxmox "pct exec 102 -- cat /root/docker/mipizarra/data/exercises.json" > data/exercises.json
git diff --stat data/exercises.json      # revisa qué fichas cambiaron
git add data/exercises.json && git commit -m "fichas: ediciones hechas desde la pestaña Fichas" && git push
# 3. en el servidor: git checkout -- data/exercises.json && git pull --ff-only   (ya es idéntico al commit)
```

Si se editó una ficha en el servidor y esa misma ficha cambió en git, mezcla a mano (`git diff` por ficha).

## Validación

Antes de guardar, la API pasa la ficha por `validar_ficha` (esquema, líneas rojas por edad, nombres e ids repetidos,
límites de duración/intensidad…) y cada diagrama por la validación de diagramas, que además repara lo determinista
(separar jugadores pegados, deducir `a_pos`): lo que se guarda es lo que se dibuja. Si algo falla no se guarda y la
respuesta (422) trae la lista de `problemas`. Guardar sin cambios no escribe nada.

## API (solo con el secreto interno)

| Ruta | Para qué |
|---|---|
| `GET /admin/fichas` | Todas las fichas e ids con versión anterior (`modificadas`) |
| `PUT /admin/fichas/{id}` | `{ficha: {...}}` guarda en exercises.json; 422 con `problemas` si no es válida |
| `DELETE /admin/fichas/{id}` | Vuelve a la versión anterior (404 si no hay) |
| `POST /admin/diagrama/vista` | `{diagrama}` → `{svg, diagrama}` o 422 con `problemas` |

La API no tiene usuarios: el permiso lo comprueba la web (`frontend/pizarra/fichas_admin.py`: 404 en la página y 403 en los
datos para otras cuentas; CSRF obligatorio al guardar) y la API solo acepta llamadas con `X-Internal-Secret`.


## Diagramas por lotes (`tools/diagramas_lote.py`)

Para dibujar o revisar varios diagramas de una vez sin pasar por la web: `listar ej_XXX ...` imprime las fichas, `comprobar PARCHE.json`
valida un parche `{id: {"diagrama": ...}}`, `hoja PARCHE.json HOJA.html` genera una hoja de contactos y `aplicar PARCHE.json` lo escribe en
`data/exercises.json` (con LF, sin tocar el resto). Una ficha no lleva a la vez `diagrama` y `diagramas`; con `diagramas`, cada uno lleva `titulo`.
