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
    # ls-remote distingue "branch assente" (rc 2) da "remoto irraggiungibile" (altro rc). Senza questa
    # distinzione un errore di rete passerebbe per primo avvio, e il save successivo, che e' un push
    # forzato, cancellerebbe storia, dedupe e notifiche gia' inviate.
    rc=0
    git -C "$ROOT" ls-remote --exit-code --heads "$(remote)" "$BRANCH" >/dev/null 2>&1 || rc=$?
    if [ "$rc" -eq 0 ]; then
      git -C "$ROOT" fetch -q --depth 1 "$(remote)" "$BRANCH"
      git -C "$ROOT" show FETCH_HEAD:offerte.sqlite > "$VAR/offerte.sqlite"
      echo "stato ripristinato dal branch $BRANCH ($(stat -c%s "$VAR/offerte.sqlite") byte)"
    elif [ "$rc" -eq 2 ]; then
      echo "nessun branch $BRANCH: primo avvio"
    else
      echo "remoto non raggiungibile (ls-remote rc=$rc): mi fermo per non sovrascrivere lo stato" >&2
      exit 1
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
