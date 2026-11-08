#!/bin/sh
# Updates Luma Melisa on the shared VDS from GitHub and restarts only its own containers.
# Usage: /opt/melisaluma/luma-backend/deploy/vds-deploy.sh [branch]   (default: main)
set -eu
BRANCH="${1:-main}"
ROOT=/opt/melisaluma

for repo in luma-backend luma-frontend; do
  if [ ! -d "$ROOT/$repo/.git" ]; then
    git clone "https://github.com/melisau/$repo.git" "$ROOT/$repo"
  fi
  git -C "$ROOT/$repo" fetch --quiet origin
  git -C "$ROOT/$repo" checkout --quiet "$BRANCH"
  git -C "$ROOT/$repo" reset --quiet --hard "origin/$BRANCH"
  echo "$repo: $(git -C "$ROOT/$repo" log --oneline -1)"
done

[ -f "$ROOT/.env.vds" ] || { echo "Missing $ROOT/.env.vds" >&2; exit 1; }
mkdir -p "$ROOT/backups"

cd "$ROOT/luma-backend/deploy"
docker compose -f compose.vds.yaml --env-file "$ROOT/.env.vds" up -d --build
docker compose -f compose.vds.yaml --env-file "$ROOT/.env.vds" ps
