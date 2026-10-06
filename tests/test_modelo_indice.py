# tests/test_modelo_indice.py
"""La base de ChromaDB recuerda con qué modelo de embeddings se indexó: consultar con otro modelo da
búsquedas sin sentido y sin ningún error, así que se avisa del desajuste."""
import importlib

import config
from modelo_indice import NOMBRE_MARCA, desajuste, escribir_marca, leer_marca


def test_la_marca_se_escribe_y_se_lee(tmp_path):
    escribir_marca(tmp_path / "db", "qwen3-embedding:0.6b")           # crea la carpeta si falta
    assert leer_marca(tmp_path / "db") == "qwen3-embedding:0.6b"
    assert (tmp_path / "db" / NOMBRE_MARCA).exists()


def test_sin_marca_no_se_sabe_con_que_modelo_se_indexo(tmp_path):
    assert leer_marca(tmp_path) is None


def test_si_el_modelo_coincide_no_hay_aviso(tmp_path):
    escribir_marca(tmp_path, "bge-m3")
    assert desajuste(tmp_path, "bge-m3") is None


def test_si_el_modelo_no_coincide_el_aviso_dice_cual_y_como_arreglarlo(tmp_path):
    escribir_marca(tmp_path, "nomic-embed-text")
    aviso = desajuste(tmp_path, "qwen3-embedding:0.6b")
    assert "nomic-embed-text" in aviso and "qwen3-embedding:0.6b" in aviso and "indexar_colecciones" in aviso


def test_una_base_sin_marca_tambien_avisa(tmp_path):
    assert "marca" in desajuste(tmp_path, "bge-m3").lower()


def test_el_modelo_de_embeddings_se_elige_por_entorno_y_por_defecto_es_qwen3(monkeypatch):
    monkeypatch.delenv("EMBED_MODEL", raising=False)
    assert importlib.reload(config).EMBED_MODEL == "qwen3-embedding:0.6b"
    monkeypatch.setenv("EMBED_MODEL", "bge-m3")
    assert importlib.reload(config).EMBED_MODEL == "bge-m3"
    monkeypatch.delenv("EMBED_MODEL", raising=False)
    importlib.reload(config)
