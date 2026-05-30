"""Reescribe los ejercicios estáticos como drills reales con movimiento,
secuencia clara, rotación y elemento competitivo o de transición.
"""
import json

SRC = r"c:\Users\nacho\Proyectos\servidor-config\mipizarra\data\exercises.json"

# ─────────────────────────────────────────────────────────────────────────────
# ej_002  Bloqueo directo — pick & roll a todo campo + 2c1 de vuelta
# ─────────────────────────────────────────────────────────────────────────────
EJ_002 = {
    "id": "ej_002",
    "nombre": "Bloqueo directo a todo campo — pick & roll + 2c1 de vuelta",
    "categoria": "bloqueo_directo",
    "subcategoria": "pick_and_roll",
    "edades": ["U14", "U16", "U18", "Senior"],
    "duracion_min": 15,
    "intensidad": 4,
    "carga_cognitiva": 4,
    "jugadores_minimos": 3,
    "objetivos": {
        "tacticos": ["bloqueo directo bajo fatiga", "lectura de la respuesta defensiva", "transición inmediata 2c1"],
        "tecnicos": ["ángulo y legalidad del bloqueo", "salida hombro con hombro", "roll al aro", "pase o tiro según la lectura"],
        "fisicos": ["sprint a todo campo", "esfuerzo continuo"]
    },
    "puntos_clave": [
        "A2 planta el bloqueo con pies anchos y brazos cruzados ANTES del contacto. Sin posición establecida es falta en ataque.",
        "A1 sale hombro con hombro rozando a A2. Si sale separado, D1 pasa por el hueco.",
        "A2 pivota inmediatamente mirando el balón y corre al aro (roll). No esperar parado.",
        "A1 lee a D1: si siguió a A1 hacia el codo → pase a A2 en el roll; si D1 ayudó al roll → A1 lanza.",
        "En la transición 2c1 de vuelta, D1 no espera: pasa a A2 en carrera y ambos atacan a máxima velocidad.",
        "Progresión: 2v0 (sin D1) para memorizar la mecánica → 2v1 con D1 pasivo → 2v1 con D1 activo."
    ],
    "descripcion": (
        "ORGANIZACIÓN: grupos de tres (A1/base con balón, A2/pívot, D1/defensor) en la línea de fondo propia. "
        "FASE 1 — ataque hacia la canasta contraria: "
        "(1) Los tres arrancan corriendo. D1 corre al lado de A1 defendiéndole. "
        "(2) Al llegar a la línea de triple de la canasta contraria, A2 planta el bloqueo directo sobre D1 — pies anchos, brazos cruzados. "
        "(3) A1 sale hombro con hombro hacia el codo. A2 hace el roll mirando el balón. "
        "(4) A1 lee a D1 y decide: pase a A2 en el roll o tiro desde el codo. "
        "FASE 2 — 2c1 de vuelta: "
        "(5) Tras la jugada (canasta o no), D1 coge el balón. A2 sprint hacia la canasta original. A1 queda como único defensor. "
        "(6) D1 pasa a A2 en carrera; D1 y A2 atacan 2c1 a la canasta original contra A1 solo. "
        "ROTACIÓN: quien fue defensor único en el 2c1 pasa a ser A1 (base) en la siguiente repetición."
    ),
    "diagramas": [
        {
            "titulo": "Fase 1 — Sprint + bloqueo directo en la canasta contraria",
            "tipo": "pista_completa",
            "jugadores_ataque": [
                {"id": "A1", "x": 50, "y": 92},
                {"id": "A2", "x": 30, "y": 92}
            ],
            "jugadores_defensa": [
                {"id": "D1", "x": 50, "y": 88}
            ],
            "balon_inicio": {"portador": "A1"},
            "movimientos": [
                {"de": "A2", "a_pos": {"x": 46, "y": 15}, "tipo": "desplazamiento", "orden": 1},
                {"de": "A1", "a_pos": {"x": 50, "y": 22}, "tipo": "bote", "orden": 2},
                {"de": "A2", "a_pos": {"x": 44, "y": 10}, "tipo": "bloqueo", "orden": 3},
                {"de": "A1", "a_pos": {"x": 35, "y": 22}, "tipo": "bote", "curva": True, "orden": 4},
                {"de": "A2", "a_pos": {"x": 50, "y": 5}, "tipo": "desplazamiento", "orden": 5},
                {"de": "A1", "a": "A2", "tipo": "pase", "orden": 6}
            ],
            "conos": []
        },
        {
            "titulo": "Fase 2 — D1 y A2 atacan 2c1 a la canasta original; A1 defiende solo",
            "tipo": "pista_completa",
            "jugadores_ataque": [
                {"id": "A1", "x": 50, "y": 50},
                {"id": "A2", "x": 30, "y": 15}
            ],
            "jugadores_defensa": [
                {"id": "D1", "x": 50, "y": 10}
            ],
            "balon_inicio": {"portador": "D1"},
            "movimientos": [
                {"de": "D1", "a": "A2", "tipo": "pase", "orden": 1},
                {"de": "A2", "a_pos": {"x": 10, "y": 75}, "tipo": "bote", "orden": 2},
                {"de": "D1", "a_pos": {"x": 50, "y": 70}, "tipo": "desplazamiento", "orden": 3},
                {"de": "A2", "a": "D1", "tipo": "pase", "orden": 4},
                {"de": "D1", "tipo": "tiro", "orden": 5}
            ],
            "conos": []
        }
    ]
}

