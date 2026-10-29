#!/usr/bin/env bash
# Riavvia il workflow alla fine di ogni giro: la pianificazione cron di GitHub, su questo
# repository, non e' mai partita. Il giro successivo parte da solo appena finisce il precedente.
#
# Serve un token personale nel secret AUTOAVVIO_TOKEN: il GITHUB_TOKEN del workflow, per
# costruzione, non puo' innescare altri workflow (GitHub lo impedisce per evitare i cicli).
# Per fermare il ciclo basta cancellare quel secret: senza token questo script non fa niente.
set -euo pipefail

if [ -z "${GH_TOKEN:-}" ]; then
  echo "autoavvio: nessun token, il ciclo resta spento"
  exit 0
fi

# Un solo giro alla volta. Se un altro run e' gia' in coda o in corso il ciclo e' gia' vivo:
# aggiungerne un altro lo sdoppierebbe a ogni giro.
altri=$(gh run list --repo "$GITHUB_REPOSITORY" --workflow offerte.yml --limit 30 \
          --json databaseId,status \
          --jq "[.[] | select(.status != \"completed\") | select(.databaseId != ${GITHUB_RUN_ID})] | length")
if [ "$altri" != "0" ]; then
  echo "autoavvio: ci sono gia' $altri giri vivi, non ne aggiungo"
  exit 0
fi

sleep "${AUTOAVVIO_PAUSA:-0}"
gh workflow run offerte.yml --repo "$GITHUB_REPOSITORY" --ref main
echo "autoavvio: giro successivo richiesto"
