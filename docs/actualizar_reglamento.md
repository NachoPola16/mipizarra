# Cómo actualizar el reglamento

El reglamento llega a la IA por dos vías que se complementan:

| Capa | Dónde | En el repositorio | Para qué sirve |
|---|---|---|---|
| **Resúmenes `.md`** | `data/reglamento/<ámbito>/*.md` | Sí | Texto breve y curado: es lo que el modelo lee primero (colección `reglamento_md`). |
| **Documentos oficiales en PDF** | `data/pdfs/coleccion_reglamento/` | No (carpeta local, ignorada por git) | Capa opcional con el detalle largo (colección `reglamento`). |

La IA funciona solo con los `.md`. Los PDF añaden precisión pero no son necesarios, y no se publican.

## Ámbitos: general o una comunidad autónoma

El modo reglamento tiene un selector de **ámbito**:

- **General** (`data/reglamento/general/`): reglas de FIBA y de la federación española. Se usa siempre.
- **Una comunidad autónoma** (`data/reglamento/<comunidad>/`, por ejemplo `aragon`): su normativa
  (competiciones escolares, bases de competición…). Al elegirla, la IA responde con la normativa de esa
  comunidad **y la completa con la general**. Si ambas difieren, prevalece la de la comunidad.

El selector se genera solo a partir de las carpetas: **añadir una comunidad es crear su carpeta** con al menos
un `.md`. El nombre que se muestra se toma de `NOMBRES_AMBITO` en `api/config.py` (por ejemplo,
`"aragon": "Aragón"`); si no está, se deriva del nombre de la carpeta.

Para los PDF locales se sigue la misma convención: los PDF sueltos en `data/pdfs/coleccion_reglamento/` son
generales, y los de una comunidad van en una subcarpeta con su nombre (`.../coleccion_reglamento/aragon/`).

### Añadir una comunidad autónoma

1. Crea `data/reglamento/<comunidad>/` (en minúsculas, sin tildes ni espacios: `castilla_y_leon`).
2. Escribe en ella uno o varios `.md` con su normativa, en lenguaje propio. Indica siempre en el texto qué
   temporada recoge y recuerda que la normativa se actualiza cada año.
3. (Opcional) Añade el nombre con tilde a `NOMBRES_AMBITO` y los PDF locales a su subcarpeta.
4. Reindexa y reinicia (ver más abajo). La comunidad aparece sola en el selector.

## Pasos cuando sale una versión nueva de las reglas

1. **Descarga el documento oficial** (la federación internacional publica cada año, en verano, el reglamento
   completo y un resumen de cambios, válidos desde el 1 de octubre; las federaciones autonómicas publican las
   bases de cada temporada) y déjalo en `data/pdfs/coleccion_reglamento/` (o en la subcarpeta de la
   comunidad). Si el PDF viene protegido contra copia, instala `cryptography` en el entorno virtual del
   proyecto para poder leerlo.
2. **Escribe o actualiza el resumen en `data/reglamento/<ámbito>/`:** un fichero con los cambios en lenguaje
   propio, indicando desde cuándo rigen. Corrige después las normas clave donde algo haya quedado obsoleto.
3. **Actualiza el prompt** de `/reglamento` en `api/prompts.py` solo si el cambio es grande (por ejemplo, una
   falta que desaparece): el modelo pequeño tiende a repetir la regla antigua si ve ambas.
4. **Retira o aparta los PDF antiguos** que contradigan la regla nueva, para que no se recuperen en las
   búsquedas.
5. **Reindexa:** `docker exec mipizarra-api python /app/tools/indexar_colecciones.py` y reinicia la API.
6. **Protege el cambio con un test:** añade una pregunta a `CASOS_REGLAMENTO` en `tools/regresion.py` (con
   `"ambito"` si es de una comunidad) y ajusta los recuentos en `tests/test_regresion_arnes.py`.

## Qué mantener y qué no

- Mantén en el repositorio solo resúmenes propios. No copies párrafos literales del reglamento oficial.
- Los PDF son locales: si no los tienes, la IA sigue funcionando con los `.md`.
- Fecha de vigencia siempre explícita en el texto, para que el modelo distinga entre la regla actual y la anterior.
