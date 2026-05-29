# Sistema de coordenadas MiPizarra

**Fuente de verdad única** para coordenadas de diagramas. Si cambias algo aquí, también hay que
cambiarlo en los 3 SYSTEM prompts que ven al modelo:

- `tools/generar_dataset.py` → constante `SYSTEM_DIAGRAMA`
- `api/rag_engine.py` → función `generar_coordenadas_ejercicio` (texto del prompt)
- `tools/exportar_a_ollama.py` → constante `MODELFILE_TEMPLATE` (SYSTEM del Modelfile)

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

| Posición                    | x  | y   | Notas                                              |
|-----------------------------|-----|-----|----------------------------------------------------|
| Canasta / aro               | 50 | 11  | Centro del aro                                     |
| Línea de fondo centro       | 50 |  5  | Debajo del aro                                     |
| Poste bajo derecho          | 38 | 18  | Junto al borde derecho del área, cerca de la línea de fondo |
| Poste bajo izquierdo        | 62 | 18  | Junto al borde izquierdo del área, cerca de la línea de fondo |
| Esquina triple derecha      |  6 | 22  | Esquina derecha, triple FIBA                       |
| Esquina triple izquierda    | 94 | 22  | Esquina izquierda, triple FIBA                     |
| Esquina mini derecha        | 10 | 22  | Esquina derecha, triple minibasket (U8-U12)        |
| Esquina mini izquierda      | 90 | 22  | Esquina izquierda, triple minibasket (U8-U12)      |
| Poste alto derecho          | 38 | 36  | Borde derecho del área, altura de la línea TL      |
| Poste alto izquierdo        | 62 | 36  | Borde izquierdo del área, altura de la línea TL    |
| Codo derecho                | 35 | 41  | Esquina derecha de la línea de tiros libres        |
| Codo izquierdo              | 65 | 41  | Esquina izquierda de la línea de tiros libres      |
| Línea TL (centro)           | 50 | 41  | Punto de tiro libre                                |
| Media distancia derecha     | 15 | 50  | Entre el codo derecho y el 45° derecho             |
| Media distancia izquierda   | 85 | 50  | Entre el codo izquierdo y el 45° izquierdo         |
| 45° derecho                 | 25 | 50  | A 45° respecto al aro, lado derecho                |
| 45° izquierdo               | 75 | 50  | A 45° respecto al aro, lado izquierdo              |
| Arco de triple (frontal)    | 50 | 60  | Tope superior del arco triple FIBA                 |
| Cabecera / Frontal          | 50 | 65  | Posición frontal al aro, fuera del triple          |
| Medio campo derecha         | 25 | 95  |                                                    |
| Medio campo izquierda       | 75 | 95  |                                                    |
| Centro medio campo          | 50 | 100 |                                                    |

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
carriles 2 y 4 → portador del balón; carriles 1 y 5 → tiradores en carrera.

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
| Infantil             | U14 (~13-14)   | esporádico       | ✓                 | ✓                 |
| Cadete en adelante   | U16+ (~15+)    | ✓                | ✓                 | ✓                 |

- **U12 e inferiores**: solo acciones individuales (1c1, mano a mano, bote).
- **U14 (Infantil)**: bloqueos indirectos con normalidad; bloqueo directo solo de forma esporádica
  y como introducción al concepto, nunca como base del ejercicio.
- **U16 (Cadete) en adelante**: bloqueo directo e indirecto con plena normalidad.

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