# ─────────────────────────────────────────────────────────────────────────────
# ej_003  Corte en V + cierre defensivo 1c1
# ─────────────────────────────────────────────────────────────────────────────
EJ_003 = {
    "id": "ej_003",
    "nombre": "Corte en V + cierre defensivo 1c1",
    "categoria": "juego_equipo",
    "subcategoria": "movimientos_sin_balon",
    "edades": ["U12", "U14", "U16", "U18", "Senior"],
    "duracion_min": 10,
    "intensidad": 4,
    "carga_cognitiva": 4,
    "jugadores_minimos": 4,
    "objetivos": {
        "tacticos": ["corte en V para desmarcarse", "recepción en movimiento", "ataque tras close-out defensivo"],
        "tecnicos": ["amago previo al corte", "cambio de ritmo brusco", "recepción en triple amenaza", "1c1 contra defensa en cierre"],
        "fisicos": ["aceleración explosiva", "reacción defensiva"]
    },
    "puntos_clave": [
        "El amago hacia línea de fondo es lento y con peso cargado — al menos un paso completo. Un amago rápido no engaña al defensor.",
        "El cambio de dirección al 45° es brusco y sin pasos extra. La limpieza del giro determina cuánto espacio se gana.",
        "Mostrar las manos en el 45° ANTES de que A2 lance. Si las manos no están arriba, el pase no sale.",
        "A2 cierra inmediatamente tras pasar: el que pasó siempre defiende. Así A1 aprende a cortar bien para llegar con ventaja real.",
        "A1 debe decidir al recibir: si A2 llega tarde → tiro o bote directo; si A2 llega pronto → cambio de dirección o pase de vuelta."
    ],
    "descripcion": (
        "ORGANIZACIÓN: dos filas — fila de pasadores en cabecera con balón (A2) y fila de cortadores en esquina derecha sin balón (A1). "
        "SECUENCIA: "
        "(1) A1 da un paso lento hacia la línea de fondo — amago convincente. "
        "(2) A1 gira bruscamente y corta explosivamente hacia el 45° mostrando las manos. "
        "(3) A2 pasa cuando A1 tiene las manos arriba. "
        "(4) INMEDIATAMENTE tras pasar, A2 corre a cerrar (close-out) y defiende a A1 en 1c1. "
        "(5) A1 ataca el 1c1 con la ventaja que tiene sobre A2 que llega en movimiento. "
        "ROTACIÓN: si A1 anota → A1 a la fila de pasadores, A2 a la fila de cortadores. "
        "Si A2 para → A2 a la fila de pasadores, A1 vuelve a cortadores. "
        "Trabajar por ambos lados. PROGRESIÓN: sin A2 defendiendo (solo corte y tiro) → A2 defiende pasivo → A2 defiende activo."
    ),
    "diagrama": {
        "tipo": "media_pista",
        "jugadores_ataque": [
            {"id": "A1", "x": 6, "y": 22},
            {"id": "A2", "x": 50, "y": 65}
        ],
        "jugadores_defensa": [],
        "balon_inicio": {"portador": "A2"},
        "movimientos": [
            {"de": "A1", "a_pos": {"x": 8, "y": 10}, "tipo": "desplazamiento", "orden": 1},
            {"de": "A1", "a_pos": {"x": 25, "y": 50}, "tipo": "desplazamiento", "orden": 2},
            {"de": "A2", "a": "A1", "tipo": "pase", "orden": 3},
            {"de": "A2", "a_pos": {"x": 30, "y": 45}, "tipo": "desplazamiento", "orden": 4}
        ],
        "conos": []
    }
}

