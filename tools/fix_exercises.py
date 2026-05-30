"""Reescribe ej_002, ej_003, ej_004 como drills reales
y sustituye 'portador' por 'jugador con balón' en todos los textos.
"""
import json

SRC = r"c:\Users\nacho\Proyectos\servidor-config\mipizarra\data\exercises.json"

# ── Nuevos ejercicios ────────────────────────────────────────────────────────

EJ_002 = {
    "id": "ej_002",
    "nombre": "Bloqueo directo base-pívot — 2c1 con lectura",
    "categoria": "bloqueo_directo",
    "subcategoria": "pick_and_roll",
    "edades": ["U14", "U16", "U18", "Senior"],
    "duracion_min": 15,
    "intensidad": 3,
    "carga_cognitiva": 4,
    "jugadores_minimos": 3,
    "objetivos": {
        "tacticos": ["bloqueo directo", "lectura de la respuesta defensiva", "caída al aro (roll)"],
        "tecnicos": ["ángulo y legalidad del bloqueo", "salida hombro con hombro", "bote de salida", "pase al continuador"],
        "fisicos": []
    },
    "puntos_clave": [
        "A2 planta el bloqueo con los pies anchos y brazos cruzados ANTES de que A1 llegue. Sin posición establecida es falta en ataque.",
        "A1 sale rozando el hombro de A2 — hombro con hombro. Si sale separado, D1 pasa por el hueco sin tocar el bloqueo.",
        "Tras plantar el bloqueo, A2 pivota inmediatamente mirando el balón y corre al aro. Esto es el roll: no quedarse parado.",
        "A1 lee a D1: si D1 siguió a A1 hacia el codo → pase a A2 en el roll para bandeja; si D1 ayudó al roll → A1 lanza desde el codo.",
        "Progresión obligatoria: empezar siempre 2v0 para memorizar la mecánica. Solo añadir D1 cuando los movimientos sean automáticos."
    ],
    "descripcion": (
        "ORGANIZACIÓN: dos filas en cabecera — fila de bases con balón (A1) y fila de pívots sin balón (A2). "
        "En progresiones, añadir D1 sobre el base. "
        "SECUENCIA: "
        "(1) A1 bota hacia el lado del bloqueo, llamando a A2. "
        "(2) A2 sube desde el poste alto y planta el bloqueo sobre D1 — pies anchos, brazos cruzados, posición legal antes del contacto. "
        "(3) A1 sale hombro con hombro botando hacia el codo. "
        "(4) A2 pivota hacia la pintura mirando el balón y corre al aro (roll). "
        "(5) A1 lee a D1: si D1 siguió a A1 → pase a A2 en el roll para bandeja; si D1 ayudó al roll → A1 lanza desde el codo. "
        "ROTACIÓN: A1 va al final de la fila de bases; A2, al final de la fila de pívots; D1 pasa a la fila de bases. "
        "Trabajar ambos lados del campo alternativamente."
    ),
    "diagramas": [
        {
            "titulo": "Fase 1 — A2 sube a plantar el bloqueo sobre D1",
            "tipo": "media_pista",
            "jugadores_ataque": [
                {"id": "A1", "x": 50, "y": 65},
                {"id": "A2", "x": 38, "y": 36}
            ],
            "jugadores_defensa": [
                {"id": "D1", "x": 50, "y": 60}
            ],
            "balon_inicio": {"portador": "A1"},
            "movimientos": [
                {"de": "A2", "a_pos": {"x": 46, "y": 62}, "tipo": "bloqueo", "orden": 1}
            ],
            "conos": []
        },
        {
            "titulo": "Fase 2 — A1 usa el bloqueo; A2 hace el roll al aro",
            "tipo": "media_pista",
            "jugadores_ataque": [
                {"id": "A1", "x": 50, "y": 65},
                {"id": "A2", "x": 46, "y": 62}
            ],
            "jugadores_defensa": [
                {"id": "D1", "x": 50, "y": 60}
            ],
            "balon_inicio": {"portador": "A1"},
            "movimientos": [
                {"de": "A1", "a_pos": {"x": 35, "y": 50}, "tipo": "bote", "curva": True, "orden": 1},
                {"de": "A2", "a_pos": {"x": 50, "y": 18}, "tipo": "desplazamiento", "orden": 2},
                {"de": "A1", "a": "A2", "tipo": "pase", "orden": 3}
            ],
            "conos": []
        }
    ]
}

