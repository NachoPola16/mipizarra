#!/usr/bin/env bash
# Despliega MiPizarra en el CT 102 desde tu equipo (git pull en el servidor, reinicia la API y reconstruye el frontend).
# Se niega a desplegar si el servidor tiene ediciones de fichas (pestaña «Fichas») sin subir a git: serían las únicas copias
# del trabajo (ver docs/administracion-fichas.md). Uso:  bash tools/desplegar.sh
# Antes de desplegar, sube tus commits (git push): el servidor hace `git pull --ff-only`.
set -u
SSH="${MIPIZARRA_SSH:-proxmox}"; CT="${MIPIZARRA_CT:-102}"; DIR="${MIPIZARRA_DIR:-/root/docker/mipizarra}"

en_servidor() { ssh "$SSH" "pct exec $CT -- bash -s" ; }

estado=$(printf 'cd %s && git --git-dir=.git-datos --work-tree=. status --porcelain -- data/exercises.json </dev/null\n' "$DIR" | en_servidor)
if [ -n "$estado" ]; then
    cat <<MSG
NO SE DESPLIEGA: el servidor tiene ediciones de fichas sin subir a git (data/exercises.json distinto del último commit del repo privado .git-datos).
Tráelas primero (revisa el diff antes de subir):
  ssh $SSH "pct exec $CT -- cat $DIR/data/exercises.json" > data/exercises.json
  tools/gitd diff --stat data/exercises.json
  tools/gitd add data/exercises.json && tools/gitd commit -m "fichas: ediciones hechas desde la pestaña Fichas" && tools/gitd push
  ssh $SSH "pct exec $CT -- bash -c 'cd $DIR && git --git-dir=.git-datos --work-tree=. checkout -- data/exercises.json'"
y vuelve a ejecutar este script. (Si esas fichas también cambiaron en git, mézclalas a mano.)
MSG
    exit 1
fi

en_servidor <<SCRIPT
set -e
cd $DIR
git pull --ff-only </dev/null
git --git-dir=.git-datos --work-tree=. pull --ff-only </dev/null
docker restart mipizarra-api </dev/null
docker compose up -d --build frontend </dev/null
sleep 8
docker ps --format '{{.Names}} {{.Status}}' </dev/null | grep mipizarra
git log --oneline -1 </dev/null
SCRIPT
