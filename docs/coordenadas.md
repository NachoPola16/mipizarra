# Sistema de coordenadas MiPizarra

**Referencia única** para coordenadas de diagramas. Si cambias algo aquí, también hay que
cambiarlo en los 3 SYSTEM prompts que ven al modelo:

- `experimental/generar_dataset.py` → constante `SYSTEM_DIAGRAMA`
- `api/diagramas.py` → función `generar_coordenadas_ejercicio` (texto del prompt)
- `experimental/exportar_a_ollama.py` → constante `MODELFILE_TEMPLATE` (SYSTEM del Modelfile)

## Convenciones

- Coordenadas normalizadas: `(x, y) ∈ [0, 100]`.
- **X**: 0 = lateral izquierdo, 100 = lateral derecho, 50 = centro.
- **Y** (media pista): 0 = línea de fondo (debajo del aro), 100 = línea de medio campo.
- **Y** (pista completa): 0 = línea de fondo ataque (debajo del aro propio), 100 = línea de fondo defensa
  (debajo del aro rival). 50 = medio campo.
- Las coordenadas se mapean a píxeles en `api/diagram_renderer.py:to_px`.

> **Izquierda/derecha** — los nombres de posición usan la perspectiva del jugador atacante
> mirando al aro desde la cabecera. Su mano derecha es el lado de x bajas (izquierda del papel
> impreso). En el diagrama, las posiciones "derechas" aparecen a la izquierda visual.

## Posiciones canónicas (media pista)

| Posición                    | x  | y   | Notas                                              | Nombre (`pos`)                |
|-----------------------------|-----|-----|----------------------------------------------------|-------------------------------|
| Canasta / aro               | 50 | 11  | Centro del aro                                     | `canasta`                     |
| Línea de fondo centro       | 50 |  5  | Debajo del aro                                     | `linea_de_fondo_centro`       |
| Poste bajo derecho          | 38 | 18  | Junto al borde derecho del área, cerca de la línea de fondo | `poste_bajo_derecho`          |
| Poste bajo izquierdo        | 62 | 18  | Junto al borde izquierdo del área, cerca de la línea de fondo | `poste_bajo_izquierdo`        |
| Esquina triple derecha      |  6 | 22  | Esquina derecha, triple FIBA                       | `esquina_triple_derecha`      |
| Esquina triple izquierda    | 94 | 22  | Esquina izquierda, triple FIBA                     | `esquina_triple_izquierda`    |
| Esquina mini derecha        | 10 | 22  | Esquina derecha, triple minibasket (U8-U12)        | `esquina_mini_derecha`        |
| Esquina mini izquierda      | 90 | 22  | Esquina izquierda, triple minibasket (U8-U12)      | `esquina_mini_izquierda`      |
| Poste alto derecho          | 38 | 36  | Borde derecho del área, altura de la línea TL      | `poste_alto_derecho`          |
| Poste alto izquierdo        | 62 | 36  | Borde izquierdo del área, altura de la línea TL    | `poste_alto_izquierdo`        |
| Codo derecho                | 35 | 41  | Esquina derecha de la línea de tiros libres        | `codo_derecho`                |
| Codo izquierdo              | 65 | 41  | Esquina izquierda de la línea de tiros libres      | `codo_izquierdo`              |
| Línea TL (centro)           | 50 | 41  | Punto de tiro libre                                | `linea_tl_centro`             |
| Media distancia derecha     | 15 | 50  | Entre el codo derecho y el 45° derecho             | `media_distancia_derecha`     |
| Media distancia izquierda   | 85 | 50  | Entre el codo izquierdo y el 45° izquierdo         | `media_distancia_izquierda`   |
| 45° derecho                 | 25 | 50  | A 45° respecto al aro, lado derecho                | `45_derecho`                  |
| 45° izquierdo               | 75 | 50  | A 45° respecto al aro, lado izquierdo              | `45_izquierdo`                |
| Arco de triple (frontal)    | 50 | 60  | Tope superior del arco triple FIBA                 | `arco_triple_frontal`         |
| Cabecera / Frontal          | 50 | 65  | Posición frontal al aro, fuera del triple          | `cabecera`                    |
| Medio campo derecha         | 25 | 95  |                                                    | `medio_campo_derecha`         |
| Medio campo izquierda       | 75 | 95  |                                                    | `medio_campo_izquierda`       |
| Centro medio campo          | 50 | 100 |                                                    | `centro_medio_campo`          |

