#!/bin/bash
# nightly-sync.sh — Synchronise la bibliothèque Calibre Desktop vers la
# bibliothèque de Calibre-Web-Automated (CWA) sur le NAS.
#
# Tourne sur l'HÔTE NAS (pas dans un conteneur), via une tâche planifiée DSM
# (Panneau de configuration → Planificateur de tâches → Script défini par
# l'utilisateur, utilisateur root) :
#     bash /volume1/docker/docker-lmelp/scripts/nas/nightly-sync.sh
#
# Étapes : arrêt de CWA → rsync Calibre Desktop → books/ de CWA → redémarrage
# de CWA (relance le backfill des checksums KOReader).
#
# ORDONNANCEMENT : lmelp-export lit cette bibliothèque CWA (CALIBRE_HOST_PATH)
# à chaque passage de sa boucle de publication (toutes les PUBLISH_INTERVAL
# secondes, 1 h par défaut). Les changements synchronisés ici atteignent donc
# l'app mobile au plus un intervalle plus tard, quelle que soit l'heure de la
# tâche DSM. Voir docs/user/calibre-vers-app-mobile.md.
#
# Les chemins sont surchargeables par variables d'environnement ; les valeurs
# par défaut sont celles du NAS de référence.
set -uo pipefail   # (pas de -e ici, on gère les erreurs nous-mêmes pour des messages clairs)

SRC="${CALIBRE_SOURCE_PATH:-/volume1/homes/guillaume/Backup/framework/home/guillaume/Calibre Library}/"
DST="${CWA_BOOKS_PATH:-/volume1/docker/calibre-web-automated/books}/"
LOG="${NIGHTLY_SYNC_LOG:-/volume1/docker/calibre-web-automated/rsync-nightly.log}"
CONTAINER="${CWA_CONTAINER:-calibre-web-automated}"

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$LOG"; }

fail() {
    log "ERREUR: $1"
    echo "ERREUR: $1"   # visible dans le "run detail" du Planificateur
    exit 1
}

log "=== Début du script ==="

# 1. Vérifier que le container tourne AVANT de l'arrêter
STATE=$(docker inspect -f '{{.State.Running}}' "$CONTAINER" 2>/dev/null) \
    || fail "Impossible d'inspecter le container '$CONTAINER' (n'existe pas ?)"

if [ "$STATE" != "true" ]; then
    fail "Le container '$CONTAINER' n'était pas en cours d'exécution avant le sync (état: $STATE) — situation anormale, arrêt du script."
fi
log "OK: container en cours d'exécution, prêt à être arrêté"

# 2. Vérifier que SRC et DST existent AVANT le rsync
[ -d "$SRC" ] || fail "Le dossier source n'existe pas : $SRC"
[ -d "$DST" ] || fail "Le dossier destination n'existe pas : $DST"
log "OK: SRC et DST existent"

# 3. Arrêt du container
log "Arrêt du container..."
docker stop "$CONTAINER" >> "$LOG" 2>&1 \
    || fail "Échec de 'docker stop $CONTAINER'"

# Vérifier qu'il est bien arrêté avant de continuer
STATE=$(docker inspect -f '{{.State.Running}}' "$CONTAINER" 2>/dev/null)
if [ "$STATE" != "false" ]; then
    fail "Le container ne s'est pas arrêté correctement (état: $STATE) — rsync annulé par sécurité."
fi
log "OK: container bien arrêté"

# 4. Rsync
log "Lancement du rsync..."
rsync -av --checksum \
  --exclude='.caltrash/' \
  "$SRC" "$DST" \
  >> "$LOG" 2>&1

RSYNC_EXIT=$?
if [ "$RSYNC_EXIT" -ne 0 ]; then
    log "rsync a retourné le code $RSYNC_EXIT — on tente quand même de redémarrer CWA pour ne pas le laisser arrêté"
    docker start "$CONTAINER" >> "$LOG" 2>&1
    fail "rsync a échoué (code $RSYNC_EXIT), voir $LOG pour le détail. Container redémarré malgré tout."
fi
log "OK: rsync terminé sans erreur"

# 5. Redémarrage du container (retrigger backfill checksums KOReader)
log "Redémarrage du container..."
docker start "$CONTAINER" >> "$LOG" 2>&1 \
    || fail "Échec de 'docker start $CONTAINER' — CWA reste ARRÊTÉ, intervention manuelle requise !"

# Vérifier qu'il a bien redémarré
sleep 3
STATE=$(docker inspect -f '{{.State.Running}}' "$CONTAINER" 2>/dev/null)
if [ "$STATE" != "true" ]; then
    fail "Le container ne semble pas avoir redémarré correctement (état: $STATE) — CWA potentiellement indisponible !"
fi

log "=== Fin du script : succès ==="
exit 0
