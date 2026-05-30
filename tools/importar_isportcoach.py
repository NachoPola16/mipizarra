"""Añade los ejercicios extraídos de isportcoach.com a exercises.json.
Adaptados manualmente al esquema MiPizarra con estructura de drill real.
Sustituye al scraper automatizado (scraper_isportcoach.py).
"""
import json

SRC = r"c:\Users\nacho\Proyectos\servidor-config\mipizarra\data\exercises.json"

NUEVOS = [
    {
        "id": "ej_051",
        "nombre": "Castillos — 1c1 de manejo en cuadrado",
        "categoria": "1c1",
        "subcategoria": "manejo_balon",
        "edades": ["U12", "U14", "U16", "U18", "Senior"],
        "duracion_min": 8,
        "intensidad": 3,
        "carga_cognitiva": 3,
        "jugadores_minimos": 2,
        "fuente": "isportcoach.com",
        "objetivos": {
            "tacticos": ["protección del balón bajo presión individual"],
            "tecnicos": ["bote de protección", "cambios de mano bajo presión", "visión periférica con balón"],
            "fisicos": ["agilidad", "reacción"]
        },
        "puntos_clave": [
            "El atacante nunca puede ponerse de lado, de espaldas ni salir del área — cara siempre hacia el defensor.",
            "El bote de protección: cuerpo entre el defensor y el balón, brazo libre como escudo, bote bajo y alejado del defensor.",
            "El defensor toca el balón, no al jugador: presión sobre el balón, no sobre el cuerpo del rival.",
            "Cambiar de mano solo cuando el defensor se compromete hacia un lado — no hacerlo sin razón.",
            "En la fila de espera se sigue botando. Nadie parado."
        ],
        "descripcion": (
            "ORGANIZACIÓN: cuadrado de conos de aproximadamente 3x3 metros. "
            "A1 (atacante con balón) y D1 (defensor con balón) dentro del cuadrado. "
            "SECUENCIA: D1 presiona intentando tocar el balón de A1 mientras A1 lo protege botando. "
            "A1 no puede salir del cuadrado, ponerse de espaldas ni de lado. "
            "D1 intenta tocar el balón de A1 con su mano libre mientras controla el suyo. "
            "COMPETICIÓN: 1 minuto de reloj. "
            "Si D1 toca el balón de A1 → punto para D1. Si A1 sale del cuadrado → punto para D1. "
            "Al minuto, cambiar roles. Gana quien acumule más puntos tras dos rondas. "
            "PROGRESIÓN: reducir el cuadrado 50 cm para aumentar la dificultad."
        ),
        "diagrama": {
            "tipo": "media_pista",
            "jugadores_ataque": [
                {"id": "A1", "x": 50, "y": 50}
            ],
            "jugadores_defensa": [
                {"id": "D1", "x": 53, "y": 47}
            ],
            "balon_inicio": {"portador": "A1"},
            "movimientos": [
                {"de": "A1", "a_pos": {"x": 48, "y": 52}, "tipo": "bote", "orden": 1}
            ],
            "conos": [
                {"x": 44, "y": 44}, {"x": 56, "y": 44},
                {"x": 44, "y": 56}, {"x": 56, "y": 56}
            ]
        }
    },
    {
        "id": "ej_052",
        "nombre": "Tiro con presión — activación de defensores laterales",
        "categoria": "tiro",
        "subcategoria": "concentracion",
        "edades": ["U14", "U16", "U18", "Senior"],
        "duracion_min": 10,
        "intensidad": 3,
        "carga_cognitiva": 4,
        "jugadores_minimos": 4,
        "fuente": "isportcoach.com",
        "objetivos": {
            "tacticos": ["tiro bajo presión defensiva", "lectura de la posición del defensor"],
            "tecnicos": ["mecánica de tiro estable bajo presión", "recepción y decisión rápida"],
            "fisicos": []
        },
        "puntos_clave": [
            "El tirador no sabe de dónde viene la presión — debe recibir, orientarse y decidir antes de que el defensor llegue.",
            "Si el defensor llega tarde → tiro directo. Si el defensor llega pronto → bote al lado libre.",
            "Mecánica estable aunque el defensor esté encima: no apresurar el lanzamiento perdiendo la técnica.",
            "El pasador activa el drill: su pase es la señal de salida de los defensores.",
            "VARIANTE: defensores salen de espaldas para mayor reacción; o par de defensores sale vs impar de defensores."
        ],
        "descripcion": (
            "ORGANIZACIÓN: A1 (tirador) en posición de tiro (ej. codo o 45°). "
            "A2 (pasador) enfrentado a A1 con balón. "
            "D1 y D2 en los laterales del tirador, a 2-3 metros, mirando hacia fuera o de espaldas. "
            "SECUENCIA: A2 hace el pase a A1. En el momento del pase, D1 y D2 arrancan a cerrar sobre A1. "
            "A1 recibe, lee qué defensor llega antes y decide: tiro si hay espacio, bote al lado contrario si no. "
            "ROTACIÓN: A1 va a pasador, A2 va a D1, D1 a D2, D2 a tirador. "
            "PROGRESIÓN: defensores de espaldas al inicio → solo un defensor activo elegido por el entrenador → defensor con balón que dificulta la línea de pase."
        ),
        "diagrama": {
            "tipo": "media_pista",
            "jugadores_ataque": [
                {"id": "A1", "x": 35, "y": 41},
                {"id": "A2", "x": 50, "y": 65}
            ],
            "jugadores_defensa": [
                {"id": "D1", "x": 20, "y": 45},
                {"id": "D2", "x": 50, "y": 45}
            ],
            "balon_inicio": {"portador": "A2"},
            "movimientos": [
                {"de": "A2", "a": "A1", "tipo": "pase", "orden": 1},
                {"de": "D1", "a_pos": {"x": 32, "y": 41}, "tipo": "desplazamiento", "orden": 2},
                {"de": "D2", "a_pos": {"x": 38, "y": 38}, "tipo": "desplazamiento", "orden": 3},
                {"de": "A1", "tipo": "tiro", "orden": 4}
            ],
            "conos": []
        }
    },
    {
        "id": "ej_053",
        "nombre": "Winchester — 5 cierres defensivos consecutivos",
        "categoria": "1c1",
        "subcategoria": "defensa_individual",
        "edades": ["U16", "U18", "Senior"],
        "duracion_min": 12,
        "intensidad": 5,
        "carga_cognitiva": 4,
        "jugadores_minimos": 2,
        "fuente": "isportcoach.com",
        "objetivos": {
            "tacticos": ["close-out defensivo bajo fatiga", "defensa 1c1 encadenada"],
            "tecnicos": ["cierre defensivo (close-out) con manos activas", "posición defensiva tras el cierre", "técnica vertical en el ataque"],
            "fisicos": ["resistencia anaeróbica", "velocidad de desplazamiento repetida"]
        },
        "puntos_clave": [
            "El defensor cierra en arco, no en línea recta: llegar ligeramente adelantado para forzar el cambio de dirección.",
            "Tras el cierre: manos arriba para dificultar el tiro, posición de defensa con los pies activos. No apoyarse en el atacante.",
            "El atacante usa técnica vertical: elevarse hacia arriba protegiendo el balón, no hacia el defensor.",
            "La fatiga acumulada en el 4.º y 5.º cierre es la clave del ejercicio: mantener la técnica cuando el cuerpo ya está cargado.",
            "VARIANTE: limitar botes del atacante (máximo 2) para acelerar la decisión y aumentar la presión."
        ],
        "descripcion": (
            "ORGANIZACIÓN: A1 (atacante) en posición con balón. D1 (defensor) en el punto de tiro libre o en el lateral, según la posición de A1. "
            "SECUENCIA: D1 hace 5 cierres consecutivos sobre A1 sin parar. "
            "Cada cierre: D1 retrocede 4-5 pasos, A1 se reposiciona, D1 cierra en sprint. "
            "Tras cada cierre, A1 ataca el 1c1 (máx. 2 botes). Si A1 anota o no anota, el siguiente cierre comienza inmediatamente. "
            "Tras 5 cierres seguidos, A1 y D1 descansan 30 s y se cambian roles. "
            "COMPETICIÓN: D1 suma 1 punto por cada 1c1 parado. A1 suma 1 por cada canasta. "
            "Quien más puntos sume en 3 tandas de 5 gana. "
            "PROGRESIÓN: 3 cierres → 5 → 7. Limitar botes del atacante."
        ),
        "diagrama": {
            "tipo": "media_pista",
            "jugadores_ataque": [
                {"id": "A1", "x": 35, "y": 50}
            ],
            "jugadores_defensa": [
                {"id": "D1", "x": 50, "y": 65}
            ],
            "balon_inicio": {"portador": "A1"},
            "movimientos": [
                {"de": "D1", "a_pos": {"x": 32, "y": 47}, "tipo": "desplazamiento", "orden": 1},
                {"de": "A1", "a_pos": {"x": 25, "y": 35}, "tipo": "bote", "orden": 2},
                {"de": "A1", "tipo": "tiro", "orden": 3}
            ],
            "conos": []
        }
    },
    {
        "id": "ej_054",
        "nombre": "3/4 de pista — 1c1 a campo abierto con persecución",
        "categoria": "1c1",
        "subcategoria": "penetracion",
        "edades": ["U14", "U16", "U18", "Senior"],
        "duracion_min": 10,
        "intensidad": 5,
        "carga_cognitiva": 3,
        "jugadores_minimos": 2,
        "fuente": "isportcoach.com",
        "objetivos": {
            "tacticos": ["ataque en campo abierto", "defensa en persecución a campo abierto"],
            "tecnicos": ["bote de velocidad", "primer paso defensivo en sprint", "finalización bajo fatiga"],
            "fisicos": ["sprint", "resistencia a la velocidad"]
        },
        "puntos_clave": [
            "El atacante sale en ventaja de campo: el defensor no puede adelantarse, solo perseguir.",
            "El atacante no espera al defensor — ataca el aro directamente desde que toca el balón.",
            "El defensor persigue en sprint intentando llegar al menos en posición de molestia antes de la finalización.",
            "La defensa en persecución no salta al defensor — llega, orienta el aro y presiona el tiro.",
            "ROTACIÓN: dos filas. Fila atacante con balón, fila defensora sin balón. Atacante pasa a defensor, defensor a cola de atacantes."
        ],
        "descripcion": (
            "ORGANIZACIÓN: dos filas en la línea de medio campo — fila de atacantes (A1, con balones) "
            "y fila de defensores (D1, sin balón) a 1-2 metros por detrás. "
            "SECUENCIA: el entrenador pita. A1 arranca en sprint hacia la canasta contraria botando. "
            "D1 sale a perseguir inmediatamente, sin ventaja de posición. "
            "A1 ataca el aro sin ralentizar. D1 intenta llegar antes de la finalización para complicar el tiro. "
            "Terminada la acción, A1 pasa a la fila de defensores, D1 a la fila de atacantes. "
            "COMPETICIÓN: cuenta cuántos cierres llega D1 antes de que A1 lance. "
            "PROGRESIÓN: D1 sale 0.5 s antes (ventaja) → simultáneo → D1 sale 0.5 s después (desventaja)."
        ),
        "diagrama": {
            "tipo": "pista_completa",
            "jugadores_ataque": [
                {"id": "A1", "x": 50, "y": 50}
            ],
            "jugadores_defensa": [
                {"id": "D1", "x": 50, "y": 55}
            ],
            "balon_inicio": {"portador": "A1"},
            "movimientos": [
                {"de": "A1", "a_pos": {"x": 50, "y": 88}, "tipo": "bote", "orden": 1},
                {"de": "D1", "a_pos": {"x": 50, "y": 75}, "tipo": "desplazamiento", "orden": 2},
                {"de": "A1", "tipo": "tiro", "orden": 3}
            ],
            "conos": []
        }
    },
    {
        "id": "ej_055",
        "nombre": "2c2 con hándicap — superioridad que se cierra",
        "categoria": "ventaja_numerica",
        "subcategoria": "superioridad",
        "edades": ["U14", "U16", "U18", "Senior"],
        "duracion_min": 12,
        "intensidad": 4,
        "carga_cognitiva": 5,
        "jugadores_minimos": 4,
        "fuente": "isportcoach.com",
        "objetivos": {
            "tacticos": ["explotar ventaja 2c1 antes de que se iguale", "transición defensiva urgente", "rotación continua"],
            "tecnicos": ["decisión en 2c1 con tiempo limitado", "repliegue defensivo en sprint", "comunicación defensiva al igualarse"],
            "fisicos": ["sprint", "resistencia"]
        },
        "puntos_clave": [
            "Los atacantes tienen ventaja 2c1 solo hasta que D2 toca la línea de fondo y se incorpora. Hay que aprovecharla ANTES.",
            "D1 gana tiempo retrocediendo sin comprometerse: no saltar al pase, no saltar al bote. Obligar a los atacantes a decidir mal.",
            "Cuando D2 llega y comunica, D1 deja el balón y va a su marcaje. La comunicación es obligatoria.",
            "Si los atacantes no finalizaron en 2c1, ahora es 2c2 normal. Los defensores asumen sus marcajes.",
            "ROTACIÓN: ataque → defensa → descanso → ataque. El último defensor que llega siempre hace el sprint del lateral."
        ],
        "descripcion": (
            "ORGANIZACIÓN: A1 y A2 en el perímetro con balón. D1 en posición defensiva retrasada. "
            "D2 en la línea de fondo lateral, fuera de la pista. "
            "SECUENCIA: A1 y A2 atacan 2c1 contra D1 en media pista. "
            "Simultáneamente, D2 toca la línea de fondo y hace sprint para incorporarse. "
            "Los atacantes deben finalizar antes de que D2 llegue. "
            "Si D2 llega → 2c2 normal. "
            "ROTACIÓN: A1 y A2 pasan a defender; D1 pasa a la fila de atacantes; D2 pasa a la fila de D1. "
            "El jugador nuevo de la fila hace el sprint lateral como D2."
        ),
        "diagrama": {
            "tipo": "media_pista",
            "jugadores_ataque": [
                {"id": "A1", "x": 50, "y": 75},
                {"id": "A2", "x": 10, "y": 75}
            ],
            "jugadores_defensa": [
                {"id": "D1", "x": 50, "y": 45},
                {"id": "D2", "x": 0,  "y": 85}
            ],
            "balon_inicio": {"portador": "A1"},
            "movimientos": [
                {"de": "A1", "a_pos": {"x": 50, "y": 52}, "tipo": "bote", "orden": 1},
                {"de": "A2", "a_pos": {"x": 10, "y": 30}, "tipo": "desplazamiento", "orden": 2},
                {"de": "D2", "a_pos": {"x": 60, "y": 38}, "tipo": "desplazamiento", "orden": 3},
                {"de": "A1", "a": "A2", "tipo": "pase", "orden": 4},
                {"de": "A2", "tipo": "tiro", "orden": 5}
            ],
            "conos": []
        }
    },
    {
        "id": "ej_056",
        "nombre": "Palomero — 3c2 continuo con rotación",
        "categoria": "ventaja_numerica",
        "subcategoria": "contraataque",
        "edades": ["U14", "U16", "U18", "Senior"],
        "duracion_min": 15,
        "intensidad": 5,
        "carga_cognitiva": 4,
        "jugadores_minimos": 6,
        "fuente": "isportcoach.com",
        "objetivos": {
            "tacticos": ["3c2 continuo", "balance defensivo inmediato", "cambio de roles ataque-defensa sin pausa"],
            "tecnicos": ["toma de decisión en 3c2", "repliegue defensivo", "asignación de marcajes en transición"],
            "fisicos": ["resistencia a esfuerzo continuo", "sprint repetido"]
        },
        "puntos_clave": [
            "El 'palomero' es el último atacante que tocó el balón: se queda a defender solo al finalizar la posesión.",
            "Los dos defensores originales pasan inmediatamente al ataque hacia la canasta contraria en cuanto la posesión termina.",
            "Los dos nuevos atacantes de la fila se suman al nuevo 3c2 en dirección contraria.",
            "El palomero no corre a la otra canasta — se queda y defiende el siguiente 3c2 que viene hacia él.",
            "La intensidad viene del encadenamiento sin pausa: al terminar una posesión, la siguiente empieza inmediatamente."
        ],
        "descripcion": (
            "ORGANIZACIÓN: dos filas en la línea de fondo (A4, A5...) y 3 atacantes (A1, A2, A3) + 2 defensores (D1, D2) en pista. "
            "SECUENCIA: A1, A2, A3 atacan 3c2 contra D1 y D2 en una canasta. "
            "Al terminar la posesión (canasta, robo o salida): "
            "(1) D1 y D2 pasan a ser atacantes hacia la canasta contraria. "
            "(2) El último de A1/A2/A3 que tocó el balón (el 'palomero') se queda a defender solo. "
            "(3) Dos nuevos jugadores de la fila (A4, A5) salen como los otros dos atacantes para completar el 3c2 en la dirección contraria. "
            "ROTACIÓN: el palomero va a la fila al terminar su defensa. "
            "El flujo es continuo — ningún jugador para durante el ejercicio."
        ),
        "diagramas": [
            {
                "titulo": "Fase 1 — A1/A2/A3 atacan 3c2 en la canasta izquierda",
                "tipo": "pista_completa",
                "jugadores_ataque": [
                    {"id": "A1", "x": 50, "y": 15},
                    {"id": "A2", "x": 10, "y": 15},
                    {"id": "A3", "x": 90, "y": 15}
                ],
                "jugadores_defensa": [
                    {"id": "D1", "x": 38, "y": 8},
                    {"id": "D2", "x": 62, "y": 8}
                ],
                "balon_inicio": {"portador": "A1"},
                "movimientos": [
                    {"de": "A1", "a_pos": {"x": 50, "y": 8}, "tipo": "bote", "orden": 1},
                    {"de": "A2", "a_pos": {"x": 10, "y": 5}, "tipo": "desplazamiento", "orden": 2},
                    {"de": "A1", "a": "A2", "tipo": "pase", "orden": 3},
                    {"de": "A2", "tipo": "tiro", "orden": 4}
                ],
                "conos": []
            },
            {
                "titulo": "Fase 2 — D1/D2 atacan 3c2 en la canasta contraria; A3 queda como palomero",
                "tipo": "pista_completa",
                "jugadores_ataque": [
                    {"id": "A1", "x": 10, "y": 12},
                    {"id": "A2", "x": 90, "y": 12},
                    {"id": "A3", "x": 50, "y": 88}
                ],
                "jugadores_defensa": [
                    {"id": "D1", "x": 38, "y": 92},
                    {"id": "D2", "x": 62, "y": 92}
                ],
                "balon_inicio": {"portador": "A1"},
                "movimientos": [
                    {"de": "A1", "a_pos": {"x": 50, "y": 85}, "tipo": "bote", "orden": 1},
                    {"de": "A2", "a_pos": {"x": 90, "y": 88}, "tipo": "desplazamiento", "orden": 2},
                    {"de": "A3", "a_pos": {"x": 50, "y": 95}, "tipo": "desplazamiento", "orden": 3}
                ],
                "conos": []
            }
        ]
    },
    {
        "id": "ej_057",
        "nombre": "Circus — 3c3 defensa de comunicación y rotaciones",
        "categoria": "juego_equipo",
        "subcategoria": "defensa",
        "edades": ["U16", "U18", "Senior"],
        "duracion_min": 12,
        "intensidad": 4,
        "carga_cognitiva": 5,
        "jugadores_minimos": 6,
        "fuente": "isportcoach.com",
        "objetivos": {
            "tacticos": ["defensa de perímetro con rotaciones", "comunicación defensiva", "presión al balón en sistema"],
            "tecnicos": ["posición defensiva de presión al balón", "negación del pase", "rotación sin perder referencias"],
            "fisicos": ["desplazamiento defensivo continuo"]
        },
        "puntos_clave": [
            "Los defensores no mantienen sus emparejamientos iniciales — rotan según la señal del entrenador, no según el movimiento del balón.",
            "La comunicación es constante y obligatoria: '¡balón!', '¡ayuda!', '¡cambio!' antes de cada movimiento defensivo.",
            "El defensor del balón presiona siempre. Los otros dos asumen posición de ayuda según donde está el balón.",
            "Al rotar, el que salía de la ayuda pasa a presionar balón y el que presionaba pasa a ayuda — sin interrupciones.",
            "Los atacantes pasan el balón de perímetro sin botar para forzar las rotaciones defensivas continuamente."
        ],
        "descripcion": (
            "ORGANIZACIÓN: A1, A2, A3 en el perímetro (cabecera y dos alas) con balón. "
            "D1, D2, D3 defienden 3c3 en el perímetro. "
            "SECUENCIA: los atacantes circulan el balón por el perímetro (sin botar, solo pases). "
            "Los defensores presionan según la posición del balón y comunican sus rotaciones. "
            "Cuando el entrenador pita, los defensores deben cambiar de emparejamiento en rotación (D1→D2→D3→D1) "
            "sin perder la presión al balón en ningún momento. "
            "Si la comunicación falla y un atacante recibe en posición de ventaja → puede atacar. "
            "ROTACIÓN de equipos: el trío defensor que encaja 3 canastas sale; entra el siguiente grupo. "
            "PROGRESIÓN: añadir cortes de los atacantes (pase y corte al aro) para forzar cambios y rotaciones más complejas."
        ),
        "diagrama": {
            "tipo": "media_pista",
            "jugadores_ataque": [
                {"id": "A1", "x": 50, "y": 65},
                {"id": "A2", "x": 25, "y": 50},
                {"id": "A3", "x": 75, "y": 50}
            ],
            "jugadores_defensa": [
                {"id": "D1", "x": 50, "y": 57},
                {"id": "D2", "x": 25, "y": 43},
                {"id": "D3", "x": 75, "y": 43}
            ],
            "balon_inicio": {"portador": "A1"},
            "movimientos": [
                {"de": "A1", "a": "A2", "tipo": "pase", "orden": 1},
                {"de": "A2", "a": "A3", "tipo": "pase", "orden": 2},
                {"de": "D1", "a_pos": {"x": 30, "y": 45}, "tipo": "desplazamiento", "orden": 3},
                {"de": "D2", "a_pos": {"x": 72, "y": 43}, "tipo": "desplazamiento", "orden": 4}
            ],
            "conos": []
        }
    },
    {
        "id": "ej_058",
        "nombre": "Shell Drill — 4c4 posiciones defensivas de media pista",
        "categoria": "juego_equipo",
        "subcategoria": "defensa",
        "edades": ["U16", "U18", "Senior"],
        "duracion_min": 15,
        "intensidad": 3,
        "carga_cognitiva": 5,
        "jugadores_minimos": 8,
        "fuente": "isportcoach.com",
        "objetivos": {
            "tacticos": ["posiciones defensivas correctas según lado del balón", "negación del pase y posición de ayuda", "defensa colectiva de media pista"],
            "tecnicos": ["posición ball-you-man", "negación activa", "defensa de cortes"],
            "fisicos": ["desplazamiento defensivo continuo"]
        },
        "puntos_clave": [
            "Ball-you-man: siempre en la línea imaginaria entre el balón y tu marcaje. Si el balón cambia de lado, tu posición cambia.",
            "Lado del balón (on-ball): presión directa con manos activas. Lado contrario (help side): posición de ayuda en el carril del aro.",
            "Niega los pases directos al lado del balón. Permite los pases de lado contrario (más lentos, más fáciles de interceptar).",
            "Al cortar el atacante: decide si seguirlo (if below the ball) o cedérselo a un compañero y comunicarlo.",
            "El ejercicio lo dirige el entrenador pitando para que los atacantes pasen — sin atacar al aro hasta la señal."
        ],
        "descripcion": (
            "ORGANIZACIÓN: cuatro posiciones base de ataque — A1 en cabecera, A2 en ala derecha, A3 en ala izquierda, A4 en poste bajo. "
            "D1, D2, D3, D4 defienden en las posiciones correctas según el balón. "
            "SECUENCIA PROGRESIVA: "
            "(1) Solo pases, sin bote ni ataques: los atacantes circulan el balón y los defensores ajustan posición en cada pase. "
            "(2) Añadir bote: los atacantes pueden botar, los defensores trabajan la presión y el 'on-ball'. "
            "(3) Añadir cortes: los atacantes sin balón pueden cortar al aro; los defensores deben decidir si seguirlos o cederlos. "
            "(4) 4c4 live: los atacantes pueden atacar cuando quieran. "
            "El entrenador para el ejercicio cuando la posición defensiva colectiva sea incorrecta y corrige en el sitio. "
            "ROTACIÓN: tras cada tanda de 2 minutos, ataque y defensa se intercambian roles."
        ),
        "diagrama": {
            "tipo": "media_pista",
            "jugadores_ataque": [
                {"id": "A1", "x": 50, "y": 65},
                {"id": "A2", "x": 25, "y": 50},
                {"id": "A3", "x": 75, "y": 50},
                {"id": "A4", "x": 38, "y": 18}
            ],
            "jugadores_defensa": [
                {"id": "D1", "x": 50, "y": 57},
                {"id": "D2", "x": 32, "y": 40},
                {"id": "D3", "x": 62, "y": 38},
                {"id": "D4", "x": 44, "y": 24}
            ],
            "balon_inicio": {"portador": "A1"},
            "movimientos": [
                {"de": "A1", "a": "A2", "tipo": "pase", "orden": 1},
                {"de": "D1", "a_pos": {"x": 32, "y": 53}, "tipo": "desplazamiento", "orden": 2},
                {"de": "D2", "a_pos": {"x": 25, "y": 43}, "tipo": "desplazamiento", "orden": 3},
                {"de": "D3", "a_pos": {"x": 55, "y": 35}, "tipo": "desplazamiento", "orden": 4}
            ],
            "conos": []
        }
    },
]


def main():
    with open(SRC, encoding="utf-8") as f:
        data = json.load(f)

    ids_existentes = {ex["id"] for ex in data}
    añadidos = 0
    for ex in NUEVOS:
        if ex["id"] in ids_existentes:
            print(f"  Saltado (ya existe): {ex['id']}")
        else:
            data.append(ex)
            print(f"  Añadido {ex['id']}: {ex['nombre']}")
            añadidos += 1

    with open(SRC, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # Verificar JSON
    with open(SRC, encoding="utf-8") as f:
        check = json.load(f)
    print(f"\nOK — {añadidos} nuevos ejercicios. Total: {len(check)} ejercicios.")


if __name__ == "__main__":
    main()
