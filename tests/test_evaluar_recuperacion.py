# tests/test_evaluar_recuperacion.py
"""tools/evaluar_recuperacion.py: las funciones puras que miden la recuperación."""
import importlib.util

import pytest

from conftest import RAIZ

_spec = importlib.util.spec_from_file_location("evaluar_recuperacion", RAIZ / "tools" / "evaluar_recuperacion.py")
er = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(er)


def test_contiene_ignora_mayusculas_y_tildes():
    assert er.contiene("Se restablecen 14 SEGUNDOS", ["14 segundos"])
    assert er.contiene("El semicirculo de no carga", ["semicírculo"])
    assert not er.contiene("El reloj de 24 segundos", ["14 segundos"])


def test_rango_es_la_posicion_del_primer_fragmento_que_responde():
    fragmentos = ["nada", "tampoco", "8 segundos para pasar", "otra vez 8 segundos"]
    assert er.rango(fragmentos, ["8 segundos"]) == 3
    assert er.rango(fragmentos, ["14 segundos"]) is None


def test_resumen_calcula_aciertos_y_mrr():
    r = er.resumen([1, 2, 5, None])
    assert r["@1"] == 0.25 and r["@3"] == 0.5 and r["@5"] == 0.75 and r["@8"] == 0.75
    assert r["MRR"] == pytest.approx((1 + 1 / 2 + 1 / 5) / 4)


def test_las_preguntas_fijas_son_20_con_id_unico_y_terminos():
    assert len(er.PREGUNTAS) == 20
    ids = [p[0] for p in er.PREGUNTAS]
    assert len(ids) == len(set(ids))
    for _, coleccion, ambito, pregunta, terminos in er.PREGUNTAS:
        assert coleccion in er.COLECCIONES_MD and pregunta.strip().endswith("?") and terminos
        assert ambito in (None, "general", "aragon")


def test_cada_pregunta_tiene_su_respuesta_en_los_documentos_del_repositorio():
    # si una respuesta no está en los .md, la pregunta no mide la recuperación sino la falta de dato
    import re
    textos = {"reglamento_md": {}, "teoria_md": []}
    for md in (RAIZ / "data" / "reglamento").rglob("*.md"):
        textos["reglamento_md"].setdefault(md.parent.name, []).append(md.read_text(encoding="utf-8"))
    textos["teoria_md"] = [md.read_text(encoding="utf-8") for md in (RAIZ / "data" / "teoria").glob("*.md")]
    for id_, coleccion, ambito, _, terminos in er.PREGUNTAS:
        if coleccion == "reglamento_md":
            cuerpo = "\n".join(textos["reglamento_md"][ambito])
        else:
            cuerpo = "\n".join(textos["teoria_md"])
        assert er.contiene(cuerpo, terminos), f"{id_}: ninguno de {terminos} está en los documentos"
