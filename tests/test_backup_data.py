# tests/test_backup_data.py
"""tools/backup_data.py: copia coherente de la base de cuentas, con rotación y permisos 600."""
import datetime
import importlib.util
import sqlite3
import tarfile

from conftest import RAIZ

_spec = importlib.util.spec_from_file_location("backup_data", RAIZ / "tools" / "backup_data.py")
backup = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(backup)


def _datos(tmp_path):
    (tmp_path / "frontend").mkdir(parents=True)
    con = sqlite3.connect(tmp_path / "frontend" / "db.sqlite3")
    con.execute("CREATE TABLE cuentas (n TEXT)")
    con.execute("INSERT INTO cuentas VALUES ('nacho')")
    con.commit()
    con.close()
    (tmp_path / "sessions").mkdir()
    (tmp_path / "sessions" / "sesion_20261001_101010.json").write_text("{}", encoding="utf-8")
    return tmp_path


def test_la_copia_trae_la_base_legible_y_las_sesiones(tmp_path):
    datos = _datos(tmp_path / "datos")
    salida = backup.hacer_copia(datos, tmp_path / "copias", conservar=3)
    with tarfile.open(salida) as tar:
        assert {"frontend/db.sqlite3", "sessions/sesion_20261001_101010.json"} <= set(tar.getnames())
        tar.extract("frontend/db.sqlite3", tmp_path / "restaurado")
    con = sqlite3.connect(tmp_path / "restaurado" / "frontend" / "db.sqlite3")
    fila = con.execute("SELECT n FROM cuentas").fetchone()
    con.close()
    assert fila == ("nacho",)


def test_solo_se_conservan_las_ultimas(tmp_path):
    datos = _datos(tmp_path / "datos")
    for dia in range(1, 6):
        backup.hacer_copia(datos, tmp_path / "copias", conservar=3, ahora=datetime.datetime(2026, 10, dia, 3, 10))
    nombres = sorted(p.name for p in (tmp_path / "copias").iterdir())
    assert [n[15:23] for n in nombres] == ["20261003", "20261004", "20261005"]
