"""Catálogo ES→EN de la interfaz. La clave es el texto en español tal como está en la plantilla (`{% t "..." %}`) o en
el JavaScript (`tr('...')`); lo que no está aquí se muestra en español. Inglés americano.

Alcance de esta primera fase: cabecera, página principal (sesión y reglamento) y pantalla de entrada. Siguen en
español: Jugadas, Fichas, las páginas legales, los ejemplos (chips) y todo lo que genera el servidor (sesiones,
respuestas de reglamento, textos de las fichas)."""

TEXTOS_EN = {
    # cabecera
    "Saltar al contenido": "Skip to content",
    "Ir al inicio de MiPizarra": "Go to the MiPizarra home page",
    "MiPizarra, ir al inicio": "MiPizarra, go to the home page",
    "Secciones": "Sections",
    "Sesión": "Session",
    "Reglamento": "Rules",
    "Jugadas": "Plays",
    "Fichas": "Cards",
    "Entrar": "Sign in",
    "Salir": "Sign out",
    "Cerrar sesión de": "Sign out of",
    "Idioma": "Language",
    # página principal: metadatos
    "MiPizarra — Asistente de entrenamiento": "MiPizarra — Training assistant",
    "Genera sesiones de entrenamiento de baloncesto y diagramas tácticos con IA local, a partir de la categoría, la duración y el objetivo del entrenamiento.":
        "Generate basketball practice sessions and tactical diagrams with local AI, based on the age group, the duration and the goal of the practice.",
    "Genera sesiones de entrenamiento de baloncesto y diagramas tácticos con IA local.":
        "Generate basketball practice sessions and tactical diagrams with local AI.",
    # sesión
    "¿Qué quieres trabajar hoy?": "What do you want to work on today?",
    "Describe el objetivo y genera una sesión completa con ejercicios y diagramas tácticos.":
        "Describe the goal and generate a full session with drills and tactical diagrams.",
    "Categoría": "Age group",
    "Categoría: sin especificar": "Age group: any",
    "Sin especificar": "Any",
    "Prebenjamín (U8)": "U8",
    "Benjamín (U10)": "U10",
    "Alevín (U12)": "U12",
    "Infantil (U14)": "U14",
    "Cadete (U16)": "U16",
    "Junior (U18)": "U18",
    "Duración": "Duration",
    "Duración: flexible": "Duration: flexible",
    "Flexible": "Flexible",
    "Jugadores": "Players",
    "Jugadores: sin límite": "Players: no limit",
    "Sin límite": "No limit",
    "Hasta 4": "Up to 4", "Hasta 6": "Up to 6", "Hasta 8": "Up to 8", "Hasta 10": "Up to 10",
    "Hasta 12": "Up to 12", "Hasta 14": "Up to 14", "Hasta 16": "Up to 16",
    "Número máximo de jugadores": "Maximum number of players",
    "Descripción del entrenamiento": "Practice description",
    "Ej: Tiro en suspensión y defensa de bloqueo directo…": "E.g.: Jump shot and defending the pick and roll…",
    "Generar diagramas": "Generate diagrams",
    "Generar sesión": "Generate session",
    "Enter para generar · Shift+Enter para nueva línea": "Enter to generate · Shift+Enter for a new line",
    "De momento las sesiones, las respuestas del reglamento y los ejercicios se generan en español: escribe el objetivo en español. El inglés llegará por fases.":
        "For now, sessions, rules answers and drills are generated in Spanish: write the goal in Spanish. English will arrive in stages.",
    # reglamento
    "¿Qué quieres saber del reglamento?": "What do you want to know about the rules?",
    "Pregunta sobre reglas, tiempos, categorías o cualquier duda arbitral.":
        "Ask about rules, timing, age groups or any officiating question.",
    "Ámbito": "Scope",
    "Ámbito del reglamento": "Rules scope",
    "Tu pregunta sobre el reglamento": "Your question about the rules",
    "Ej: ¿Es falta técnica si el entrenador entra a la pista?": "E.g.: Is it a technical foul if the coach steps onto the court?",
    "Consultar": "Ask",
    "Enter para consultar · Shift+Enter para nueva línea": "Enter to ask · Shift+Enter for a new line",
    "Respuestas sobre el reglamento": "Answers about the rules",
    "Respuestas": "Answers",
    "Limpiar": "Clear",
    # estados y resultado
    "Generando sesión… (puede tardar hasta 2 minutos)": "Generating session… (it can take up to 2 minutes)",
    "Sesión lista": "Session ready",
    "Ver en la web": "View on the web",
    "Descargar PDF": "Download PDF",
    "Resultado": "Result",
    "Nueva sesión": "New session",
    "Ejercicios consultados": "Drills consulted",
    "Descargar .txt": "Download .txt",
    "¿Usaste esta sesión en un entrenamiento real?": "Did you use this session in a real practice?",
    "Ej: Quité el 3c2 porque solo había 8 jugadores.": "E.g.: I removed the 3-on-2 because there were only 8 players.",
    "Cambios realizados sobre la sesión": "Changes made to the session",
    "Valoración de la sesión": "Session rating",
    "1 de 5": "1 of 5", "2 de 5": "2 of 5", "3 de 5": "3 of 5", "4 de 5": "4 of 5", "5 de 5": "5 of 5",
    "Guardar sesión usada": "Save the session as used",
    "0 ejercicios seleccionados": "0 drills selected",
    "Qué quieres cambiar de los ejercicios seleccionados": "What you want to change in the selected drills",
    "¿Qué quieres cambiar? Ej: sin defensor, más dinámico…": "What do you want to change? E.g.: no defender, more dynamic…",
    "Aplicar cambio": "Apply change",
    # pie
    "Política de privacidad": "Privacy policy (in Spanish)",
    "Aviso legal": "Legal notice (in Spanish)",
    "Código fuente (AGPL-3.0)": "Source code (AGPL-3.0)",
    # entrar
    "Entrar — MiPizarra": "Sign in — MiPizarra",
    "Acceso privado: entra con tu cuenta para usar MiPizarra.": "Private access: sign in with your account to use MiPizarra.",
    "Usuario": "Username",
    "Contraseña": "Password",
    "Mostrar": "Show",
}

