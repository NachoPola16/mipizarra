# tests/test_fundamentos_y_resumen.py
"""«Fundamentos» que se queda en el arranque del prompt y resumen del objetivo para la portada del PDF."""
from unittest.mock import patch

import resumen_objetivo as ro
from sesion import _arreglar_fundamentos_incompletos


def test_fundamentos_en_el_arranque_se_sustituyen_por_los_de_las_fichas():
    bloques = {"fundamentos": "En esta sesión se trabajan"}
    assert _arreglar_fundamentos_incompletos(bloques, "bote, pase.")
    assert bloques["fundamentos"] == "En esta sesión se trabajan bote, pase."


def test_fundamentos_incompletos_sin_reserva_se_quitan():
    bloques = {"fundamentos": "En esta sesión se trabajan", "ej:1": "x"}
    assert _arreglar_fundamentos_incompletos(bloques, "")
    assert "fundamentos" not in bloques and "ej:1" in bloques


def test_fundamentos_completos_no_se_tocan():
    texto = "En esta sesión se trabajan el bote de protección, la lectura del defensor y el pase corto."
    bloques = {"fundamentos": texto}
    assert not _arreglar_fundamentos_incompletos(bloques, "bote.")
    assert bloques["fundamentos"] == texto


def test_objetivo_corto_se_deja_tal_cual():
    with patch.object(ro.requests, "post") as post:
        assert ro.resumir_objetivo("  Intensidad,  bote y contraataques ") == "Intensidad, bote y contraataques"
        post.assert_not_called()


class _Resp:
    def __init__(self, texto): self._t = texto
    def raise_for_status(self): pass
    def json(self): return {"response": self._t}


LARGO = ("Quiero trabajar el bote con las dos manos, que se mire al frente, ritmo alto, juego sin fila de espera, "
         "mucho contacto con el balón y finalizar siempre en canasta con bandeja de las dos manos") * 2


def test_objetivo_largo_usa_el_resumen_del_modelo():
    with patch.object(ro.requests, "post", return_value=_Resp("«Resumen: Bote con ambas manos y finalización.»")):
        assert ro.resumir_objetivo(LARGO) == "Bote con ambas manos y finalización"


def test_objetivo_largo_sin_modelo_se_recorta_por_palabras():
    with patch.object(ro.requests, "post", side_effect=RuntimeError("sin modelo")):
        r = ro.resumir_objetivo(LARGO)
    assert len(r) <= ro.MAX_RESUMEN and r.endswith("…") and LARGO.startswith(r[:-1].rstrip())


def test_resumen_mas_largo_que_el_objetivo_se_descarta():
    with patch.object(ro.requests, "post", return_value=_Resp("x" * 300)):
        r = ro.resumir_objetivo(LARGO)
    assert len(r) <= ro.MAX_RESUMEN


def test_resumen_con_demasiados_temas_conserva_los_primeros():
    largo = ", ".join(["Bote con ambas manos", "mirada al frente", "ritmo alto", "contacto con el balón",
                      "finalización con bandeja", "pases cortos", "comunicación entre compañeros"])
    assert len(largo) > ro.MAX_RESUMEN
    with patch.object(ro.requests, "post", return_value=_Resp(largo)):
        r = ro.resumir_objetivo(LARGO)
    assert len(r) <= ro.MAX_RESUMEN and r.startswith("Bote con ambas manos, mirada al frente") and not r.endswith(",")


def test_los_fundamentos_de_reserva_priorizan_el_objetivo_pedido():
    from sesion import _fundamentos_de_las_fichas

    def hueco(*tecnicos):
        return type("H", (), {"ficha": {"objetivos": {"tecnicos": list(tecnicos)}}})()

    huecos = [hueco("bomba sobre un pie", "pase de pecho"), hueco("bote para avanzar", "recepción con dos manos"), hueco("pase picado")]
    texto = _fundamentos_de_las_fichas(huecos, "pase y visión de juego")
    assert texto.startswith("pase de pecho, pase picado")
    assert "bomba sobre un pie" in texto and texto.endswith(".")
    assert len(texto.split(", ")) <= 5
