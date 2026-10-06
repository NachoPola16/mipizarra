# tests/test_validar_candidatos.py
"""tools/validar_candidatos.py: informe de un lote de fichas candidatas contrastado con la biblioteca."""
import copy
import importlib.util
import json

from conftest import RAIZ
from test_validacion_fichas import FICHA_OK

_spec = importlib.util.spec_from_file_location("validar_candidatos", RAIZ / "tools" / "validar_candidatos.py")
vc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vc)


def _lote(tmp_path, fichas):
    ruta = tmp_path / "lote.json"
    ruta.write_text(json.dumps(fichas, ensure_ascii=False), encoding="utf-8")
    return str(ruta)


def test_un_lote_correcto_sale_con_codigo_0(tmp_path, capsys):
    assert vc.main([_lote(tmp_path, [FICHA_OK])]) == 0
    assert "1 de 1" in capsys.readouterr().out


def test_un_lote_con_problemas_sale_con_codigo_1_y_los_cuenta(tmp_path, capsys):
    mala = copy.deepcopy(FICHA_OK)
    mala.update(id="ej_902", nombre="Otro ejercicio", categoria="inventada")
    assert vc.main([_lote(tmp_path, [FICHA_OK, mala])]) == 1
    salida = capsys.readouterr().out
    assert "ej_902" in salida and "categoria" in salida and "1 de 2" in salida


def test_los_candidatos_se_contrastan_con_la_biblioteca_real(tmp_path, capsys):
    repetida = copy.deepcopy(FICHA_OK)
    repetida["id"] = "ej_001"                                   # ya existe en data/exercises.json
    assert vc.main([_lote(tmp_path, [repetida])]) == 1
    assert "repetido" in capsys.readouterr().out


def test_los_candidatos_del_mismo_lote_no_pueden_repetirse_entre_si(tmp_path, capsys):
    otra = copy.deepcopy(FICHA_OK)
    assert vc.main([_lote(tmp_path, [FICHA_OK, otra])]) == 1
    assert "repetido" in capsys.readouterr().out


def test_acepta_una_sola_ficha_en_lugar_de_una_lista(tmp_path):
    assert vc.main([_lote(tmp_path, FICHA_OK)]) == 0


def test_un_fichero_que_no_es_json_es_un_error_claro(tmp_path, capsys):
    ruta = tmp_path / "roto.json"
    ruta.write_text("esto no es json", encoding="utf-8")
    assert vc.main([str(ruta)]) == 2
    assert "JSON" in capsys.readouterr().out


def test_solo_errores_oculta_las_fichas_que_pasan(tmp_path, capsys):
    mala = dict(copy.deepcopy(FICHA_OK), id="ej_903", nombre="Mala", categoria="x")
    vc.main([_lote(tmp_path, [FICHA_OK, mala]), "--solo-errores"])
    salida = capsys.readouterr().out
    assert "ej_903" in salida and "ej_901 " not in salida
