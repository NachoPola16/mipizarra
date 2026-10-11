---
name: MiPizarra
description: Asistente de entrenamiento de baloncesto: sesiones con diagramas y consulta de reglamento, oscuro y cálido.
colors:
  accent-orange: "#e8752c"
  accent-deep: "#c85f1f"
  ink-black: "#15120e"
  panel: "#1e1a15"
  panel-raised: "#2a2118"
  line: "#332c22"
  text: "#f2ede4"
  text-soft: "#d8d0c4"
  text-muted: "#9c9186"
  print-ink: "#1b1b1f"
  print-accent-text: "#b44a0c"
  print-line: "#e1dbd0"
typography:
  display:
    fontFamily: "Sora, Inter, sans-serif"
    fontSize: "clamp(1.5rem, 4vw, 2rem)"
    fontWeight: 800
    lineHeight: 1.15
    letterSpacing: "-0.02em"
  title:
    fontFamily: "Sora, Inter, sans-serif"
    fontSize: "1.02rem"
    fontWeight: 700
    lineHeight: 1.4
  body:
    fontFamily: "Inter, sans-serif"
    fontSize: "0.95rem"
    fontWeight: 400
    lineHeight: 1.7
  label:
    fontFamily: "Inter, sans-serif"
    fontSize: "0.68rem"
    fontWeight: 600
    letterSpacing: "0.12em"
rounded:
  sm: "6px"
  md: "10px"
  lg: "12px"
  pill: "20px"
spacing:
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "32px"
components:
  button-primary:
    backgroundColor: "{colors.accent-orange}"
    textColor: "{colors.ink-black}"
    rounded: "{rounded.md}"
    padding: "10px 22px"
    height: "44px"
  button-primary-hover:
    backgroundColor: "{colors.accent-deep}"
  chip:
    backgroundColor: "transparent"
    textColor: "{colors.text-muted}"
    rounded: "{rounded.pill}"
    padding: "7px 16px"
    height: "44px"
  dropdown-button:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.text-soft}"
    rounded: "{rounded.pill}"
    padding: "6px 14px"
    height: "44px"
  card:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.text-soft}"
    rounded: "{rounded.md}"
    padding: "20px 24px"
---

# Design System: MiPizarra

## 1. Overview

**Creative North Star: "El cuaderno del entrenador de noche"**

MiPizarra es una herramienta de trabajo, no un escaparate. Su aspecto es el de un cuaderno técnico bien hecho leído con poca
luz: fondos marrón oscuro cálido, texto crema, un único naranja de pista que marca lo que se puede pulsar y dónde está el
foco. La densidad es baja y el ritmo es vertical: una pregunta, una respuesta, una sesión, de arriba abajo, sin paneles
laterales ni cuadros de mando.

El sistema rechaza, por ese orden, el chatbot de IA con burbujas y degradados, la app corporativa de gestión de club, la web
deportiva recargada y el documento escolar sin jerarquía. Lo que queda es sobrio y cercano: tipografía con carácter solo en
los títulos, texto muy legible y mucho aire alrededor de lo importante.

**Key Characteristics:**
- Un solo acento (naranja) sobre neutros tintados de marrón; nunca negro ni blanco puros en pantalla.
- Tarjetas solo donde hay contenido que agrupar (una respuesta, un ejercicio); nada anidado.
- Objetivos táctiles de 44 px en pantallas táctiles y estrechas; compactos en escritorio.
- Impresión y PDF como superficie de primera clase, con su propia paleta de tinta sobre papel blanco.

## 2. Colors

Paleta cálida y restringida: neutros marrones y un naranja.

