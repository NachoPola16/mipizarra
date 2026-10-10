# tests/test_huecos_biblioteca.py
"""tools/huecos_biblioteca.py: mide cuántos ejercicios de una sesión inventaría la IA por falta de ficha."""
import importlib.util

from conftest import RAIZ

_spec = importlib.util.spec_from_file_location("huecos_biblioteca", RAIZ / "tools" / "huecos_biblioteca.py")
huecos_biblioteca = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(huecos_biblioteca)


def test_huecos_devuelve_cuantos_faltan_y_el_total_del_plan(ejercicios):
    h, n = huecos_biblioteca.huecos("U10", 60, "bote", ejercicios)
    assert n == 4 and 0 <= h <= n


def test_sin_biblioteca_todos_los_huecos_son_de_la_ia():
    h, n = huecos_biblioteca.huecos("U12", 90, "bote", [])
    assert h == n == 7


def test_la_tabla_incluye_cada_edad_y_el_total(capsys):
    assert huecos_biblioteca.main(["--edades", "U8", "U16", "--duraciones", "60", "--objetivos", "bote", "tiro"]) == 0
    salida = capsys.readouterr().out
    assert "U8" in salida and "U16" in salida and "Total:" in salida


def test_solo_huecos_oculta_las_filas_sin_huecos(capsys):
    huecos_biblioteca.main(["--edades", "U16", "--duraciones", "60", "--objetivos", "bote", "--solo-huecos"])
    assert "U16" not in capsys.readouterr().out.split("Total:")[0].split("\n\n", 1)[1]


def test_el_modo_estricto_no_cuenta_las_fichas_de_un_fundamento_asociado():
    ficha = {"id": "x1", "nombre": "Pases en parejas", "categoria": "juego_equipo", "subcategoria": "pase",
             "edades": ["U10"], "duracion_min": 10, "intensidad": 2, "carga_cognitiva": 2,
             "descripcion": "Dos jugadores se pasan el balón con pase de pecho.", "puntos_clave": ["a", "b"],
             "objetivos": {"tacticos": [], "tecnicos": ["pase de pecho"], "fisicos": []}}
    h_normal, n = huecos_biblioteca.huecos("U10", 60, "contraataque", [ficha])
    h_estricto, _ = huecos_biblioteca.huecos("U10", 60, "contraataque", [ficha], estricto=True)
    assert h_normal < n            # «pase» es un fundamento asociado al contraataque
    assert h_estricto == n         # pero la ficha no habla de contraataque
