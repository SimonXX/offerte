#!/usr/bin/env bash
# Copia le unit in ~/.config/systemd/user con il percorso di questo progetto. Non abilita nulla.
set -euo pipefail
DIR="$(cd "$(dirname "$0")/.." && pwd)"
UNITS="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
mkdir -p "$UNITS"
for u in offerte-fetch.service offerte-fetch.timer offerte-serve.service; do
  sed "s|@PROJECT_DIR@|$DIR|g" "$DIR/systemd/$u" > "$UNITS/$u"
done
systemctl --user daemon-reload
echo "Unit installate in $UNITS. Per attivare:"
echo "  systemctl --user enable --now offerte-fetch.timer offerte-serve.service"
