# tests/test_cabecera_en_negrita.py
"""Si el modelo escribe la cabecera de un ejercicio en negrita («**Ejercicio 3: nombre**»), el ejercicio se conserva.
Antes se tomaba por «abrió otra sección» y se tiraba un ejercicio entero y válido: la sesión salía con un hueco."""
import sesion
from bloques import extraer_bloques, nombre_de_cabecera

BLOQUE = ("{cab}\n\nDuración: 10 min\nOrganización:\ntres jugadores con un balón se pasan en movimiento por la banda.\n"
          "Puntos clave:\n- Mirar antes de pasar.\n- Pasar al espacio.\n")


def test_extraer_bloques_reconoce_la_cabecera_en_negrita():
    texto = "Ejercicio 2: Uno\nDuración: 10 min\n\n" + BLOQUE.format(cab="**Ejercicio 3: Pase en movimiento por la banda**")
    bloques = extraer_bloques(texto)
    assert set(bloques) == {"ej:2", "ej:3"}
    assert nombre_de_cabecera(bloques["ej:3"]) == "Pase en movimiento por la banda"


def test_un_hueco_cuyo_ejercicio_llega_con_cabecera_en_negrita_no_se_pierde(monkeypatch):
    for cabecera in ("**Ejercicio 3: Pase en movimiento por la banda**", "Ejercicio 3: **Pase en movimiento por la banda**",
                     "Ejercicio 3: Pase en movimiento por la banda"):
        monkeypatch.setattr(sesion, "_pedir_texto_sesion",
                            lambda prompt, num_predict, num_ctx, parar_en=(), c=cabecera: (BLOQUE.format(cab=c), None))
        huecos = [sesion._Hueco(3, None, 10, 0, None, 1)]
        texto = sesion._completar_apartados("PROMPT\n", "Ejercicio 2: Uno\nDuración: 10 min\n", huecos,
                                            {"ej:3": "Ejercicio 3:"}, 6144)
        bloques = extraer_bloques(texto)
        assert "ej:3" in bloques, cabecera
        assert "Mirar antes de pasar" in bloques["ej:3"], cabecera
