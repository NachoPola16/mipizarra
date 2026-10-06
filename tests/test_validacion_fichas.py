# tests/test_validacion_fichas.py
"""Filtro automático de fichas de ejercicio: rechaza solo lo que incumple reglas objetivas (esquema, edades, líneas
rojas, terminología, diagrama válido). Es la primera barrera de los candidatos antes de que nadie los lea."""
import copy

import pytest

from validacion_fichas import validar_ficha

FICHA_OK = {
    "id": "ej_901", "nombre": "Pase y recepción por parejas", "categoria": "juego_equipo",
    "subcategoria": "pase", "edades": ["U8", "U10", "U12"], "duracion_min": 10, "intensidad": 2,
    "carga_cognitiva": 2, "jugadores_minimos": 4,
    "objetivos": {"tacticos": ["pase y recepción"], "tecnicos": ["pase de pecho"], "fisicos": []},
    "puntos_clave": ["Mirar al compañero antes de pasar.", "Dar la mano de apoyo al recibir."],
    "descripcion": "ORGANIZACIÓN: parejas enfrentadas a tres metros, un balón por pareja. SECUENCIA: se pasan el balón "
                   "con pase de pecho y dan un paso atrás cada cinco pases. ROTACIÓN: cada minuto se cambia de pareja.",
}


def _ficha(**cambios):
    f = copy.deepcopy(FICHA_OK)
    f.update(cambios)
    return f


def _problemas(ficha, biblioteca=()):
    return validar_ficha(ficha, biblioteca)


def test_una_ficha_correcta_no_tiene_problemas():
    assert _problemas(FICHA_OK) == []


def test_las_fichas_actuales_de_la_biblioteca_pasan_el_filtro(ejercicios):
    # auditoría: el filtro no puede ser más estricto que lo que ya está aceptado en la biblioteca
    for ficha in ejercicios:
        otras = [e for e in ejercicios if e["id"] != ficha["id"]]
        assert _problemas(ficha, otras) == [], ficha["id"]


@pytest.mark.parametrize("campo", ["id", "nombre", "categoria", "edades", "duracion_min", "intensidad",
                                   "carga_cognitiva", "objetivos", "descripcion", "puntos_clave"])
def test_cada_campo_obligatorio_se_exige(campo):
    f = copy.deepcopy(FICHA_OK)
    del f[campo]
    assert any(campo in p for p in _problemas(f))


def test_lo_que_no_es_un_diccionario_se_rechaza():
    assert _problemas("texto") and _problemas(None)


def test_el_id_tiene_el_formato_de_la_biblioteca_y_no_se_repite():
    assert any("id" in p for p in _problemas(_ficha(id="ejercicio uno")))
    assert any("repetido" in p for p in _problemas(_ficha(id="ej_001"), [{"id": "ej_001", "nombre": "Otro"}]))


def test_el_nombre_no_puede_estar_repetido_aunque_cambien_mayusculas_o_tildes():
    otra = {"id": "ej_002", "nombre": "PASE Y RECEPCION POR PAREJAS"}
    assert any("nombre" in p and "repetido" in p for p in _problemas(FICHA_OK, [otra]))


@pytest.mark.parametrize("cambios", [
    {"categoria": "inventada"}, {"edades": []}, {"edades": ["U20"]}, {"duracion_min": 4}, {"duracion_min": 45},
    {"duracion_min": "10"}, {"intensidad": 0}, {"intensidad": 6}, {"carga_cognitiva": 9},
])
def test_valores_fuera_de_rango_o_de_la_lista_se_rechazan(cambios):
    assert _problemas(_ficha(**cambios))


def test_las_duraciones_reales_de_la_biblioteca_valen_aunque_no_sean_multiplo_de_5():
    for minutos in (6, 8, 12, 15):
        assert _problemas(_ficha(duracion_min=minutos)) == []


def test_un_ejercicio_tecnico_sin_objetivo_tactico_es_valido_pero_sin_ningun_objetivo_no():
    assert _problemas(_ficha(objetivos={"tacticos": [], "tecnicos": ["bote de protección"], "fisicos": []})) == []
    assert any("objetivos" in p for p in _problemas(_ficha(objetivos={"tacticos": [], "tecnicos": [], "fisicos": []})))


def test_el_diagrama_de_una_ficha_curada_no_se_juzga_por_el_recuento_del_nombre():
    # «1c1» con un pasador sin defensor es un patrón legítimo de la biblioteca
    pasador = dict(DIAGRAMA_OK, jugadores_defensa=[])
    assert _problemas(_ficha(nombre="Pasador y 1c1 con salida", diagrama=pasador)) == []