# ─────────────────────────────────────────────────────────────────────────────
# ej_005  1c1 en poste bajo — series competitivas
# ─────────────────────────────────────────────────────────────────────────────
EJ_005 = {
    "id": "ej_005",
    "nombre": "1c1 en poste bajo — series competitivas con pívot y cierre",
    "categoria": "1c1",
    "subcategoria": "juego_interior",
    "edades": ["U14", "U16", "U18", "Senior"],
    "duracion_min": 12,
    "intensidad": 4,
    "carga_cognitiva": 3,
    "jugadores_minimos": 3,
    "objetivos": {
        "tacticos": ["juego interior 1c1", "lectura del defensor desde el poste bajo"],
        "tecnicos": ["giro de poder (drop step)", "protección del balón en el poste", "uso del tablero"],
        "fisicos": ["dominio físico", "fuerza de pivote", "lucha de posición"]
    },
    "puntos_clave": [
        "Antes de recibir: A2 lucha para ganar posición. Si el defensor está por la línea de fondo → recibir y girar hacia el interior; si está por el interior → recibir y girar hacia la línea de fondo (drop step).",
        "Drop step: el pie exterior cae en diagonal hacia el tablero, un bote bajo y protegido, dos apoyos firmes bajo el aro antes de saltar.",
        "Proteger el balón durante todo el giro: cuerpo entre el defensor y el balón. No extender los brazos para proteger — usar el torso.",
        "El tablero es el aliado desde los ángulos de poste bajo: apuntar al cuadrado blanco, no al aro.",
        "A1 como pasador: si D2 abandona el poste para ayudar en otra zona, el pase entra inmediatamente. El pasador no es pasivo."
    ],
    "descripcion": (
        "ORGANIZACIÓN: A1 en el 45° derecho con balón, A2 en poste bajo derecho, D2 defendiendo a A2. "
        "SECUENCIA: "
        "(1) A2 pide el balón peleando la posición. A1 pasa cuando A2 está bien colocado. "
        "(2) A2 recibe y lee a D2: ejecuta el giro de poder (drop step) hacia la línea de fondo si D2 está por encima, o gira al interior si D2 está por abajo. "
        "(3) Finaliza con bandeja usando el tablero o tiro cercano. "
        "COMPETICIÓN: series de 5 posesiones. Quien mete más canastas de 5 gana. "
        "ROTACIÓN tras cada serie: A2 pasa a ser D2, D2 pasa a ser A1 (pasador), A1 pasa a ser A2 (atacante). "
        "Trabajar también el lado izquierdo del poste."
    ),
    "diagrama": {
        "tipo": "media_pista",
        "jugadores_ataque": [
            {"id": "A1", "x": 25, "y": 50},
            {"id": "A2", "x": 38, "y": 18}
        ],
        "jugadores_defensa": [
            {"id": "D2", "x": 44, "y": 22}
        ],
        "balon_inicio": {"portador": "A1"},
        "movimientos": [
            {"de": "A1", "a": "A2", "tipo": "pase", "orden": 1},
            {"de": "A2", "a_pos": {"x": 50, "y": 11}, "tipo": "bote", "curva": True, "orden": 2},
            {"de": "A2", "tipo": "tiro", "orden": 3}
        ],
        "conos": []
    }
}