EJ_003 = {
    "id": "ej_003",
    "nombre": "Corte en V desde esquina",
    "categoria": "juego_equipo",
    "subcategoria": "movimientos_sin_balon",
    "edades": ["U12", "U14", "U16", "U18", "Senior"],
    "duracion_min": 10,
    "intensidad": 3,
    "carga_cognitiva": 3,
    "jugadores_minimos": 4,
    "objetivos": {
        "tacticos": ["desmarcarse sin balón con corte en V", "creación de espacio para el pasador", "recepción en movimiento"],
        "tecnicos": ["amago previo al corte", "cambio de ritmo brusco", "recepción en triple amenaza"],
        "fisicos": ["aceleración explosiva"]
    },
    "puntos_clave": [
        "El amago hacia la línea de fondo debe ser lento — al menos un paso completo con el peso cargado. Si el amago es rápido, el defensor no muerde y el corte no genera espacio.",
        "El cambio de dirección al 45° es brusco y sin pasos extra. Cuanto más limpio el giro, más espacio ganado sobre el defensor.",
        "En el 45°, mostrar las manos ANTES de que el pasador lance. El pasador espera esa señal para soltar el balón.",
        "Recepción en triple amenaza: pies orientados al aro, rodillas flexionadas, balón protegido con los codos. No recibir de espaldas ni con los pies cruzados.",
        "El pasador no lanza si el cortador no tiene las manos arriba — si lanza antes, la defensa puede interceptar."
    ],
    "descripcion": (
        "ORGANIZACIÓN: dos filas — fila de pasadores en cabecera con balón (A2) y fila de cortadores en esquina derecha sin balón (A1). "
        "SECUENCIA: "
        "(1) A1 da un paso lento y largo hacia la línea de fondo, simulando querer entrar a canasta — amago convincente. "
        "(2) Al segundo paso, A1 gira bruscamente y corta explosivamente hacia el 45° mostrando las manos al pasador. "
        "(3) A2 en cabecera lanza cuando A1 tiene las manos arriba en el 45°. "
        "(4) A1 recibe en triple amenaza y decide: tiro, bote hacia el interior, o pase de vuelta a A2. "
        "(5) A1 recoge su propio rebote si tira. "
        "ROTACIÓN: A1 pasa a la fila de pasadores; A2 pasa a la fila de cortadores. "
        "Trabajar por ambos lados. "
        "PROGRESIÓN: sin defensa → D1 pasivo sobre el cortador → D1 activo."
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
            {"de": "A2", "a": "A1", "tipo": "pase", "orden": 3}
        ],
        "conos": []
    }
}

EJ_004 = {
    "id": "ej_004",
    "nombre": "Pases en carrera + 2 contra 1 desde saque de banda",
    "categoria": "ventaja_numerica",
    "subcategoria": "contraataque",
    "edades": ["U12", "U14", "U16", "U18", "Senior"],
    "duracion_min": 12,
    "intensidad": 4,
    "carga_cognitiva": 3,
    "jugadores_minimos": 3,
    "objetivos": {
        "tacticos": ["pase en carrera a pista completa", "transición a 2c1 desde saque lateral", "lectura del único defensor"],
        "tecnicos": ["pase adelantado diagonal en carrera", "saque de banda en movimiento", "decisión en 2c1"],
        "fisicos": ["sprint", "coordinación en carrera"]
    },
    "puntos_clave": [
        "Los pases van siempre adelantados y en diagonal: el receptor no frena para recibir. Si alguien para, el ritmo del drill se rompe.",
        "La secuencia de pases es fija — centro→derecha→centro→izquierda — para memorizarla y ejecutarla a máxima velocidad sin pensar.",
        "Quien planta el balón fuera NO entra a la pista hasta que uno de los dos saca de banda. El saque simula una situación real de partido.",
        "En el 2c1: el que saca de banda ataca con bote directo al aro; el otro sale al carril libre. El defensor elige a quién presionar — la decisión la lee el que tiene el balón.",
        "El defensor arranca en desventaja de posición — los dos atacantes deben aprovechar esa ventaja sin ralentizar la acción."
    ],
    "descripcion": (
        "ORGANIZACIÓN: tres jugadores en la línea de fondo — A1 en el centro con balón, A2 en la banda derecha, A3 en la banda izquierda. "
        "SECUENCIA FASE 1 — carrera con pases: "
        "(1) Los tres arrancan corriendo hacia la canasta contraria. "
        "(2) A1 pasa a A2 (centro a derecha); A2 pasa a A1 (derecha a centro); A1 pasa a A3 (centro a izquierda). "
        "Pases adelantados en diagonal — nadie para para recibir. "
        "(3) Cuando A3 llega a la línea de medio campo con el balón, lo planta en el suelo fuera de la pista (en la línea lateral) y se queda fuera. "
        "SECUENCIA FASE 2 — 2c1: "
        "(4) A3 pasa a defender: entra a la pista cuando uno de los dos comience el saque de banda. "
        "(5) A1 o A2 recoge el balón plantado y saca de banda desde la línea lateral; el otro se coloca en el carril opuesto. "
        "(6) A1 y A2 atacan 2c1 contra A3 hasta anotar o que la defensa recupere el balón. "
        "ROTACIÓN: en la siguiente repetición, quien defendió pasa a salir de centro (A1)."
    ),
    "diagramas": [
        {
            "titulo": "Fase 1 — Carrera con pases: centro → derecha → centro → izquierda",
            "tipo": "pista_completa",
            "jugadores_ataque": [
                {"id": "A1", "x": 50, "y": 92},
                {"id": "A2", "x": 10, "y": 92},
                {"id": "A3", "x": 90, "y": 92}
            ],
            "jugadores_defensa": [],
            "balon_inicio": {"portador": "A1"},
            "movimientos": [
                {"de": "A1", "a": "A2", "tipo": "pase", "orden": 1},
                {"de": "A2", "a": "A1", "tipo": "pase", "orden": 2},
                {"de": "A1", "a": "A3", "tipo": "pase", "orden": 3},
                {"de": "A3", "a_pos": {"x": 100, "y": 50}, "tipo": "desplazamiento", "orden": 4}
            ],
            "conos": [
                {"x": 100, "y": 50}
            ]
        },
        {
            "titulo": "Fase 2 — A3 defiende; A1 y A2 atacan 2c1 desde saque lateral en medio campo",
            "tipo": "media_pista",
            "jugadores_ataque": [
                {"id": "A1", "x": 2, "y": 85},
                {"id": "A2", "x": 50, "y": 85}
            ],
            "jugadores_defensa": [
                {"id": "D1", "x": 50, "y": 55}
            ],
            "balon_inicio": {"portador": "A1"},
            "movimientos": [
                {"de": "A1", "a": "A2", "tipo": "pase", "orden": 1},
                {"de": "A2", "a_pos": {"x": 50, "y": 55}, "tipo": "bote", "orden": 2},
                {"de": "A1", "a_pos": {"x": 10, "y": 50}, "tipo": "desplazamiento", "orden": 3},
                {"de": "A2", "a": "A1", "tipo": "pase", "orden": 4},
                {"de": "A1", "tipo": "tiro", "orden": 5}
            ],
            "conos": []
        }
    ]
}

