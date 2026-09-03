# Auditoría de diseño/UX — MiPizarra (skill impeccable)

**Fecha:** 2026-09-03
**Entorno auditado:** staging `http://192.168.1.74:8501` (sin login, sin modelo LLM cargado detrás — la generación real vía `/generar/` no se evaluó porque no completa en este staging; eso es esperado, no un hallazgo)
**Alcance:** pantalla principal (`/`, modo "Sesión"), modo "Reglamento" (pestaña dentro de la misma página — no es una ruta GET independiente pese al nombre de la URL `/reglamento/`, que es un endpoint `@require_POST` para la API), `/privacidad/`, `/aviso-legal/`.
**Código revisado:** `mipizarra/frontend/pizarra/templates/pizarra/index.html`, `privacidad.html`, `aviso_legal.html`, `pizarra/urls.py`, `pizarra/views.py`, `pizarra/static/pizarra/css/fonts.css`.

**Nota de contexto:** el proyecto no tiene `PRODUCT.md` ni `DESIGN.md` (el loader de contexto del skill confirma `hasProduct: false`, `hasDesign: false`). Se auditó igualmente usando el contexto de `CLAUDE.md`/`README.md` del proyecto (asistente de IA local para entrenadores de baloncesto, uso personal, no comercial) y tratando la pantalla principal como **registro "producto"** (herramienta de tarea: rellenar un formulario y obtener una sesión), no como superficie de marca. Si se quiere una auditoría con mayor precisión de intención de marca, vale la pena correr `/impeccable teach` en una sesión aparte.

---

## Audit Health Score

| # | Dimensión | Antes | Después | Hallazgo clave |
|---|-----------|:-:|:-:|---|
| 1 | Accesibilidad (A11y) | 2 | 3 | Contraste roto en el CTA principal (2.99:1) + página sin ningún `<h1>`/jerarquía de encabezados |
| 2 | Performance | 3 | 3 | Fuentes propias con `font-display:swap`, sin animaciones de layout — bien de partida |
| 3 | Responsive | 3 | 3 | Objetivos táctiles (`mode-tab`, `chip`, `dd-btn`) por debajo de 44px — abierto, no tocado |
| 4 | Theming | 2 | 4 | Paleta de tokens duplicada íntegra en 3 plantillas — centralizada en `theme.css` |
| 5 | Anti-Patterns | 2 | 4 | 3 usos del patrón prohibido "side-stripe border" — eliminados los 3 |
| **Total** | | **12/20** | **17/20** | **Acceptable → Good** |

---

## Veredicto anti-patrones (empezar por aquí)

**No, esto no tiene pinta de "hecho por IA sin criterio".** Es un trabajo de UI cuidado: paleta cálida oscura consistente (nada de `#000`/`#fff` puro en fondo/texto — solo se colaba en el texto de dos botones, corregido), un `<select>` nativo sustituido por un combobox accesible con roles ARIA y navegación por teclado completa (`role="listbox"`, `aria-expanded`, flechas/Enter/Escape), estados de error en línea sin `alert()` bloqueante, `prefers-reduced-motion` respetado. Eso ya descarta la mayoría de los tells típicos de IA (glassmorphism, gradientes de texto, grid de tarjetas genérico, iconos de stock).

Lo que sí apareció, y de forma repetida, es el patrón **"side-stripe border"** (`border-left: 3px solid var(--accent)` como único recurso para señalar "esto es importante"): en el título de cada ejercicio generado, en el cuadro de aviso de `privacidad.html`, y en el cuadro de error del formulario. Es una firma visual reconocible de plantillas genéricas y estaba, además, prohibida explícitamente por las reglas del skill. Se sustituyó en los 3 sitios (ver detalle abajo).

---

## Resumen ejecutivo

- **Puntuación inicial: 12/20 (Acceptable)** → **final: 17/20 (Good)**
- Hallazgos: 1 P1 (contraste), 3 P2 (side-stripe ×3, tratados como un único patrón sistémico), 1 P2 (falta de jerarquía de encabezados), 1 P2 (duplicación de CSS), 1 P3 (objetivos táctiles pequeños, abierto)
- Los 3 primeros tipos de hallazgo (contraste, side-stripe, encabezados) y la duplicación de CSS ya están corregidos en el código.
- Queda abierto: tamaño de objetivos táctiles en móvil — requiere iteración visual en vivo, no se tocó a ciegas (ver "Qué queda abierto").

---

## Hallazgos detallados

