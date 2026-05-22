# Sistema de coordenadas MiPizarra

**Fuente de verdad única** para coordenadas de diagramas. Si cambias algo aquí, también hay que
cambiarlo en los 3 SYSTEM prompts que ven al modelo:

- `tools/generar_dataset.py` → constante `SYSTEM_DIAGRAMA`
- `api/rag_engine.py` → función `generar_coordenadas_ejercicio` (texto del prompt)
- `tools/exportar_a_ollama.py` → constante `MODELFILE_TEMPLATE` (SYSTEM del Modelfile)

## Convenciones

- Coordenadas normalizadas: `(x, y) ∈ [0, 100]`.
- **X**: 0 = lateral izquierdo, 100 = lateral derecho, 50 = centro.
- **Y** (media pista): 0 = baseline (debajo del aro), 100 = línea de medio campo.
- **Y** (pista completa): 0 = baseline ataque (debajo del aro propio), 100 = baseline defensa
  (debajo del aro rival). 50 = medio campo.
- Las coordenadas se mapean a píxeles en `api/diagram_renderer.py:to_px`.

## Posiciones canónicas (media pista)

| Posición                  | x  | y  | Notas                                |
|---------------------------|----|----|--------------------------------------|
| Canasta / aro             | 50 | 11 | Centro del aro                       |
| Baseline centro           | 50 | 5  | Línea de fondo, debajo del aro       |
| Poste bajo derecho        | 38 | 18 | Junto a la zona, lado fuerte         |
| Poste bajo izquierdo      | 62 | 18 |                                      |
| Esquina triple derecha    | 6  | 22 | Esquina inferior derecha, triple FIBA|
| Esquina triple izquierda  | 94 | 22 |                                      |
| Esquina mini derecha      | 10 | 22 | Triple minibasket (U8-U12)           |
| Esquina mini izquierda    | 90 | 22 |                                      |
| Poste alto derecho        | 38 | 36 | Justo dentro de la línea TL          |
| Poste alto izquierdo      | 62 | 36 |                                      |
| Codo TL derecho           | 35 | 41 | Esquina derecha de la línea TL       |
| Codo TL izquierdo         | 65 | 41 |                                      |
| Línea TL (centro)         | 50 | 41 | Donde se tiran los tiros libres      |
| Ala derecha (corta)       | 15 | 50 |                                      |
| Ala izquierda (corta)     | 85 | 50 |                                      |
| 45° derecho               | 25 | 50 | Recepción habitual del alero         |
| 45° izquierdo             | 75 | 50 |                                      |
| Arco de triple (top)      | 50 | 60 | Tope superior del arco triple FIBA   |
| Cabecera triple           | 50 | 65 | Posición típica del base (top key)   |
| Medio campo derecha       | 25 | 95 |                                      |
| Medio campo izquierda     | 75 | 95 |                                      |
| Centro medio campo        | 50 | 100|                                      |

## Convenciones de roles

- Ataque: `A1` base, `A2` escolta/alero, `A3` alero, `A4` ala-pívot, `A5` pívot.
- Defensa: `D1`..`D5` (mismo número que el atacante al que defienden por convención).
- Conos: sin id, solo `{x, y}`.

## Tipos de movimiento

| Tipo               | Campos obligatorios            | Descripción                          |
|--------------------|--------------------------------|--------------------------------------|
| `desplazamiento`   | `de`, `a_pos`, `orden`         | Movimiento sin balón (línea discontinua) |
| `pase`             | `de`, `a` (id), `orden`        | Pase entre jugadores (flecha sólida) |
| `tiro`             | `de`, `orden`                  | Tiro al aro desde la posición actual |
| `bloqueo`          | `de`, `a_pos`, `orden`         | Coloca bloqueo en `a_pos` (línea gruesa roja) |
