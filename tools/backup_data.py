#!/usr/bin/env python3
"""Copia de seguridad de lo que NO está en git: la base de las cuentas (data/frontend/db.sqlite3: cuentas, jugadas
guardadas y cambios de la biblioteca del botón de administrador), los cambios del administrador sobre
las fichas (data/cambios/ficha_cambios.json), la clave secreta si vive en el volumen y las
sesiones guardadas. Solo biblioteca estándar; se puede ejecutar con la web en marcha (la base se copia con la API de
copias de SQLite, que es coherente aunque alguien esté escribiendo).

Genera `mipizarra-data-AAAAMMDD-HHMMSS.tar.gz` (permisos 600: lleva las contraseñas cifradas) en el destino y borra
las más antiguas, dejando las últimas `--conservar`.

Uso (en el servidor, desde la carpeta del proyecto):
  python3 tools/backup_data.py --destino /root/backups/mipizarra
  python3 tools/backup_data.py --datos ./data --destino /mnt/copias --conservar 30
Cron diario a las 03:10:
  10 3 * * * cd /root/docker/mipizarra && python3 tools/backup_data.py --destino /root/backups/mipizarra >> /var/log/mipizarra-backup.log 2>&1
Restaurar: parar el frontend, descomprimir y copiar `frontend/db.sqlite3` a data/frontend/, arrancar.
"""
import argparse
import contextlib
import datetime
import os
import sqlite3
import sys
import tarfile
import tempfile
from pathlib import Path

PREFIJO = "mipizarra-data-"


def copiar_base(origen: Path, destino: Path) -> None:
    """Copia coherente de una base SQLite en uso (no basta con copiar el fichero)."""
    with contextlib.closing(sqlite3.connect(f"file:{origen}?mode=ro", uri=True)) as src, \
            contextlib.closing(sqlite3.connect(destino)) as dst:
        src.backup(dst)


def hacer_copia(datos: Path, destino: Path, conservar: int, ahora: datetime.datetime | None = None) -> Path:
    base = datos / "frontend" / "db.sqlite3"
    if not base.is_file():
        raise SystemExit(f"No encuentro la base de datos: {base}")
    ahora = ahora or datetime.datetime.now()
    destino.mkdir(parents=True, exist_ok=True)
    salida = destino / f"{PREFIJO}{ahora:%Y%m%d-%H%M%S}.tar.gz"
    with tempfile.TemporaryDirectory() as tmp:
        copia = Path(tmp) / "db.sqlite3"
        copiar_base(base, copia)
        # comprobación: la copia se abre y la base es íntegra
        with contextlib.closing(sqlite3.connect(copia)) as c:
            if c.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise SystemExit("La copia de la base no pasa integrity_check; no se guarda")
        fd = os.open(salida, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as f, tarfile.open(fileobj=f, mode="w:gz") as tar:
            tar.add(copia, arcname="frontend/db.sqlite3")
            clave = datos / "frontend" / "secret_key.txt"
            if clave.is_file():
                tar.add(clave, arcname="frontend/secret_key.txt")
            cambios = datos / "cambios" / "ficha_cambios.json"      # cambios del administrador sobre las fichas
            if cambios.is_file():
                tar.add(cambios, arcname="cambios/ficha_cambios.json")
            sesiones = datos / "sessions"
            if sesiones.is_dir():
                tar.add(sesiones, arcname="sessions")
    antiguas = sorted(destino.glob(f"{PREFIJO}*.tar.gz"))[:-conservar] if conservar > 0 else []
    for vieja in antiguas:
        vieja.unlink()
    return salida


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--datos", type=Path, default=Path(__file__).resolve().parent.parent / "data")
    ap.add_argument("--destino", type=Path, required=True)
    ap.add_argument("--conservar", type=int, default=14, help="cuántas copias se guardan (por defecto 14)")
    a = ap.parse_args()
    salida = hacer_copia(a.datos, a.destino, a.conservar)
    print(f"{datetime.datetime.now():%F %T} copia creada: {salida} ({salida.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
