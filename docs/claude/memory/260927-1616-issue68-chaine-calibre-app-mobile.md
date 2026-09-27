# Issue #68 — Documenter la chaîne Calibre → CWA → lmelp-export → GitHub Release → app mobile

## Contexte

Dans [lmelp-mobile#135](https://github.com/castorfou/lmelp-mobile/issues/135), une semaine de
statuts de lecture Calibre n'est jamais arrivée dans l'app mobile. La cause : `nightly-sync.sh`
(tâche DSM, 04:00 heure de Paris) tournait **après** l'export anacron de `lmelp-export`, qui
lisait donc toujours la bibliothèque CWA de la veille. L'export concluait `Contenu inchangé…
publication ignorée` sans erreur visible. Le correctif (tâche DSM avancée à 00:05) est côté NAS.
L'issue #68 couvre la documentation de toute la chaîne et le versionnement du script.

## Faits établis (vérifiés dans le dépôt `lmelp-mobile`, pas supposés)

- **L'export anacron n'a pas d'heure fixe.** `Dockerfile.export` écrit
  `1 10 publish-data-release …` dans `/etc/anacrontab` (période 1 jour, délai 10 min), et
  l'entrypoint relance `anacron -d` toutes les `ANACRON_LOOP_INTERVAL` (3600 s). anacron
  raisonne en **dates** : le job part au premier passage horaire après le changement de date,
  plus 10 min, soit entre 00:10 et 01:10. Les « 00:55 » observés ne sont qu'un exemple, qui
  dépend de la minute de démarrage du conteneur.
- **Le conteneur est en UTC** : pas de `TZ` sur `lmelp-export` dans `docker-compose.yml`.
  L'export tombe donc entre 02:10 et 03:10 heure de Paris l'été, et entre 01:10 et 02:10
  l'hiver. Confirmé par le `stat` de #135 : `metadata.db` modifié à 02:01 UTC, soit
  nightly-sync à 04:00 CEST.
- **`/var/spool/anacron` n'est pas persisté** : seuls `/calibre` et `/var/log` sont montés.
  Chaque recréation (Watchtower, redéploiement) repart d'un état vierge, lance un export
  environ 10 min après le démarrage et décale la minute des exports suivants.
- **Le tag de release est `data-v{ROOM_VERSION}`** (actuellement `data-v9`, issue
  lmelp-mobile#132). `data-latest` est obsolète (dernière publication le 19/08/2026), mais
  était encore cité dans la doc et les commentaires de ce dépôt.
- **DSM est en Europe/Paris** (confirmé par l'utilisateur) : 00:05 correspond à 22:05 UTC
  l'été et 23:05 UTC l'hiver, soit au moins 1 h de marge avant l'export (2 h l'été).

**Règle d'ordonnancement** : `nightly-sync.sh` doit avoir **fini** avant 00:10 UTC. Toute
modification de l'une des deux planifications se recalcule en UTC.

## Décision : piste écartée

Ajouter `TZ=Europe/Paris` sur `lmelp-export` aurait rendu les logs plus lisibles, mais aurait
déplacé la fenêtre de l'export à 00:10–01:10 **heure de Paris**, soit 5 minutes seulement
après nightly-sync à 00:05 : un risque de course. On garde l'UTC et on le documente.

## Modifications

- `scripts/nas/nightly-sync.sh` : script fourni par l'utilisateur, versionné avec une logique
  **inchangée**. Seules les 4 lignes de configuration deviennent surchargeables, avec les
  valeurs NAS par défaut (`CALIBRE_SOURCE_PATH`, `CWA_BOOKS_PATH`, `CWA_CONTAINER`,
  `NIGHTLY_SYNC_LOG`). Un en-tête rappelle la contrainte d'ordonnancement.
  - `set -uo pipefail` **sans `-e`**, volontairement : chaque étape est vérifiée à la main
    pour que le « run detail » du Planificateur DSM affiche un message clair. Ne pas « corriger ».
  - Le slash final de `SRC` est ajouté après la valeur par défaut
    (`"${CALIBRE_SOURCE_PATH:-…}/"`) : il est indispensable à la sémantique rsync (copier le
    contenu, pas le dossier).
- `tests/test_nightly_sync.py` : tests statiques (existe, exécutable, `bash -n`,
  `set -uo pipefail`, valeurs par défaut surchargeables) et comportementaux.
  - Pattern réutilisable : les faux `docker`/`rsync`/`sleep` sont placés dans le `PATH`. Le
    faux `docker` garde l'état du conteneur dans un fichier, pour que
    `docker inspect -f '{{.State.Running}}'` reflète les `stop`/`start` précédents.
  - Cas couverts : ordre stop → rsync → start, chemins passés à rsync, redémarrage de CWA
    même si rsync échoue, arrêt sans synchronisation si CWA ne tournait pas, log écrit.
  - Également : la page de doc est dans le menu et couvre chaque maillon ; plus aucune
    mention de `data-latest`.
- `docs/user/calibre-vers-app-mobile.md` (menu : après « Export vers Android ») :
  - un schéma mermaid des 6 maillons et un tableau configuration / déclencheur / log ;
  - le détail de chaque couche et un avertissement sur l'ordonnancement, avec le tableau
    UTC / heure de Paris ;
  - une check-list de diagnostic en 6 points, qui remonte de l'app jusqu'à Synology Drive.
- `data-latest` remplacé par `data-v{N}` dans `docker-compose.yml`, `.env.example`,
  `.env.nas.example` et `docs/user/export-android.md`.

## Validation

- Tests `test_nightly_sync.py` et `test_docker_compose.py` verts, pre-commit (ruff, mypy)
  vert, `mkdocs build --strict` OK.
- `test_mongodb_image.py` ne peut pas tourner dans le devcontainer (pas de démon Docker) ;
  il échoue de la même façon sur `main`.
- Validé par l'utilisateur sur le NAS : script versionné déployé, tâche DSM repointée,
  exécution manuelle réussie.

## Leçon

Un symptôme « l'app ne se met pas à jour » sans aucune erreur vient souvent d'un **ordre**
entre tâches planifiées. On le diagnostique en comparant, en UTC, la date de modification de
`metadata.db` vue par `lmelp-export` à l'heure du dernier passage anacron.
