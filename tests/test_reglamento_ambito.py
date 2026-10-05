# tests/test_reglamento_ambito.py
"""Reglamento por ámbito: general o comunidad autónoma (que usa también el general)."""
import pytest
from pydantic import ValidationError

import rag_engine
from main import ReglamentoRequest
from rag_engine import (
    AMBITO_GENERAL, listar_ambitos, nombre_ambito, normalizar_ambito, responder_duda_reglamento,
)


@pytest.fixture
def carpeta_ambitos(tmp_path, monkeypatch):
    """data/reglamento de prueba: general, aragon, una carpeta vacía y otra con nombre no válido."""
    for nombre, con_md in [("general", True), ("aragon", True), ("vacia", False), ("Mal Nombre", True)]:
        d = tmp_path / nombre
        d.mkdir()
        if con_md:
            (d / "norma.md").write_text("# norma\n", encoding="utf-8")
    (tmp_path / "suelto.md").write_text("# suelto\n", encoding="utf-8")
    monkeypatch.setattr(rag_engine, "REGLAMENTO_DIR", str(tmp_path))
    return tmp_path


# ── listar_ambitos / normalizar_ambito ──────────────────────────────

def test_listar_ambitos_general_primero_y_solo_carpetas_validas(carpeta_ambitos):
    assert [a["id"] for a in listar_ambitos()] == ["general", "aragon"]


def test_listar_ambitos_sin_carpeta_devuelve_general(tmp_path, monkeypatch):
    monkeypatch.setattr(rag_engine, "REGLAMENTO_DIR", str(tmp_path / "no_existe"))
    assert [a["id"] for a in listar_ambitos()] == ["general"]


def test_listar_ambitos_del_repositorio():
    ids = [a["id"] for a in listar_ambitos()]
    assert ids[0] == "general"
    assert "aragon" in ids


def test_nombres_legibles():
    assert nombre_ambito("aragon") == "Aragón"
    assert nombre_ambito("castilla_y_leon") == "Castilla Y Leon"      # sin nombre propio: se deriva del id


@pytest.mark.parametrize("valor,esperado", [
    (None, "general"), ("", "general"), ("general", "general"),
    ("aragon", "aragon"), ("ARAGON", "aragon"), ("  aragon ", "aragon"),
    ("inexistente", "general"), ("vacia", "general"), ("../etc", "general"), ("aragon/../x", "general"),
])
def test_normalizar_ambito(carpeta_ambitos, valor, esperado):
    assert normalizar_ambito(valor) == esperado


# ── Validación de la petición ───────────────────────────────────────

def test_peticion_por_defecto_es_general():
    assert ReglamentoRequest(pregunta="¿Qué es una falta técnica?").ambito == "general"


def test_peticion_acepta_comunidad():
    assert ReglamentoRequest(pregunta="¿Cuántos tiempos muertos?", ambito="aragon").ambito == "aragon"


@pytest.mark.parametrize("malo", ["Aragón", "../x", "a", "x" * 31, "con espacio", "1aragon", "aragon;drop"])
def test_peticion_rechaza_ambito_mal_formado(malo):
    with pytest.raises(ValidationError):
        ReglamentoRequest(pregunta="¿Cuántos tiempos muertos?", ambito=malo)


# ── Recuperación y prompt según el ámbito ───────────────────────────

class _Resp:
    def raise_for_status(self):
        pass

    def json(self):
        return {"message": {"content": "respuesta de prueba"}}


@pytest.fixture
def espia(carpeta_ambitos, monkeypatch):
    """Registra las consultas a ChromaDB y el mensaje enviado al modelo."""
    reg = {"consultas": [], "mensaje": None}

    def consulta(nombre, texto, n_resultados=4, where=None):
        reg["consultas"].append((nombre, where))
        ambito = (where or {}).get("ambito", "sin_filtro")
        return f"texto de {nombre} [{ambito}]"

    def post(url, json=None, timeout=None):
        reg["mensaje"] = json["messages"][1]["content"]
        return _Resp()

    monkeypatch.setattr(rag_engine, "consultar_coleccion", consulta)
    monkeypatch.setattr(rag_engine.requests, "post", post)
    return reg


def test_general_no_consulta_comunidades(espia):
    assert responder_duda_reglamento("¿Qué es el paso cero?") == "respuesta de prueba"
    filtros = [w["ambito"] for _, w in espia["consultas"] if w]
    assert filtros and set(filtros) == {AMBITO_GENERAL}
    assert "ÁMBITO DE LA CONSULTA: general" in espia["mensaje"]
    assert "NORMATIVA DE" not in espia["mensaje"]


def test_comunidad_consulta_su_normativa_y_la_general(espia):
    responder_duda_reglamento("¿Cuántos jugadores juegan dos periodos?", "aragon")
    consultas = espia["consultas"]
    assert ("reglamento_md", {"ambito": "aragon"}) in consultas
    assert ("reglamento", {"ambito": "aragon"}) in consultas
    assert ("reglamento_md", {"ambito": "general"}) in consultas
    msg = espia["mensaje"]
    assert "ÁMBITO DE LA CONSULTA: Aragón" in msg
    assert "NORMATIVA DE ARAGÓN" in msg and "REGLAMENTO GENERAL" in msg
    assert msg.index("NORMATIVA DE ARAGÓN") < msg.index("REGLAMENTO GENERAL")   # la específica va primero
    assert "prevalece sobre la general" in msg


def test_ambito_desconocido_cae_en_general(espia):
    responder_duda_reglamento("¿Qué es el paso cero?", "inexistente")
    assert all(w["ambito"] == AMBITO_GENERAL for _, w in espia["consultas"] if w)
    assert "ÁMBITO DE LA CONSULTA: general" in espia["mensaje"]


def test_sin_resultados_el_modelo_recibe_solo_la_instruccion_y_la_pregunta(carpeta_ambitos, monkeypatch):
    mensajes = []
    monkeypatch.setattr(rag_engine, "consultar_coleccion", lambda *a, **k: "")
    monkeypatch.setattr(rag_engine.requests, "post",
                        lambda url, json=None, timeout=None: (mensajes.append(json["messages"][1]["content"]), _Resp())[1])
    responder_duda_reglamento("¿Cuántos tiempos muertos?", "aragon")
    assert mensajes[0].endswith("PREGUNTA: ¿Cuántos tiempos muertos?")
    assert "EXTRACTOS" not in mensajes[0]


# ── Datos del repositorio ───────────────────────────────────────────

def test_los_md_de_cada_ambito_existen_y_no_estan_vacios():
    from conftest import DATA_DIR
    for ambito in ("general", "aragon"):
        ficheros = list((DATA_DIR / "reglamento" / ambito).glob("*.md"))
        assert ficheros, f"sin .md en data/reglamento/{ambito}"
        assert all(f.stat().st_size > 500 for f in ficheros)