# Mensajes del JavaScript. Los huecos se escriben {nombre} y los rellena tr(clave, {nombre: valor}).
JS_EN = {
    "Has hecho muchas peticiones seguidas. Podrás volver a probar en {t}.": "You have made too many requests in a row. You can try again in {t}.",
    "Error del servidor ({status})": "Server error ({status})",
    "Escribe una pregunta.": "Type a question.",
    "Consultando el reglamento…": "Checking the rules…",
    "Consultando el reglamento… {seg} s (la primera consulta puede tardar hasta 2 minutos)":
        "Checking the rules… {seg} s (the first query can take up to 2 minutes)",
    "Demasiadas consultas seguidas: espera a que termine la cuenta atrás.": "Too many queries in a row: wait for the countdown to finish.",
    "El reglamento no devolvió una respuesta. Prueba a reformular la pregunta.": "The rules assistant returned no answer. Try rephrasing the question.",
    "La consulta tardó demasiado. Inténtalo de nuevo.": "The query took too long. Try again.",
    "Describe qué quieres trabajar en el entrenamiento.": "Describe what you want to work on in practice.",
    "Error: {msg}": "Error: {msg}",
    "Reglamento general": "General rules",
    "{nombre} y reglamento general": "{nombre} and general rules",
    "Se responde con la normativa de {nombre} y, en todo lo que no regule, con el reglamento general de FIBA y de la federación española.":
        "Answers use the {nombre} rules and, for anything they do not cover, the general FIBA and Spanish federation rules.",
    "Reglamento de FIBA y de la federación española, válido en todas las comunidades.":
        "FIBA and Spanish federation rules, valid in every region.",
    "1 ejercicio seleccionado": "1 drill selected",
    "{n} ejercicios seleccionados": "{n} drills selected",
    "Describe qué quieres cambiar.": "Describe what you want to change.",
    "Corrigiendo {i}/{n}…": "Editing {i}/{n}…",
    "Error corrigiendo \"{nombre}\": {msg}": "Error editing \"{nombre}\": {msg}",
    "Aplicar cambio": "Apply change",
    "No hay sesión": "No session",
    "Generando PDF…": "Generating PDF…",
    "Error generando PDF": "Error generating the PDF",
    "Error generando PDF: {msg}": "Error generating the PDF: {msg}",
    "PDF descargado. También puedes ver la sesión en la web.": "PDF downloaded. You can also view the session on the web.",
    "Describe brevemente qué cambiaste.": "Briefly describe what you changed.",
    "✓ Sesión guardada. ¡Gracias!": "✓ Session saved. Thank you!",
    "Error guardando. Inténtalo de nuevo.": "Error saving. Try again.",
}
