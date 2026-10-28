#!/usr/bin/env bash
# Stato del servizio (var/offerte.sqlite) su un branch git orfano con un solo commit, riscritto a ogni giro.
#   stato.sh restore   scarica lo stato dal branch, se esiste
#   stato.sh save      riscrive il branch con lo stato corrente
# Remoto: $OFFERTE_DATA_REMOTE, altrimenti il repository GitHub del workflow (token), altrimenti origin.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VAR="${OFFERTE_VAR_DIR:-$ROOT/var}"
BRANCH="${OFFERTE_DATA_BRANCH:-data}"
mkdir -p "$VAR"

remote() {
  if [ -n "${OFFERTE_DATA_REMOTE:-}" ]; then echo "$OFFERTE_DATA_REMOTE"
  elif [ -n "${GITHUB_TOKEN:-}" ] && [ -n "${GITHUB_REPOSITORY:-}" ]; then echo "https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_REPOSITORY}.git"
  else git -C "$ROOT" remote get-url origin; fi
}

case "${1:-}" in
  restore)
    if git -C "$ROOT" fetch -q --depth 1 "$(remote)" "$BRANCH" 2>/dev/null; then
      git -C "$ROOT" show FETCH_HEAD:offerte.sqlite > "$VAR/offerte.sqlite"
      echo "stato ripristinato dal branch $BRANCH ($(stat -c%s "$VAR/offerte.sqlite") byte)"
    else
      echo "nessun branch $BRANCH: primo avvio"
    fi ;;
  save)
    if [ ! -f "$VAR/offerte.sqlite" ]; then echo "niente da salvare"; exit 0; fi
    tmp="$(mktemp -d)"
    cp "$VAR/offerte.sqlite" "$tmp/"
    git -C "$tmp" init -q -b "$BRANCH"
    git -C "$tmp" add offerte.sqlite
    git -C "$tmp" -c user.name=offerte -c user.email=offerte@users.noreply.github.com commit -qm "stato $(date -u +%FT%TZ)"
    git -C "$tmp" push -q --force "$(remote)" "$BRANCH"
    rm -rf "$tmp"
    echo "stato salvato sul branch $BRANCH" ;;
  *) echo "uso: $0 restore|save" >&2; exit 2 ;;
esac
