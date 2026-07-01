#!/usr/bin/env bash
# Временно дополняет .dockerignore для узкого build context одного образа.
# Использование: scripts/docker_build.sh classifier|server|webapp [docker build args...]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

SERVICE="${1:?service: classifier|server|webapp}"
shift

case "$SERVICE" in
  classifier)
    EXTRA_IGNORE=$'server/\nwebapp/\nconfig/\nmigrations/\n'
    DOCKERFILE="Dockerfile.classifier"
    ;;
  server)
    EXTRA_IGNORE=$'api/\ncv/\nrag/\nscripts/\nwebapp/\n'
    DOCKERFILE="Dockerfile.server"
    ;;
  webapp)
    EXTRA_IGNORE=$'server/\napi/\ncv/\nrag/\nscripts/\nconfig/\nmigrations/\n'
    DOCKERFILE="Dockerfile.webapp"
    ;;
  *)
    echo "unknown service: $SERVICE" >&2
    exit 1
    ;;
esac

BACKUP=""
cleanup() {
  if [[ -n "$BACKUP" && -f "$BACKUP" ]]; then
    mv -f "$BACKUP" .dockerignore
  fi
}
trap cleanup EXIT

BACKUP="$(mktemp)"
cp .dockerignore "$BACKUP"
printf '%s' "$EXTRA_IGNORE" >> .dockerignore

docker build -f "$DOCKERFILE" "$@" .