### [P1] Contraste insuficiente en el botón de acción principal — CORREGIDO
- **Ubicación:** `index.html`, clases `.btn-send` (línea ~93 tras el cambio) y `.mode-tab.active` (línea ~53) — texto blanco (`#fff`) sobre `var(--accent)` (`#e8752c`)
- **Categoría:** Accesibilidad
- **Impacto:** el botón "⚡ Generar sesión" / "🔍 Consultar" / "Aplicar cambio" — la acción principal de toda la interfaz — y la pestaña activa del selector de modo tenían **2.99:1** de contraste (calculado con la fórmula de luminancia relativa de WCAG). El texto es `.88rem`/`.82rem` con `font-weight:600`, por debajo del umbral de "texto grande" que permitiría relajar el requisito a 3:1, así que aplica el mínimo de **4.5:1** para AA. Falla claramente. Es el mismo patrón de bug encontrado en la auditoría de `web-nacho` (allí era 1.97:1), aunque aquí menos severo.
- **WCAG:** 1.4.3 Contrast (Minimum), nivel AA
- **Arreglo aplicado:** el texto de ambos componentes pasa de `#fff` a `var(--bg)` (el mismo negro cálido del fondo de la app), manteniendo el naranja de fondo. Contraste resultante: **6.23:1** en reposo, **4.55:1** en hover (antes 4.11:1 con blanco — también mejora). Cambio de una sola propiedad en 3 reglas CSS, sin tocar el layout ni el resto de la paleta.

### [P2] Patrón "side-stripe border" repetido 3 veces — CORREGIDO
- **Ubicación:**
  - `index.html`, `.ejercicio-title` (título de cada ejercicio dentro de una sesión generada)
  - `index.html`, `.feedback-msg.err[id="form-error"]` (caja de error del formulario)
  - `privacidad.html`, `.highlight-box` (aviso destacado sobre tratamiento de datos)
- **Categoría:** Anti-Pattern
- **Impacto:** border-left de 3px como único recurso de énfasis es una firma visual de plantilla genérica, explícitamente prohibida en las reglas del skill ("Never intentional. Rewrite with full borders, background tints, leading numbers/icons, or nothing"). Se repetía en 3 componentes distintos sin variación — indicio de que se copió el mismo recurso por defecto en vez de diseñarse cada caso.
- **Arreglo aplicado:**
  - `.ejercicio-title`: se quitó el `border-left`/`padding-left` y se sustituyó por un punto (`::before`, círculo de 7px en `var(--accent)`) delante del título, en línea con el estilo de "leading icon" que ya permiten las reglas.
  - `.feedback-msg.err#form-error`: se quitó el `border-left` y se dejó un único borde completo (`1px solid #b3452f`, el mismo tono rojo-marrón que antes solo estaba en el borde lateral) — más consistente visualmente y más fácil de ver como caja de alerta completa.
  - `.highlight-box` (privacidad.html): igual, se quitó el `border-left` y el borde completo pasa a `1px solid var(--accent)` (antes era `var(--border)` + el lateral en acento) — mismo peso visual, sin la firma prohibida.

### [P2] Página principal sin jerarquía de encabezados — CORREGIDO
- **Ubicación:** `index.html`
- **Categoría:** Accesibilidad / Semántica
- **Impacto:** ni el título "¿Qué quieres trabajar hoy?"/"¿Qué quieres saber del reglamento?" ni los títulos de sección ("PARTE PRINCIPAL", etc.) ni el título de cada ejercicio usaban etiquetas de encabezado (`<h1>`–`<h3>`) — todos eran `<div>`. Un usuario de lector de pantalla no tenía ningún punto de navegación por encabezados en toda la página, ni siquiera un `<h1>` que identificara la pantalla. Además, el único candidato a `<h1>` (el título del formulario) se oculta con `display:none` en cuanto se muestran resultados (`showResults()`), así que la vista más cargada de contenido —la sesión generada— se quedaba sin ningún encabezado visible o accesible mientras se está mostrando.
- **WCAG:** 1.3.1 Info and Relationships (AA); mejores prácticas de navegación por encabezados
- **Arreglo aplicado:**
  - Los dos títulos de estado inicial (`.center-title`) pasan de `<div>` a `<h1>`. Como están en `display:none` mutuamente excluyente, nunca coexisten dos `<h1>` visibles/accesibles a la vez.
  - Se añadió un `<h1 id="results-heading" class="sr-only">` al inicio del bloque `#results`, oculto visualmente (nueva clase `.sr-only` en `theme.css`, patrón estándar de "visualmente oculto pero accesible") pero presente para lectores de pantalla, con texto dinámico ("Sesión de entrenamiento generada" / "Respuesta sobre el reglamento") fijado por JS en `renderResults()`/`renderReglamento()`.
  - Los títulos de sección generados por JS (`.section-title`, ej. "PARTE PRINCIPAL") pasan de `<div>` a `<h2>`.
  - El título de cada ejercicio (`.ejercicio-title`) pasa de `<div>` a `<h3>`, correctamente anidado bajo su sección.
  - Las páginas legales (`privacidad.html`, `aviso_legal.html`) ya usaban `<h1>`/`<h2>` correctamente — no se tocaron.

