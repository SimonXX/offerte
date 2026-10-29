#!/usr/bin/env bash
# Chiede il giro successivo appena finito il proprio. E' la ruota di scorta, non il motore:
# un giro che ne chiama subito un altro tiene un runner occupato in permanenza, e i termini di
# GitHub chiedono che il carico sia proporzionato al beneficio. Il motore e' .github/workflows/sveglia.yml.
#
# Acceso solo se la variabile di repository AUTOAVVIO vale "on":
#   gh variable set AUTOAVVIO --body on       accende il ciclo continuo
#   gh variable delete AUTOAVVIO              lo spegne (predefinito)
# Serve anche il secret AUTOAVVIO_TOKEN: il GITHUB_TOKEN del workflow, per costruzione, non
# puo' innescare altri workflow.
set -euo pipefail

if [ "${AUTOAVVIO:-}" != "on" ]; then
  echo "autoavvio: ciclo continuo spento, la cadenza la detta sveglia.yml"
  exit 0
fi
if [ -z "${GH_TOKEN:-}" ]; then
  echo "autoavvio: nessun token, il ciclo resta spento"
  exit 0
fi

# Un solo giro alla volta: senza questo controllo ogni giro ne aggiungerebbe uno, e si sdoppierebbero.
altri=$(gh run list --repo "$GITHUB_REPOSITORY" --workflow offerte.yml --limit 30 \
          --json databaseId,status \
          --jq "[.[] | select(.status != \"completed\") | select(.databaseId != ${GITHUB_RUN_ID})] | length")
if [ "$altri" != "0" ]; then
  echo "autoavvio: ci sono gia' $altri giri vivi, non ne aggiungo"
  exit 0
fi

gh workflow run offerte.yml --repo "$GITHUB_REPOSITORY" --ref main
echo "autoavvio: giro successivo richiesto"
