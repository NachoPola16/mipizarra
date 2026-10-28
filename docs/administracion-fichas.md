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
- Guardar (botón o Ctrl+S), descartar cambios y «Restaurar la original» (pide pulsar dos veces).

## Dónde se guardan los cambios

`exercises.json` (git) es la base y **no se modifica**. Los cambios van a `data/cambios/ficha_cambios.json` (`{id: campos}`,
volumen propio de la API, fuera de git, en `.gitignore`) y se aplican encima cada vez que se carga la biblioteca
(`api/ficha_cambios.py`, usado por `cargar_ejercicios()` y por `GET /ejercicios`). Valen enseguida para generar sesiones.

- Un cambio sustituye los campos editables de la ficha; el `id` sale siempre de la base. El diagrama solo se sustituye si
  el cambio lo trae (el editor manda siempre `sin_diagrama`).
- **Copia de seguridad:** `tools/backup_data.py` incluye el fichero.
- **Subirlos a git:** copia `ficha_cambios.json` del servidor y ejecuta
  `python tools/aplicar_cambios_fichas.py --cambios ficha_cambios.json [--vaciar]`; revisa `git diff` y haz commit.

## Validación

Antes de guardar, la API pasa la ficha por `validar_ficha` (esquema, líneas rojas por edad, nombres e ids repetidos,
límites de duración/intensidad…) y cada diagrama por la validación de diagramas, que además repara lo determinista
(separar jugadores pegados, deducir `a_pos`): lo que se guarda es lo que se dibuja. Si algo falla no se guarda y la
respuesta (422) trae la lista de `problemas`.

## API (solo con el secreto interno)

| Ruta | Para qué |
|---|---|
| `GET /admin/fichas` | Fichas con los cambios aplicados, ids modificados y originales de las modificadas |
| `PUT /admin/fichas/{id}` | `{ficha: {...}}` guarda los cambios; 422 con `problemas` si no es válida |
| `DELETE /admin/fichas/{id}` | Restaura la original |
| `POST /admin/diagrama/vista` | `{diagrama}` → `{svg, diagrama}` o 422 con `problemas` |

La API no tiene usuarios: el permiso lo comprueba la web (`frontend/pizarra/fichas_admin.py`: 404 en la página y 403 en los
datos para otras cuentas; CSRF obligatorio al guardar) y la API solo acepta llamadas con `X-Internal-Secret`.
