# Cómo actualizar el reglamento

El reglamento llega a la IA por dos vías que se complementan:

| Capa | Dónde | En el repositorio | Para qué sirve |
|---|---|---|---|
| **Resúmenes `.md`** | `data/teoria/reglamento_*.md` | Sí | Texto breve y curado: lo que el modelo lee primero (colección `teoria_md`, prioritaria). |
| **Documentos oficiales en PDF** | `data/pdfs/coleccion_reglamento/` | No (carpeta local, ignorada por git) | Capa opcional con el detalle largo (colección `reglamento`), útil para normativa muy específica. |

La IA funciona solo con los `.md`. Los PDF añaden precisión pero no son necesarios, y no se publican.

## Pasos cuando sale una versión nueva de las reglas

1. **Descarga el documento oficial** (la federación internacional publica cada año, en verano, el reglamento
   completo y un resumen de cambios, válidos desde el 1 de octubre) y déjalo en
   `data/pdfs/coleccion_reglamento/`. Si el PDF viene protegido contra copia, instala `cryptography` en el
   entorno virtual del proyecto para poder leerlo.
2. **Escribe o actualiza el resumen en `data/teoria/`:** un fichero `reglamento_fiba_cambios_AAAA.md` con los
   cambios en lenguaje propio, indicando desde cuándo rigen y recordando que las competiciones de formación
   adoptan los cambios según su calendario. Corrige después las normas clave
   (`reglamento_fiba_normas_clave.md`) donde algo haya quedado obsoleto.
3. **Actualiza el prompt** de `/reglamento` en `api/prompts.py` solo si el cambio es grande (por ejemplo, una
   falta que desaparece): el modelo pequeño tiende a repetir la regla antigua si ve ambas.
4. **Retira o aparta los PDF antiguos** que contradigan la regla nueva, para que no se recuperen en las
   búsquedas.
5. **Reindexa:** `docker exec mipizarra-api python /app/tools/indexar_colecciones.py`.
6. **Protege el cambio con un test:** añade una pregunta a `CASOS_REGLAMENTO` en `tools/regresion.py` (y
   ajusta los recuentos en `tests/test_regresion_arnes.py`) y lanza el arnés en vivo.

## Qué mantener y qué no

- Mantén en el repositorio solo resúmenes propios. No copies párrafos literales del reglamento oficial.
- Los PDF son locales: si no los tienes, la IA sigue funcionando con los `.md`.
- Fecha de vigencia siempre explícita en el texto, para que el modelo distinga entre la regla actual y la anterior.
