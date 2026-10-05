# tests/test_parseo_sesion.py
"""parsear_ejercicios_de_sesion y parsear_calentamiento_y_vuelta (api/main.py)
con sesiones sintéticas que siguen la plantilla de generar_sesion."""
from main import parsear_calentamiento_y_vuelta, parsear_ejercicios_de_sesion

SESION_SIMPLE = """\
**CALENTAMIENTO (15 min)**
Juego: Pañuelo con balón
Reglas: Dos equipos numerados; al oír su número, cada jugador sale botando a por el balón central.
Espacio: Media pista.

**PARTE PRINCIPAL**

Ejercicio 1: Rueda de bote y bandeja
Duración: 20 min
Organización: Dos filas en el medio campo. El primero de cada fila sale botando con mano derecha y finaliza en bandeja.
Puntos clave:
- Mirada arriba durante el bote.
- Último bote fuerte antes de la batida.

Ejercicio 2: 2c1 desde medio campo
Duración: 20 min
Organización: A1 y A2 atacan contra D1, que espera en el codo.
Puntos clave:
- Fijar al defensor antes de pasar.
- Ocupar carriles separados.

**DESCANSO (3 min)**

Ejercicio 3: 3c3 en media pista
Duración: 20 min
Organización: Tres atacantes contra tres defensores; prohibido botar más de dos veces.
Puntos clave:
- Pasar y cortar.
- Ayuda y recuperación.

**VUELTA A LA CALMA (5 min)**
Juego: Tiros libres por parejas
Reglas: Cada pareja suma canastas; estiramientos entre tandas.

**Fundamentos**: bote de protección, pase picado, bandeja con mano dominante."""


SESION_CON_VARIANTES = """\
**CALENTAMIENTO (10 min)**
Juego: Cazadores
Reglas: Dos cazadores sin balón persiguen a los demás, que botan dentro de media pista.
Espacio: Media pista.

**PARTE PRINCIPAL**

Ejercicio 1.1: Bote con cambio de mano entre conos
Duración: 10 min
Organización: Fila en la línea de fondo; cada jugador bota en zigzag entre conos.
Puntos clave:
- Cambio de mano por delante, bajo.
-

Ejercicio 1.2 (variante de "Bote con cambio de mano entre conos" — mismo ejercicio con un cambio o regla nueva, no lo repitas igual):
Duración: 5 min
Qué cambia respecto a 1.1: Se añade un defensor pasivo en el último cono.
Organización: Igual que 1.1, pero al llegar al último cono el defensor intenta tocar el balón.
Puntos clave:
- Proteger el balón con el cuerpo.

Ejercicio 2.1: 1c1 desde el 45°
Duración: 10 min
Organización: Atacante recibe en el 45° con un defensor delante.
Puntos clave:
- Salida cruzada.

Ejercicio 2.2 (variante de "1c1 desde el 45°" — mismo ejercicio con un cambio o regla nueva, no lo repitas igual):
Duración: 5 min
Qué cambia respecto a 2.1:
Organización: El defensor empieza con desventaja tocando la línea de fondo.
Puntos clave:
- Atacar el pie adelantado.

**DESCANSO (3 min)**

Ejercicio 3: 2c2 con bote limitado
Duración: 15 min
Organización: Dos contra dos en media pista, máximo tres botes por posesión.
Puntos clave:
- Pase y corte.

**VUELTA A LA CALMA (5 min)**
Juego: Concurso de tiro libre
Reglas: Cada acierto suma un punto para su equipo.

**Fundamentos**: bote de protección, cambio de mano, salida cruzada."""


def test_sesion_simple_tres_ejercicios():
    ejs = parsear_ejercicios_de_sesion(SESION_SIMPLE)
    assert [e["nombre"] for e in ejs] == [
        "Rueda de bote y bandeja",
        "2c1 desde medio campo",
        "3c3 en media pista",
    ]