# ─────────────────────────────────────────────────────────────────────────────
# ej_006  3c0 pase y corte — regla de los 5 pases + progresión a 3c3
# ─────────────────────────────────────────────────────────────────────────────
EJ_006 = {
    "id": "ej_006",
    "nombre": "3c0 pase y corte — regla de los 5 pases máximo",
    "categoria": "juego_equipo",
    "subcategoria": "rotaciones",
    "edades": ["U12", "U14", "U16", "U18", "Senior"],
    "duracion_min": 10,
    "intensidad": 3,
    "carga_cognitiva": 4,
    "jugadores_minimos": 3,
    "objetivos": {
        "tacticos": ["pase y corte", "espaciado dinámico", "toma de decisión con límite de tiempo"],
        "tecnicos": ["pase de pecho", "corte al aro tras pase", "relleno del espacio vacío"],
        "fisicos": []
    },
    "puntos_clave": [
        "Regla: máximo 5 pases desde que comienza la posesión. Si no hay tiro en 5 pases → la posesión no cuenta. Crea urgencia real.",
        "Tras pasar, cortar inmediatamente al aro. No pausar ni reposicionarse antes de cortar.",
        "El receptor lee el corte del pasador: si está libre → devolverle el balón; si está cubierto → ocupar el espacio que dejó.",
        "El tercer jugador rellena siempre el espacio vacío que deja quien corta. Nadie se queda en la misma posición.",
        "Progresión: 3c0 con regla → 3c1 (defensor solo en zona) → 3c3 live. El patrón sin defensa debe verse igual con defensores."
    ],
    "descripcion": (
        "ORGANIZACIÓN: A1 en cabecera con balón, A2 en 45° derecho, A3 en 45° izquierdo. "
        "REGLA: el trío tiene máximo 5 pases para anotar. Al 5º pase, si no hay tiro limpio, se reinicia la posesión y no cuenta. "
        "SECUENCIA: A1 pasa a A2 y corta al aro. A3 sube a cabecera. A2 decide: tira, pasa a A1 en el corte o reversa a A3. "
        "La acción continúa hasta que alguien tira (dentro del límite de 5 pases). "
        "COMPETICIÓN: contar cuántos triples o tiros abiertos se consiguen en 2 minutos. "
        "ROTACIÓN: los tres grupos de 3 se alternan cada 2 minutos. "
        "PROGRESIÓN: 3c0 → añadir 1 defensor en zona → 3c3 con defensores activos."
    ),
    "diagrama": {
        "tipo": "media_pista",
        "jugadores_ataque": [
            {"id": "A1", "x": 50, "y": 65},
            {"id": "A2", "x": 25, "y": 50},
            {"id": "A3", "x": 75, "y": 50}
        ],
        "jugadores_defensa": [],
        "balon_inicio": {"portador": "A1"},
        "movimientos": [
            {"de": "A1", "a": "A2", "tipo": "pase", "orden": 1},
            {"de": "A1", "a_pos": {"x": 50, "y": 11}, "tipo": "desplazamiento", "orden": 2},
            {"de": "A3", "a_pos": {"x": 50, "y": 65}, "tipo": "desplazamiento", "orden": 3},
            {"de": "A2", "a": "A1", "tipo": "pase", "orden": 4},
            {"de": "A1", "tipo": "tiro", "orden": 5}
        ],
        "conos": []
    }
}