# ── Reemplazos de texto ──────────────────────────────────────────────────────

REEMPLAZOS = [
    # Más específico primero
    ("portador del balón",          "jugador con balón"),
    ("portador central",            "jugador con balón en el centro"),
    ("portador anterior",           "jugador que tenía el balón"),
    ("alternando el portador",      "alternando quién lleva el balón"),
    ("portador siempre al centro",  "el que lleva el balón siempre al centro"),
    ("el nuevo portador",           "el nuevo jugador con balón"),
    ("al portador",                 "al jugador con balón"),
    ("Al portador",                 "Al jugador con balón"),
    ("del portador",                "del jugador con balón"),
    ("sobre el portador",           "sobre el jugador con balón"),
    ("un portador",                 "un jugador con balón"),
    ("el portador",                 "el jugador con balón"),
    ("El portador",                 "El jugador con balón"),
    # catch-all (residual)
    ("portador",                    "jugador con balón"),
]


def fix_text(t: str) -> str:
    for old, new in REEMPLAZOS:
        t = t.replace(old, new)
    return t


def fix_ex(ex: dict) -> dict:
    for field in ("descripcion", "nombre"):
        if field in ex and isinstance(ex[field], str):
            ex[field] = fix_text(ex[field])
    if "puntos_clave" in ex:
        ex["puntos_clave"] = [fix_text(p) for p in ex["puntos_clave"]]
    if "objetivos" in ex:
        for k in ex["objetivos"]:
            ex["objetivos"][k] = [fix_text(t) for t in ex["objetivos"][k]]
    return ex


# ── Main ─────────────────────────────────────────────────────────────────────

with open(SRC, encoding="utf-8") as f:
    data = json.load(f)

replacements = {"ej_002": EJ_002, "ej_003": EJ_003, "ej_004": EJ_004}

for i, ex in enumerate(data):
    if ex["id"] in replacements:
        data[i] = replacements[ex["id"]]
        print(f"  Reemplazado {ex['id']}")

data = [fix_ex(ex) for ex in data]

with open(SRC, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

# Verificar que no queda "portador" en texto
remaining = []
for ex in data:
    for field in ("descripcion", "nombre"):
        val = ex.get(field, "")
        if "portador" in val:
            remaining.append((ex["id"], field, val[:80]))
    for p in ex.get("puntos_clave", []):
        if "portador" in p:
            remaining.append((ex["id"], "puntos_clave", p[:80]))
    for k, v in ex.get("objetivos", {}).items():
        for t in v:
            if "portador" in t:
                remaining.append((ex["id"], f"objetivos.{k}", t[:80]))

if remaining:
    print("\nInstancias de 'portador' que quedan en texto:")
    for r in remaining:
        print(f"  {r}")
else:
    print("\nOK — ninguna instancia de 'portador' en campos de texto.")

print(f"\nTotal ejercicios: {len(data)}")