def test_organizacion_sin_puntos_clave_ni_duracion():
    ejs = parsear_ejercicios_de_sesion(SESION_SIMPLE)
    assert ejs[0]["descripcion"].startswith("Dos filas en el medio campo.")
    assert "finaliza en bandeja" in ejs[0]["descripcion"]
    for ej in ejs:
        assert "Puntos clave" not in ej["descripcion"]
        assert "Duración" not in ej["descripcion"]


def test_ultimo_ejercicio_no_absorbe_secciones_por_falta_de_marcador():
    """El 3.º ejercicio se corta en 'Puntos clave:' y no arrastra la vuelta a la calma."""
    desc = parsear_ejercicios_de_sesion(SESION_SIMPLE)[2]["descripcion"]
    assert "VUELTA A LA CALMA" not in desc
    assert "Fundamentos" not in desc


def test_variantes_n1_n2():
    ejs = parsear_ejercicios_de_sesion(SESION_CON_VARIANTES)
    assert [e["nombre"] for e in ejs] == [
        "Bote con cambio de mano entre conos",
        "Bote con cambio de mano entre conos",
        "1c1 desde el 45°",
        "1c1 desde el 45°",
        "2c2 con bote limitado",
    ]


def test_variante_incluye_que_cambia():
    ejs = parsear_ejercicios_de_sesion(SESION_CON_VARIANTES)
    base, variante = ejs[0], ejs[1]
    assert not base["descripcion"].startswith("Cambio respecto")
    assert variante["descripcion"].startswith(
        "Cambio respecto al ejercicio base: Se añade un defensor pasivo en el último cono."
    )
    # La organización de la variante sigue presente tras el cambio.
    assert "el defensor intenta tocar el balón" in variante["descripcion"]
    # No se duplica el punto final del cambio.
    assert ".." not in variante["descripcion"]


def test_variante_con_que_cambia_vacio_no_anade_prefijo():
    variante = parsear_ejercicios_de_sesion(SESION_CON_VARIANTES)[3]
    assert not variante["descripcion"].startswith("Cambio respecto")
    assert variante["descripcion"].startswith("El defensor empieza con desventaja")


def test_cabecera_sin_nombre_en_la_misma_linea_se_ignora():
    texto = "Ejercicio 1:\nDuración: 10 min\nOrganización: algo.\n"
    assert parsear_ejercicios_de_sesion(texto) == []


def test_nombre_entre_comillas_se_limpia():
    texto = 'Ejercicio 1: "Rueda de tiro"\nDuración: 10 min\nOrganización: Tiro desde el codo.\n'
    ejs = parsear_ejercicios_de_sesion(texto)
    assert ejs == [{"nombre": "Rueda de tiro", "descripcion": "Tiro desde el codo."}]


def test_sin_organizacion_descripcion_vacia():
    texto = "Ejercicio 1: Rueda de tiro\nDuración: 10 min\nPuntos clave:\n- Codo alineado.\n"
    assert parsear_ejercicios_de_sesion(texto) == [{"nombre": "Rueda de tiro", "descripcion": ""}]


def test_texto_sin_ejercicios():
    assert parsear_ejercicios_de_sesion("") == []
    assert parsear_ejercicios_de_sesion("**Error generando sesión**: timeout") == []


def test_calentamiento_y_vuelta_a_la_calma():
    extras = parsear_calentamiento_y_vuelta(SESION_SIMPLE)
    assert [e["nombre"] for e in extras] == [
        "Calentamiento: Pañuelo con balón",
        "Vuelta a la calma: Tiros libres por parejas",
    ]
    assert extras[0]["descripcion"].startswith("Dos equipos numerados")
    assert "Espacio" not in extras[0]["descripcion"]
    assert "Fundamentos" not in extras[1]["descripcion"]


def test_calentamiento_sin_juego_se_omite():
    texto = "**CALENTAMIENTO (10 min)**\nMovilidad articular libre.\n\n**PARTE PRINCIPAL**\n"
    assert parsear_calentamiento_y_vuelta(texto) == []