### [P2] Paleta y reset CSS duplicados íntegros en 3 plantillas — CORREGIDO
- **Ubicación:** `index.html`, `privacidad.html`, `aviso_legal.html`
- **Categoría:** Theming / mantenibilidad
- **Impacto:** el bloque `:root { --accent: ...; --bg: ...; ... }` (9 variables) y el reset universal `*,*::before,*::after{box-sizing...}` estaban copiados letra por letra en las 3 plantillas, junto con el mismo `@media (prefers-reduced-motion: no-preference) { @view-transition {...} }`. Un cambio de paleta (por ejemplo, ajustar el naranja de marca) requeriría editar 3 sitios a mano y arriesgarse a que se desincronicen — que es justo lo que ya había pasado parcialmente con los colores de "error" (`#b3452f`/`#5c4322`), definidos sueltos en vez de como token.
- **Arreglo aplicado:** se creó `pizarra/static/pizarra/css/theme.css` con el `:root`, el reset y el `@view-transition` compartidos, más la nueva clase `.sr-only`. Las 3 plantillas cargan ahora `<link rel="stylesheet" href="{% static 'pizarra/css/theme.css' %}">` justo después de `fonts.css`, y sus bloques `<style>` inline se quedan solo con las reglas específicas de cada página. Sin cambio visual: es una extracción, no una modificación de valores.

### [P3] Objetivos táctiles pequeños en controles compactos — ABIERTO
- **Ubicación:** `.mode-tab` (~26px de alto), `.chip` (~27px), `.dd-btn` (~26px) en `index.html`
- **Categoría:** Responsive / táctil
- **Impacto:** por debajo de los 44×44px recomendados para controles táctiles (afecta principalmente al selector de modo Sesión/Reglamento y a los desplegables de categoría/duración en móvil). No es un bloqueo — los controles son alcanzables, solo más incómodos de precisar con el dedo.
- **Por qué se deja abierto:** aumentar el padding lo suficiente para llegar a 44px casi duplicaría el tamaño visual de estos elementos (chips y pills), lo que puede desequilibrar una composición ya ajustada a mano. Sin poder verificar en vivo en un navegador contra el propio staging (Playwright no estaba disponible en esta sesión), no quise aplicar ese cambio a ciegas y arriesgar una regresión visual. Recomendación: retomar con `/impeccable adapt` o iteración en vivo cuando haya navegador disponible.

---

## Patrones y hallazgos positivos (a mantener)

- **Combobox accesible hecho a mano:** el reemplazo del `<select>` nativo para "Categoría" y "Duración" tiene `role="listbox"`/`role="option"`, `aria-expanded`, `aria-selected`, navegación completa por teclado (flechas, Enter, Espacio, Escape) y sincroniza con un `<select>` oculto real para no perder el valor del formulario. Nivel de detalle por encima de la media.
- **Errores en línea, no bloqueantes:** ni un solo `alert()` en todo el flujo; los errores usan `role="alert"` con texto dinámico.
- **Paleta de tokens consistente:** salvo las excepciones ya corregidas, todo el color pasa por variables CSS, y ni el fondo ni el texto usan negro/blanco puro (`#15120e`/`#f2ede4`), coherente con el matiz cálido de marca.
- **`prefers-reduced-motion` respetado** tanto para las animaciones de entrada (`slideUp`) como para las transiciones de hover.
- **Fuentes autoalojadas con `font-display: swap`**, sin dependencia de Google Fonts — buena decisión de rendimiento y privacidad, coherente con la política de "todo en el servidor propio" que describe `privacidad.html`.
- **Longitud de línea cuidada** en las páginas legales (`.page-wrap { max-width: 720px }`, `line-height: 1.7`).

---

## Acciones recomendadas (orden de prioridad)

1. **[P1] Ya aplicado** — contraste del CTA principal y de la pestaña activa corregido (`/impeccable harden` cubriría una pasada más amplia de contraste si se quiere revisar el resto de la superficie).
2. **[P2] Ya aplicado** — 3 side-stripe borders eliminados (`/impeccable polish`).
3. **[P2] Ya aplicado** — jerarquía de encabezados añadida (`/impeccable clarify` para revisar si falta algo similar en otras vistas futuras).
4. **[P2] Ya aplicado** — CSS duplicado centralizado en `theme.css` (`/impeccable document` si se quiere dejar constancia formal del sistema de tokens).
5. **[P3] Pendiente** — objetivos táctiles: `/impeccable adapt` con navegador en vivo contra el staging para ajustar el padding de `.mode-tab`/`.chip`/`.dd-btn` sin desequilibrar la composición.

> Puedes pedirme que ejecute lo pendiente cuando quieras, o dejarlo para una sesión con navegador disponible.
>
> Vuelve a correr `/impeccable audit` después de desplegar estos cambios en staging para confirmar visualmente que la puntuación sube.

---

## Ficheros modificados

- `mipizarra/frontend/pizarra/templates/pizarra/index.html`
- `mipizarra/frontend/pizarra/templates/pizarra/privacidad.html`
- `mipizarra/frontend/pizarra/templates/pizarra/aviso_legal.html`
- `mipizarra/frontend/pizarra/static/pizarra/css/theme.css` (nuevo)

Ningún cambio toca backend, Docker, infraestructura ni el servidor real — son ediciones de plantillas Django y CSS en el repo local. No se ha desplegado ni reiniciado nada.