### Posiciones con nombre en el JSON

Además de `{"x": .., "y": ..}`, cualquier punto del diagrama puede darse por el nombre de la
columna «Nombre» de la tabla anterior. El diccionario vive en un único módulo,
`api/posiciones.py` (`POSICIONES_CANONICAS`), que usan el renderer, el validador y las
plantillas; `tests/test_posiciones.py` comprueba que coincide con esta tabla.

| Dónde            | Con coordenadas                | Con nombre                          |
|------------------|--------------------------------|-------------------------------------|
| Jugador          | `{"id": "A1", "x": 35, "y": 41}` | `{"id": "A1", "pos": "codo_derecho"}` |
| Cono             | `{"x": 94, "y": 22}`           | `{"pos": "esquina_triple_izquierda"}` |
| `a_pos`          | `{"x": 38, "y": 18}`           | `"poste_bajo_derecho"` o `{"pos": "poste_bajo_derecho"}` |

- Si un punto trae a la vez `x`/`y` y `pos`, mandan `x` e `y`.
- El nombre se normaliza: da igual mayúsculas, tildes, espacios o guiones
  (`"Codo derecho"` = `"codo_derecho"`).
- Un nombre que no está en la tabla es un error claro (`posición desconocida '...'`, con
  sugerencias si se parece a uno válido): el validador rechaza el diagrama y el renderer
  lanza `PosicionDesconocida` (un `ValueError`).
- En `pista_completa` el nombre se sitúa en la mitad de ataque: la `y` de la tabla se divide
  entre dos (`codo_derecho` → `(35, 20.5)`, `centro_medio_campo` → `(50, 50)`).

Los prompts del modelo y el JSON Schema que se le pide **no** usan todavía los nombres
(siguen pidiendo `x`/`y`); de momento los nombres sirven para diagramas escritos a mano,
plantillas y para reparar respuestas del modelo (ver «Reparación en el validador»).

## Marcadores solapados

Dos jugadores, o un jugador y un cono, a menos de **8 unidades** se solapan en el dibujo.
`api/solapes.py` (`separar_puntos`) los separa de forma mínima, estable y determinista:

- Los puntos se colocan por orden (atacantes, defensores, conos): los primeros no se mueven y
  el que llega después se aparta hasta la posición válida más cercana (a 8 unidades de todos
  los ya colocados), dentro de la pista y a no más de 8 unidades de donde estaba.
- Dos conos juntos no cuentan como solape.
- Si no hay hueco cerca, el punto se queda donde estaba.
- Las distancias se miden en unidades 0-100, igual en media pista y en pista completa.

El **renderer** aplica esta separación solo al dibujar: el JSON guardado no cambia, y un
diagrama sin solapes se dibuja exactamente igual que antes. Los movimientos de un jugador
desplazado salen de su posición dibujada.

## Reparación en el validador

`_validar_diagrama` (`api/diagramas.py`) arregla en el propio diagrama lo que tiene una
solución determinista antes de rechazarlo, y registra cada arreglo en el log:

1. **`a_pos` que falta** en `desplazamiento`, `bote` o `bloqueo`. Solo se rellena cuando el
   diagrama lo dice sin ambigüedad; nunca se inventan coordenadas:
   - `a` es una posición: `{"x", "y"}` o un nombre de la tabla (`"a": "codo_derecho"`);
     se pasa a `a_pos` y se quita `a`.
   - `bloqueo` con `a` = id de un defensor: `a_pos` es donde está ese defensor en ese momento
     (teniendo en cuenta sus movimientos anteriores).
   - El siguiente movimiento del mismo jugador (por `orden`) dice dónde empieza con el campo
     opcional `desde` (`{"x", "y"}` o nombre): ese punto es el `a_pos`.

   `bote`/`desplazamiento` «hacia» otro jugador (`"a": "A1"`) no dice dónde termina y sigue
   siendo un error (`movimiento 'bote' sin 'a_pos'`), igual que si no hay ninguna pista.
2. **Jugadores a menos de 8 unidades**: se separan con `separar_puntos` (solo jugadores,
   el primero declarado se queda). Si alguno no tiene hueco a 8 unidades o menos, no se toca
   nada y se mantiene el error `demasiado cerca`.

## Carriles

Sistema de referencia para transición, contraataque y repliegue. El campo se divide en franjas
verticales independientemente de la longitud (aplica igual a media pista y pista completa).