# ─────────────────────────────────────────────────────────────────────────────
# ej_007  Penetración por línea de fondo — fila + progresión 1c1
# ─────────────────────────────────────────────────────────────────────────────
EJ_007 = {
    "id": "ej_007",
    "nombre": "Penetración por línea de fondo desde el 45° — fila + 1c1",
    "categoria": "1c1",
    "subcategoria": "penetracion",
    "edades": ["U12", "U14", "U16", "U18", "Senior"],
    "duracion_min": 10,
    "intensidad": 4,
    "carga_cognitiva": 3,
    "jugadores_minimos": 2,
    "objetivos": {
        "tacticos": ["penetración por línea de fondo", "uso del cuerpo como escudo"],
        "tecnicos": ["primer paso pegado al defensor", "bote de progresión", "bandeja a contrapié usando el tablero"],
        "fisicos": ["explosividad", "cambio de ritmo"]
    },
    "puntos_clave": [
        "El primer paso va pegado a la cadera del defensor (o del cono), no en arco. Pasar el hombro por delante de la cadera del defensor.",
        "El ángulo de bote va hacia el tablero, no al centro del aro. Así se usa el tablero y se evita la ayuda interior.",
        "Proteger el balón en todo el recorrido: cuerpo entre el defensor y el balón durante los botes.",
        "El último apoyo antes del aro: parada en dos tiempos para absorber el contacto o entrar equilibrado.",
        "En espera: los que no están actuando botan en el sitio. Nadie parado."
    ],
    "descripcion": (
        "ORGANIZACIÓN: fila en el 45° izquierdo (A2, A3... con balones). Cono en la posición del defensor imaginario (en el 45°). "
        "FASE 1 — sin defensa: cada jugador sale del 45°, da el primer paso PEGADO al cono y penetra por la línea de fondo. "
        "Entra por debajo del aro y hace bandeja por el lado contrario usando el tablero. "
        "Coge el rebote y va al final de la fila. "
        "FASE 2 — con defensa (D1 real): D1 espera en posición sobre el 45°. A1 recibe el balón (del anterior rebote o de la fila) "
        "y ataca 1c1 por la línea de fondo. D1 defiende activamente. "
        "ROTACIÓN: A1 → D1, D1 → final de la fila de atacantes. "
        "Trabajar el 45° derecho también."
    ),
    "diagrama": {
        "tipo": "media_pista",
        "jugadores_ataque": [
            {"id": "A1", "x": 75, "y": 50}
        ],
        "jugadores_defensa": [],
        "balon_inicio": {"portador": "A1"},
        "movimientos": [
            {"de": "A1", "a_pos": {"x": 90, "y": 20}, "tipo": "bote", "orden": 1},
            {"de": "A1", "a_pos": {"x": 50, "y": 11}, "tipo": "bote", "orden": 2},
            {"de": "A1", "tipo": "tiro", "orden": 3}
        ],
        "conos": [
            {"x": 75, "y": 42}
        ]
    }
}

# ─────────────────────────────────────────────────────────────────────────────
# ej_008  Defensa bloqueo directo 2c2 — marcador competitivo
# ─────────────────────────────────────────────────────────────────────────────
EJ_008 = {
    "id": "ej_008",
    "nombre": "Defensa del bloqueo directo 2c2 — competición defensiva",
    "categoria": "bloqueo_directo",
    "subcategoria": "defensa_pick_and_roll",
    "edades": ["U16", "U18", "Senior"],
    "duracion_min": 15,
    "intensidad": 4,
    "carga_cognitiva": 5,
    "jugadores_minimos": 4,
    "objetivos": {
        "tacticos": ["defensa del bloqueo directo", "comunicación defensiva", "ayuda y recuperación"],
        "tecnicos": ["hedge/show", "under", "cambio defensivo", "ice"],
        "fisicos": ["desplazamiento defensivo bajo fatiga"]
    },
    "puntos_clave": [
        "D1 y D2 comunican la opción defensiva (hedge, under, cambio, ice) ANTES de que A2 plante el bloqueo. No improvisar.",
        "Hedge/show: D2 sale a cortar el bote brevemente y recupera a su jugador. Si D2 tarda en recuperar → A2 queda libre en el roll.",
        "Under: solo válida si el jugador con balón es mal lanzador exterior. Regala espacio de tiro al perímetro.",
        "Cambio: debe ser audible y anticipado. Nunca reactivo. Requiere similitud física entre D1 y D2.",
        "Ice: D1 fuerza al jugador con balón hacia la línea de fondo antes del bloqueo; D2 corta ese camino. Requiere comunicación perfecta antes."
    ],
    "descripcion": (
        "ORGANIZACIÓN: A1 en cabecera con balón, A2 en el poste alto. D1 defiende a A1, D2 defiende a A2. "
        "SECUENCIA: A1 llama al bloqueo. D2 elige y comunica la opción defensiva a D1 ANTES de que A2 llegue. Se ejecuta el bloqueo y la acción sigue hasta finalización. "
        "MARCADOR COMPETITIVO: "
        "  - Defensa anota si para el play (turnover, tiro difícil o rebote defensivo). "
        "  - Ataque anota si consigue bandeja limpia o tiro abierto. "
        "  - Primero en llegar a 5 puntos gana la tanda. "
        "ROTACIÓN: el equipo perdedor sale; entra el siguiente grupo. El ganador se mantiene y cambia roles (ataque ↔ defensa). "
        "Trabajar las cuatro opciones defensivas en rondas separadas: una ronda hedge, una under, una cambio, una ice."
    ),
    "diagrama": {
        "tipo": "media_pista",
        "jugadores_ataque": [
            {"id": "A1", "x": 50, "y": 65},
            {"id": "A2", "x": 50, "y": 50}
        ],
        "jugadores_defensa": [
            {"id": "D1", "x": 50, "y": 58},
            {"id": "D2", "x": 50, "y": 44}
        ],
        "balon_inicio": {"portador": "A1"},
        "movimientos": [
            {"de": "A2", "a_pos": {"x": 44, "y": 60}, "tipo": "bloqueo", "orden": 1},
            {"de": "A1", "a_pos": {"x": 35, "y": 50}, "tipo": "bote", "curva": True, "orden": 2},
            {"de": "A2", "a_pos": {"x": 50, "y": 18}, "tipo": "desplazamiento", "orden": 3}
        ],
        "conos": []
    }
}