def test_la_descripcion_no_puede_ser_una_frase_suelta():
    assert any("descripcion" in p for p in _problemas(_ficha(descripcion="Pasar el balón.")))


@pytest.mark.parametrize("puntos", [[], ["uno"], ["a", "b", "c", "d", "e", "f", "g", "h"], ["bien", ""], ["bien", 3]])
def test_los_puntos_clave_son_de_2_a_7_textos_no_vacios(puntos):
    assert any("puntos_clave" in p for p in _problemas(_ficha(puntos_clave=puntos)))


def test_una_linea_roja_de_minibasket_se_rechaza_en_la_ficha_de_esa_edad():
    f = _ficha(descripcion=FICHA_OK["descripcion"] + " Después hacen un bloqueo directo con el pívot.")
    assert any("línea roja" in p and "bloqueo" in p for p in _problemas(f))


def test_negar_una_linea_roja_en_la_ficha_no_es_un_problema():
    f = _ficha(descripcion=FICHA_OK["descripcion"] + " Sin bloqueos ni pantallas en esta etapa.")
    assert not any("línea roja" in p for p in _problemas(f))


def test_la_misma_frase_no_es_linea_roja_en_una_ficha_de_cadete():
    f = _ficha(edades=["U16"], descripcion=FICHA_OK["descripcion"] + " Después hacen un bloqueo directo.")
    assert not any("línea roja" in p for p in _problemas(f))


@pytest.mark.parametrize("edades,categoria", [(["U10"], "bloqueo_directo"), (["U12"], "bloqueo_indirecto"),
                                             (["U14"], "bloqueo_directo")])
def test_las_categorias_de_bloqueo_no_van_en_edades_que_no_las_trabajan(edades, categoria):
    assert any("bloqueo" in p for p in _problemas(_ficha(edades=edades, categoria=categoria)))


@pytest.mark.parametrize("palabra", ["Fuente: un libro", "sacado del manual.pdf", "una pantalla al tirador"])
def test_terminologia_y_procedencia_prohibidas(palabra):
    f = _ficha(puntos_clave=[palabra, "Mirar al compañero."])
    assert any("prohibido" in p.lower() for p in _problemas(f))


DIAGRAMA_OK = {
    "tipo": "media_pista",
    "jugadores_ataque": [{"id": "A1", "x": 30, "y": 60}, {"id": "A2", "x": 70, "y": 60}],
    "jugadores_defensa": [], "balon_inicio": {"portador": "A1"},
    "movimientos": [{"de": "A1", "tipo": "pase", "a": "A2", "orden": 1}], "conos": [],
}


def test_un_diagrama_valido_pasa_y_se_dibuja():
    assert _problemas(_ficha(diagrama=DIAGRAMA_OK)) == []


def test_un_diagrama_con_referencias_rotas_se_rechaza():
    roto = copy.deepcopy(DIAGRAMA_OK)
    roto["movimientos"][0]["a"] = "A9"
    assert any("diagrama" in p for p in _problemas(_ficha(diagrama=roto)))


def test_un_diagrama_con_coordenadas_fuera_de_la_pista_se_rechaza():
    fuera = copy.deepcopy(DIAGRAMA_OK)
    fuera["jugadores_ataque"][0]["x"] = 140
    assert any("diagrama" in p and "coordenadas" in p for p in _problemas(_ficha(diagrama=fuera)))


def test_los_diagramas_por_fases_se_validan_todos():
    roto = copy.deepcopy(DIAGRAMA_OK)
    roto["balon_inicio"] = {"portador": "A7"}
    f = _ficha(diagramas=[dict(DIAGRAMA_OK, titulo="Fase 1"), dict(roto, titulo="Fase 2")])
    assert any("diagrama" in p for p in _problemas(f))


@pytest.mark.parametrize("campo,valor", [("material", ""), ("consigna", 3), ("errores_frecuentes", []),
                                         ("que_observar", ["", "x"]), ("progresion", {"facilitar": ""}),
                                         ("progresion", {"otra": "x"})])
def test_los_campos_opcionales_si_estan_tienen_la_forma_correcta(campo, valor):
    assert any(campo in p for p in _problemas(_ficha(**{campo: valor})))


def test_se_devuelven_todos_los_problemas_a_la_vez():
    f = _ficha(categoria="inventada", duracion_min=45, puntos_clave=[])
    assert len(_problemas(f)) >= 3