### Primary
- **Naranja de pista** (#e8752c): acción principal (botón de generar y consultar), pestaña activa, marca, casillas y foco.
- **Naranja profundo** (#c85f1f): estado hover del botón primario.

### Neutral
- **Negro cálido** (#15120e): fondo de página.
- **Panel** (#1e1a15): tarjetas, desplegables, barras de edición.
- **Panel elevado** (#2a2118): hover de opciones y superficies secundarias.
- **Línea** (#332c22): bordes y separadores.
- **Crema** (#f2ede4): texto principal y títulos.
- **Crema suave** (#d8d0c4): cuerpo de las tarjetas.
- **Gris cálido** (#9c9186): etiquetas, ayudas y texto secundario (≥ 4.5:1 sobre el fondo).

### Impresión
- **Tinta** (#1b1b1f) sobre papel blanco, **naranja de texto** (#b44a0c) para títulos de sección y **línea** (#e1dbd0).
  Mismo naranja de marca (#e8752c) en el filete del PDF.

**La regla del único acento.** El naranja ocupa menos del 10 % de cualquier pantalla y siempre significa «esto es lo siguiente
que haces» o «aquí está lo importante». No se usa como decoración.

## 3. Typography

**Display:** Sora (700 y 800). **Cuerpo y etiquetas:** Inter (300 a 700). Las dos se sirven en local (woff2) y los TTF del PDF
son los mismos.

### Hierarchy
- **Display** (800, clamp 1.5 a 2 rem, interlineado 1.15, -0.02em): título de cada pantalla y marca.
- **Title** (700, 1 a 1.25 rem): título de ejercicio, pregunta del reglamento, secciones.
- **Body** (400, 0.92 a 0.95 rem, 1.7): descripciones y respuestas; máximo 72 caracteres de línea.
- **Label** (600, 0.68 a 0.75 rem, mayúsculas con 0.12em): etiquetas de campo, rótulos de diagrama.

**La regla de las dos familias.** Sora solo para títulos y marca; todo lo demás, Inter. Nada de una tercera familia.

## 4. Elevation

Plano por capas tonales: la profundidad la dan los tres escalones de marrón (fondo, panel, panel elevado) y un borde de 1 px.
La única sombra es la de los desplegables abiertos (`0 12px 32px rgba(0,0,0,.45)`), porque flotan sobre el contenido. En
impresión no hay sombras ni fondos.

## 5. Components

### Buttons
- **Primario** («Generar sesión», «Consultar»): naranja de pista, texto negro cálido, radio 10 px, 44 px de alto en táctil.
  Hover a naranja profundo. Deshabilitado al 50 % mientras hay una petición en curso.
- **Descarga y secundarios**: contorno de 1 px sobre panel, hover con borde naranja.
- **Volver y texto**: sin caja, gris cálido, hover a crema.

### Chips y desplegables
- **Chips de ejemplo**: contorno, píldora de 20 px, texto gris; rellenan el campo, no envían nada.
- **Desplegable a medida** (categoría, duración, ámbito): píldora sobre panel, lista con `role=listbox`, flechas y
  Escape; opción activa en naranja con marca ✓.

### Cards
- **Tarjeta de respuesta o ejercicio**: panel, borde de 1 px, radio 10 px, relleno 20 a 24 px. Nunca anidadas.
- **Ficha de campos**: etiqueta en mayúsculas pequeñas a la izquierda, texto a la derecha; una columna en móvil.

### Inputs
- **Caja de texto con acciones**: borde que pasa a naranja con el foco dentro; Enter envía y Mayús+Enter salta de línea.

### Navigation
- **Conmutador Sesión / Reglamento**: pestañas en una cápsula sobre panel, la activa en naranja con texto oscuro.

### Diagrama
- **Pista y jugadores**: SVG propio, círculos blancos para ataque y cuadrados oscuros para defensa, siempre sobre blanco.

## 6. Do's and Don'ts

### Do:
- **Do** mantener un solo acento naranja y neutros tintados de marrón.
- **Do** usar 44 px de alto en cualquier control pulsable en pantallas táctiles o de ≤ 560 px.
- **Do** tratar la impresión y el PDF como superficies propias, con tinta sobre blanco y los mismos títulos que la web.
- **Do** decir al usuario cuánto puede tardar algo y qué hacer ante un error, en frases cortas.

### Don't:
- **Don't** usar negro ni blanco puros en pantalla, degradados, texto con degradado ni efectos de vidrio.
- **Don't** usar bordes laterales de color como acento ni tarjetas anidadas.
- **Don't** parecer un chatbot (burbujas, avatares, «asistente mágico») ni un ERP de club (tablas y menús laterales).
- **Don't** añadir una tercera familia tipográfica ni animaciones que compitan con la espera.