### 5 carriles

| Nº | Nombre                    | X centro | Franja X |
|----|---------------------------|----------|----------|
| 1  | Carril lateral derecho    | 10       | 0 – 20   |
| 2  | Carril interior derecho   | 30       | 20 – 40  |
| 3  | Carril central            | 50       | 40 – 60  |
| 4  | Carril interior izquierdo | 70       | 60 – 80  |
| 5  | Carril lateral izquierdo  | 90       | 80 – 100 |

Ocupación típica en contraataque: carril central → reboteador/pívot;
carriles 2 y 4 → jugador con balón; carriles 1 y 5 → tiradores en carrera.

### 3 carriles (versión simplificada)

| Nº | Nombre           | X centro | Franja X |
|----|------------------|----------|----------|
| A  | Banda derecha    | 17       | 0 – 33   |
| B  | Carril central   | 50       | 33 – 67  |
| C  | Banda izquierda  | 83       | 67 – 100 |

### Posiciones de referencia en transición (pista completa, y = 0–100)

En `pista_completa`, y=50 es la línea de medio campo.
Posiciones clave para situar jugadores en cada carril durante la transición:

| Posición                          | x  | y  | Notas                          |
|-----------------------------------|----|----|--------------------------------|
| Línea de fondo lateral derecha    | 10 |  3 | Carril 1, línea de fondo       |
| Línea de fondo interior derecha   | 30 |  3 | Carril 2                       |
| Línea de fondo lateral izquierda  | 90 |  3 | Carril 5                       |
| Línea de fondo interior izquierda | 70 |  3 | Carril 4                       |
| Primer tercio derecho             | 10 | 33 | Carril 1, primer tercio        |
| Primer tercio interior derecho    | 30 | 33 | Carril 2                       |
| Primer tercio central             | 50 | 33 | Carril 3                       |
| Primer tercio interior izquierdo  | 70 | 33 | Carril 4                       |
| Primer tercio izquierdo           | 90 | 33 | Carril 5                       |
| Medio campo lateral derecho       | 10 | 50 | Carril 1, línea de medio campo |
| Medio campo interior derecho      | 30 | 50 | Carril 2                       |
| Medio campo central               | 50 | 50 | Carril 3                       |
| Medio campo interior izquierdo    | 70 | 50 | Carril 4                       |
| Medio campo lateral izquierdo     | 90 | 50 | Carril 5                       |

## Identificadores de jugadores

- Ataque: `A1`–`A5`. Son etiquetas numéricas para identificar jugadores en el diagrama.
  El número **no implica rol de juego**: A1 no tiene por qué ser el base ni A5 el pívot.
  El entrenador asigna a sus jugadores reales a cada etiqueta según el ejercicio.
- Defensa: `D1`–`D5`. Por convención, el número coincide con el atacante al que defienden
  (D1 defiende a A1, etc.), aunque no es obligatorio.
- Conos: sin id, solo `{x, y}`.

## Tipos de movimiento

| Tipo             | Campos obligatorios   | Visual                               | Descripción táctica                             |
|------------------|-----------------------|--------------------------------------|-------------------------------------------------|
| `desplazamiento` | `de`, `a_pos`, `orden`| Línea continua con flecha            | Jugador se mueve sin balón (corte, reposición)  |
| `pase`           | `de`, `a`, `orden`    | Línea punteada con flecha            | Pase entre dos jugadores identificados          |
| `bote`           | `de`, `a_pos`, `orden`| Línea ondulada con flecha            | Jugador avanza botando (penetración, progresión)|
| `tiro`           | `de`, `orden`         | Flecha verde hacia el aro            | Lanzamiento al aro desde la posición actual     |
| `bloqueo`        | `de`, `a_pos`, `orden`| Línea roja fina + barra perpendicular gruesa al final | El bloqueador se mueve hasta el defensor y planta el bloqueo |

`a_pos` admite también una posición con nombre (ver «Posiciones con nombre en el JSON»).
Cualquier movimiento puede llevar el campo opcional `desde` (punto donde empieza); el
renderer no lo dibuja, solo lo usa el validador para deducir el `a_pos` del movimiento
anterior del mismo jugador.

Nota sobre `pase`: el campo `a` es el **id** del jugador receptor (ej. `"a": "A3"`),
no una posición. El jugador emisor no actualiza su posición tras el pase.
`bote` y `desplazamiento` sí actualizan la posición del jugador para los movimientos siguientes.