# ─────────────────────────────────────────────────────────────────────────────
# ej_011  5c0 ataque posicional — límite de posesión + transición a 5c5
# ─────────────────────────────────────────────────────────────────────────────
EJ_011 = {
    "id": "ej_011",
    "nombre": "5c0 ataque posicional — límite de posesión + transición a 5c5",
    "categoria": "juego_equipo",
    "subcategoria": "ataque_posicional",
    "edades": ["U16", "U18", "Senior"],
    "duracion_min": 15,
    "intensidad": 3,
    "carga_cognitiva": 5,
    "jugadores_minimos": 10,
    "objetivos": {
        "tacticos": ["ataque posicional", "espaciado colectivo", "toma de decisión con límite de posesión"],
        "tecnicos": ["pase y corte", "reversas", "espaciado dinámico"],
        "fisicos": []
    },
    "puntos_clave": [
        "Límite de posesión: 8 segundos para anotar desde que se cruza el medio campo. El límite obliga a atacar con convicción, no a circular sin decisión.",
        "Tras pasar, acción inmediata: cortar al aro o reposicionarse. Nunca quedarse en el mismo sitio tras un pase.",
        "Espaciado mínimo: cada jugador a 4-5 metros del compañero más cercano. Sin espaciado, el 5c0 colapsa en 5c5.",
        "Cambiar el balón de lado obliga a la defensa (imaginaria) a reorganizarse. Las reversas abren el ataque.",
        "Cuando el ataque falla el límite de 8 segundos → los cinco hacen un sprint al fondo y vuelven a iniciar. Consecuencia física real."
    ],
    "descripcion": (
        "ORGANIZACIÓN: cinco jugadores en posiciones base (cabecera, 45° derecho e izquierdo, poste alto, poste bajo). "
        "REGLA: 8 segundos para anotar desde que A1 cruza el medio campo. Si no se anota en 8 s → todos hacen sprint al fondo y vuelven (consecuencia). "
        "SECUENCIA: ejecutar el sistema de pase y corte buscando siempre tiro abierto o entrada limpia dentro del límite temporal. "
        "MARCADOR: contar canastas conseguidas dentro del límite en 5 minutos. "
        "ROTACIÓN de grupos: si hay dos grupos de 5, alternar cada 2 minutos. "
        "PROGRESIÓN: 5c0 con límite → 5c2 (dos defensores pasivos) → 5c5 live con el mismo límite de 8 s."
    ),
    "diagrama": {
        "tipo": "media_pista",
        "jugadores_ataque": [
            {"id": "A1", "x": 50, "y": 65},
            {"id": "A2", "x": 25, "y": 50},
            {"id": "A3", "x": 75, "y": 50},
            {"id": "A4", "x": 38, "y": 36},
            {"id": "A5", "x": 62, "y": 18}
        ],
        "jugadores_defensa": [],
        "balon_inicio": {"portador": "A1"},
        "movimientos": [
            {"de": "A1", "a": "A2", "tipo": "pase", "orden": 1},
            {"de": "A1", "a_pos": {"x": 38, "y": 18}, "tipo": "desplazamiento", "orden": 2},
            {"de": "A3", "a_pos": {"x": 50, "y": 65}, "tipo": "desplazamiento", "orden": 3},
            {"de": "A2", "a": "A1", "tipo": "pase", "orden": 4},
            {"de": "A1", "tipo": "tiro", "orden": 5}
        ],
        "conos": []
    }
}

