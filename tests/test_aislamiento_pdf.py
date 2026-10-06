# tests/test_aislamiento_pdf.py
"""Los PDF de terceros quedan aislados del sistema: la API no los ve (no se montan en el contenedor), no hay
forma de activar su uso y el indexador no sabe leerlos. Lo que ve la IA sale solo de documentos propios (.md) y
de la biblioteca de ejercicios (.json), reescritos por el entrenador."""
import importlib
import re

import pytest
import yaml

import config
import contexto
from colecciones import COLECCIONES_PDF, colecciones_a_indexar
from conftest import RAIZ

COMPOSE = yaml.safe_load((RAIZ / "docker-compose.yml").read_text(encoding="utf-8"))


def _montajes_de_data(servicio: str) -> list[str]:
    return [v for v in COMPOSE["services"][servicio].get("volumes", []) if "/app/data" in str(v)]


def test_la_api_no_monta_la_carpeta_de_pdf_ni_toda_la_carpeta_data():
    montajes = _montajes_de_data("api")
    assert montajes, "la API necesita sus datos"
    for m in montajes:
        assert "pdfs" not in m, m
        assert not re.fullmatch(r"\./data(/)?:/app/data(/)?(:\w+)?", m), f"monta todo data/: {m}"


def test_la_api_solo_monta_lo_que_necesita_de_data():
    montados = {m.split(":")[0].replace("\\", "/") for m in _montajes_de_data("api")}
    assert montados == {"./data/exercises.json", "./data/teoria", "./data/reglamento",
                        "./data/chroma_db", "./data/sessions"}


def test_los_documentos_de_solo_lectura_se_montan_asi():
    por_origen = {m.split(":")[0]: m for m in _montajes_de_data("api")}
    for origen in ("./data/exercises.json", "./data/teoria", "./data/reglamento"):
        assert por_origen[origen].endswith(":ro"), origen


def test_el_compose_no_ofrece_ninguna_opcion_para_activar_los_pdf():
    texto = (RAIZ / "docker-compose.yml").read_text(encoding="utf-8")
    assert "USAR_PDFS" not in texto


def test_no_existe_ajuste_para_usar_pdfs_ni_con_la_variable_de_entorno(monkeypatch):
    monkeypatch.setenv("RAG_USAR_PDFS", "1")
    assert not hasattr(importlib.reload(config), "USAR_PDFS")
    monkeypatch.delenv("RAG_USAR_PDFS")
    importlib.reload(config)


class _BaseFalsa:
    def __init__(self):
        self.pedidas = []

    def get_collection(self, nombre):
        self.pedidas.append(nombre)
        raise KeyError(nombre)


@pytest.mark.parametrize("nombre", sorted(COLECCIONES_PDF))
def test_las_colecciones_de_pdf_nunca_se_consultan(monkeypatch, nombre):
    base = _BaseFalsa()
    monkeypatch.setattr(contexto, "_chroma", base)
    assert contexto.consultar_coleccion(nombre, "cualquier pregunta") == ""
    assert base.pedidas == []


@pytest.mark.parametrize("nombre", ["teoria_md", "reglamento_md"])
def test_los_documentos_propios_se_consultan(monkeypatch, nombre):
    base = _BaseFalsa()
    monkeypatch.setattr(contexto, "_chroma", base)
    contexto.consultar_coleccion(nombre, "cualquier pregunta")
    assert base.pedidas == [nombre]


def test_el_indexador_nunca_incluye_las_colecciones_de_pdf():
    todas = {"teoria_md": 1, "teoria": 2, "planificacion": 3, "reglamento_md": 4, "reglamento": 5}
    assert set(colecciones_a_indexar(todas)) == {"teoria_md", "reglamento_md"}


def test_el_indexador_no_sabe_leer_pdf_ni_acepta_la_opcion():
    codigo = (RAIZ / "tools" / "indexar_colecciones.py").read_text(encoding="utf-8")
    assert "PDFReader" not in codigo and "--con-pdfs" not in codigo and "PDFS_BASE_DIR" not in codigo
    assert '.glob("*.pdf")' not in codigo


def test_el_contexto_de_las_sesiones_solo_trae_documentos_propios(monkeypatch):
    consultadas = []
    base = _BaseFalsa()
    original = contexto.consultar_coleccion

    def espia(nombre, consulta, n_resultados=4, where=None):
        consultadas.append(nombre)
        return original(nombre, consulta, n_resultados, where)

    monkeypatch.setattr(contexto, "consultar_coleccion", espia)
    monkeypatch.setattr(contexto, "_chroma", base)
    contexto.construir_contexto_teoria("bote", "U10")
    assert not set(base.pedidas) & COLECCIONES_PDF                     # a la base solo llegan colecciones propias
    assert {"teoria_md", "reglamento_md"} <= set(base.pedidas)