**Terminología:** usar siempre `bloqueo`, nunca `pantalla` en los outputs.
El modelo puede reconocer "pantalla" en los prompts de entrada, pero en las respuestas
y en el JSON siempre escribe `bloqueo`.

**Restricciones de bloqueo por categoría de edad:**

| Categoría            | Edades (~años) | Bloqueo directo  | Bloqueo indirecto | 1c1 / mano a mano |
|----------------------|----------------|------------------|-------------------|-------------------|
| Prebenjamín/Benjamín | U8, U10        | ✗                | ✗                 | ✓                 |
| Alevín               | U12            | ✗                | ✗                 | ✓                 |
| Infantil             | U14 (~13-14)   | ✗                | ✓                 | ✓                 |
| Cadete en adelante   | U16+ (~15+)    | ✓                | ✓                 | ✓                 |

- **U12 e inferiores**: solo acciones individuales (1c1, mano a mano, bote).
- **U14 (Infantil)**: bloqueos indirectos con normalidad; bloqueo directo solo de forma puntual (según el nivel del equipo o en una jugada concreta), no como contenido central.
- **U16 (Cadete) en adelante**: bloqueo directo e indirecto con plena normalidad.

**Juego de poste bajo**: no es una acción ilegal en categorías de formación (U8-U12),
pero no se recomienda enseñarla — no aporta a esas edades. `vocabulario_tecnico()` en
`sesion.py` ya excluye "poste bajo" y el vocabulario de bloqueos del prompt de
sesión para estas categorías.

## Plantillas de calentamiento y vuelta a la calma

`api/plantillas.py` genera sin modelo diagramas de media pista para las partes de la sesión
que no tienen ficha. `generar_plantilla(nombre, n_jugadores, n_conos=None)` devuelve el JSON de
diagrama de siempre (`x`/`y` numéricos, ids `A1..An` y `D1..Dn`), válido para
`_validar_diagrama` sin reparaciones y sin marcadores solapados.

| Plantilla                 | Momento            | Jugadores | Conos (defecto) |
|---------------------------|--------------------|-----------|-----------------|
| `filas_esquinas`          | calentamiento      | 2-12      | 0-2 (0)         |
| `circuito_conos`          | calentamiento      | 2-12      | 3-10 (6)        |
| `rondo_circular`          | calentamiento      | 4-12      | 0-4 (4)         |
| `cuatro_esquinas`         | calentamiento      | 4-12      | 4 (4)           |
| `dos_filas_enfrentadas`   | calentamiento      | 2-12      | 0-2 (0)         |
| `zigzag_conos`            | calentamiento      | 2-12      | 3-8 (6)         |
| `pilla_pilla`             | calentamiento      | 3-12      | 0-4 (4)         |
| `pases_por_parejas`       | calentamiento      | 2-12      | 0-2 (0)         |
| `rueda_de_tiro`           | calentamiento      | 2-12      | 0-2 (2)         |
| `trote_en_circulo`        | vuelta a la calma  | 2-12      | 0-4 (0)         |
| `estiramientos_en_lineas` | vuelta a la calma  | 2-12      | 0-2 (0)         |
| `tiros_libres_rotacion`   | vuelta a la calma  | 2-12      | 0-2 (0)         |

Un nombre desconocido o un número fuera de rango lanza `ValueError`. En el rondo y el
pilla-pilla los defensores (`D`) son los que roban o pillan. Las plantillas aún no se usan
en la generación de sesiones.

## Campo opcional `curva`

`desplazamiento`, `pase`, `bote` y `tiro` aceptan el campo `"curva"`.
`bloqueo` lo ignora (siempre se dibuja recto).

La línea se dibuja como una curva en lugar de recta:

- `"curva": true` → desvío lateral de ~1 metro (valor por defecto, válido para la mayoría de casos)
- `"curva": 60` → desvío mayor (~1.3 m), para rodear un defensor con más amplitud
- `"curva": 30` → desvío suave (~0.7 m), para una trayectoria ligeramente curvada
- `"curva": -40` → misma curvatura pero al lado contrario

El sentido del desvío es relativo al movimiento: positivo curva hacia la izquierda
del jugador según su dirección de desplazamiento; negativo, hacia su derecha.
Para `bote`, la onda sinusoidal sigue la curva.