# ─────────────────────────────────────────────────────────────────────────────
# ej_012  Corte puerta atrás + cierre defensivo 1c1
# ─────────────────────────────────────────────────────────────────────────────
EJ_012 = {
    "id": "ej_012",
    "nombre": "Corte puerta atrás + cierre defensivo 1c1",
    "categoria": "juego_equipo",
    "subcategoria": "cortes",
    "edades": ["U12", "U14", "U16", "U18", "Senior"],
    "duracion_min": 10,
    "intensidad": 4,
    "carga_cognitiva": 4,
    "jugadores_minimos": 4,
    "objetivos": {
        "tacticos": ["corte puerta atrás al explotar la sobredefensa", "timing del corte y el pase", "ataque tras close-out"],
        "tecnicos": ["amago creíble hacia el balón", "corte explosivo a canasta", "bandeja en carrera", "1c1 contra defensa en cierre"],
        "fisicos": ["aceleración explosiva"]
    },
    "puntos_clave": [
        "El amago hacia el balón debe ser creíble y comprometer al defensor — si el defensor no sigue el amago, no hay puerta atrás; cambiar al corte en V.",
        "El momento del corte lo dicta el defensor: cortar cuando el defensor carga el peso hacia el balón.",
        "A2 pasa al espacio donde va a llegar A1, no al cuerpo. Pase en lob o picado adelantado según la distancia.",
        "Si el pase llega → bandeja directa sin frenar. Si no llega → salir al perímetro y llamar de nuevo.",
        "A2 cierra inmediatamente tras el pase. A1 aprende a finalizar antes de que A2 llegue."
    ],
    "descripcion": (
        "ORGANIZACIÓN: dos filas — fila de pasadores en cabecera con balón (A2) y fila de cortadores en esquina izquierda sin balón (A1). "
        "SECUENCIA: "
        "(1) A1 da un paso hacia el balón (hacia A2), fingiendo pedir el pase. "
        "(2) Cuando A2 asiente o da la señal, A1 corta explosivamente a canasta por la línea de fondo (puerta atrás). "
        "(3) A2 pasa al espacio donde llegará A1 — pase adelantado al aro. "
        "(4) A1 recibe en carrera y termina en bandeja. "
        "(5) INMEDIATAMENTE tras pasar, A2 corre a cerrar (close-out) sobre A1 si no hubo bandeja limpia. A1 ataca el 1c1. "
        "ROTACIÓN: si A1 anota → A1 a pasadores, A2 a cortadores. Si A2 para → A2 a pasadores, A1 a cortadores. "
        "Trabajar por ambos lados. PROGRESIÓN: sin A2 defendiendo → A2 defiende pasivo → A2 defiende activo."
    ),
    "diagrama": {
        "tipo": "media_pista",
        "jugadores_ataque": [
            {"id": "A1", "x": 94, "y": 22},
            {"id": "A2", "x": 50, "y": 65}
        ],
        "jugadores_defensa": [],
        "balon_inicio": {"portador": "A2"},
        "movimientos": [
            {"de": "A1", "a_pos": {"x": 80, "y": 35}, "tipo": "desplazamiento", "orden": 1},
            {"de": "A1", "a_pos": {"x": 55, "y": 11}, "tipo": "desplazamiento", "orden": 2},
            {"de": "A2", "a": "A1", "tipo": "pase", "orden": 3},
            {"de": "A1", "tipo": "tiro", "orden": 4},
            {"de": "A2", "a_pos": {"x": 60, "y": 18}, "tipo": "desplazamiento", "orden": 5}
        ],
        "conos": []
    }
}

# ─────────────────────────────────────────────────────────────────────────────
# ej_028  3c2 cruce de bandas — con rotación y transición
# ─────────────────────────────────────────────────────────────────────────────
EJ_028 = {
    "id": "ej_028",
    "nombre": "3 contra 2 con cruce de bandas — transición continua",
    "categoria": "ventaja_numerica",
    "subcategoria": "contraataque",
    "edades": ["U14", "U16", "U18", "Senior"],
    "duracion_min": 12,
    "intensidad": 4,
    "carga_cognitiva": 4,
    "jugadores_minimos": 5,
    "objetivos": {
        "tacticos": ["contraataque con cruce para desorganizar la defensa", "lectura tras el cruce", "transición inmediata"],
        "tecnicos": ["cruce coordinado sin balón", "bote de progresión", "pase tras lectura"],
        "fisicos": ["sprint", "cambio de dirección a toda velocidad"]
    },
    "puntos_clave": [
        "El cruce ocurre antes de la línea de tiros libres: los bandas se cruzan por detrás del centro para no colisionar con el balón.",
        "El centro (A1) no se detiene durante el cruce: sigue botando al frente mientras A2 y A3 intercambian carriles.",
        "El cruce debe ser rápido y simultáneo. Si uno frena, la defensa recupera y el cruce no crea ventaja.",
        "A1 lee después del cruce: si la defensa siguió a cada lateral → hay vía abierta por el centro. Si la defensa no siguió → uno de los laterales está libre en la banda.",
        "TRANSICIÓN: los dos defensores recogen el balón y atacan 2c1 hacia la canasta contraria; el último atacante que tuvo el balón defiende solo."
    ],
    "descripcion": (
        "ORGANIZACIÓN: A1 en carril central con balón, A2 en banda derecha, A3 en banda izquierda. D1 y D2 en posición defensiva. "
        "FASE 1 — ataque con cruce: los tres salen en carrera. A2 y A3 cruzan sus carriles antes de la línea de tiros libres (A2 va a la izquierda, A3 a la derecha). "
        "A1 lee la respuesta de D1 y D2 y decide: pasa al lateral libre o entra por el centro. "
        "FASE 2 — transición: tras la jugada (canasta o no), D1 y D2 recogen el balón y salen en 2c1 a la canasta contraria. "
        "El último de A1/A2/A3 que tocó el balón queda como defensor único. Los otros dos se retiran. "
        "ROTACIÓN: el defensor único del 2c1 pasa a ser D1 en la siguiente repetición. "
        "PROGRESIÓN: 3c0 → 3c2 pasivos → 3c2 activos con transición."
    ),
    "diagrama": {
        "tipo": "media_pista",
        "jugadores_ataque": [
            {"id": "A1", "x": 50, "y": 80},
            {"id": "A2", "x": 10, "y": 80},
            {"id": "A3", "x": 90, "y": 80}
        ],
        "jugadores_defensa": [
            {"id": "D1", "x": 38, "y": 36},
            {"de": "D2", "x": 62, "y": 36}
        ],
        "balon_inicio": {"portador": "A1"},
        "movimientos": [
            {"de": "A1", "a_pos": {"x": 50, "y": 55}, "tipo": "bote", "orden": 1},
            {"de": "A2", "a_pos": {"x": 90, "y": 22}, "tipo": "desplazamiento", "curva": True, "orden": 2},
            {"de": "A3", "a_pos": {"x": 10, "y": 22}, "tipo": "desplazamiento", "curva": -40, "orden": 3},
            {"de": "A1", "a": "A3", "tipo": "pase", "orden": 4},
            {"de": "A3", "tipo": "tiro", "orden": 5}
        ],
        "conos": []
    }
}

# ─────────────────────────────────────────────────────────────────────────────
# Aplicar cambios al JSON
# ─────────────────────────────────────────────────────────────────────────────

REWRITES = {
    "ej_002": EJ_002,
    "ej_003": EJ_003,
    "ej_005": EJ_005,
    "ej_006": EJ_006,
    "ej_007": EJ_007,
    "ej_008": EJ_008,
    "ej_011": EJ_011,
    "ej_012": EJ_012,
    "ej_028": EJ_028,
}

with open(SRC, encoding="utf-8") as f:
    data = json.load(f)

for i, ex in enumerate(data):
    if ex["id"] in REWRITES:
        data[i] = REWRITES[ex["id"]]
        print(f"  Reemplazado {ex['id']}: {REWRITES[ex['id']]['nombre']}")

with open(SRC, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

# Verificar JSON
with open(SRC, encoding="utf-8") as f:
    check = json.load(f)
print(f"\nOK — {len(check)} ejercicios. JSON válido.")
