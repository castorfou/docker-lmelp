# Issue #77 — lmelp-export : publication horaire + notifications ntfy

## Contexte

[castorfou/lmelp-mobile#153](https://github.com/castorfou/lmelp-mobile/issues/153)
change l'image `ghcr.io/castorfou/lmelp-mobile-export` :

- l'anacron quotidien (`1 10` dans `/etc/anacrontab`) disparaît ; `/docker-entrypoint.sh`
  lance `publish-loop &` (`scripts/docker_publish_loop.sh` côté lmelp-mobile), qui exécute
  `export-and-publish-release` **dès le démarrage**, puis dort `PUBLISH_INTERVAL` s
  (défaut 3600, `0` = boucle désactivée) ;
- `scripts/notify_ntfy.py` (lmelp-mobile) notifie chaque publication réelle (donc
  seulement si le `content_hash` a changé), le **premier** échec (20 dernières lignes du
  log), puis le retour à la normale. `NTFY_TOPIC` vide → no-op (`if not topic`),
  `NTFY_SERVER_URL` vide → `https://ntfy.sh`, `NTFY_TOKEN` optionnel ;
- état ok/failed dans `NTFY_STATE_FILE` = `/var/lib/lmelp-export/last_status` (absent = ok) ;
- verrou `flock -n /tmp/lmelp-publish.lock` : un `docker exec` manuel pendant un passage
  de la boucle sort en code 0 (« Publication déjà en cours, run ignoré ») ;
- le log `/var/log/publish-data-release.log` reçoit un bloc `=== <date -Is UTC> : ok|failed ===`
  + sortie complète, à chaque passage.

Au moment du travail, #153 n'était **pas mergée** : le comportement a été lu sur la
branche `153-publication-horaire-de-lmelpdb-+-notifications-ntfy-succèséchec` via
`gh api repos/castorfou/lmelp-mobile/contents/<f>?ref=<branche url-encodée>`.

## Ce qui a été fait (docker-lmelp)

- `docker-compose.yml`, service `lmelp-export` :
  - `PUBLISH_INTERVAL=${PUBLISH_INTERVAL:-3600}` ;
  - `NTFY_SERVER_URL=${NTFY_SERVER_URL:-}` / `NTFY_TOPIC=${NTFY_TOPIC:-}`, **strictement
    identiques** aux entrées de `backend` (topic partagé, titres `lmelp-mobile - …`) ;
  - volume `${LMELP_EXPORT_STATE_PATH:-./data/logs/lmelp-export-state}:/var/lib/lmelp-export` ;
  - commentaires « anacron » → `publish-loop`.
- `.env.example` / `.env.nas.example` : `PUBLISH_INTERVAL` (commenté), `LMELP_EXPORT_STATE_PATH`
  (NAS : `/volume1/docker/lmelp/logs/lmelp-export-state`), commentaire ntfy indiquant le partage
  avec lmelp-export.
- `docs/user/calibre-vers-app-mobile.md` : diagramme et tableau (boucle horaire), section du
  conteneur réécrite (variables, export au démarrage, verrou, notifications, `last_status`),
  « Contrainte d'ordonnancement » remplacée par « Délai entre Calibre et l'app », diagnostic
  basé sur les lignes `=== … ===` et `last_status` au lieu de `/var/spool/anacron`.
- `scripts/nas/nightly-sync.sh` : commentaire ORDONNANCEMENT mis à jour (plus de 00:10 UTC).
- `CLAUDE.md` : la règle « L'anacron de lmelp-export n'a pas d'heure fixe, et tourne en UTC »
  devient « `lmelp-export` publie en boucle : la donnée Calibre arrive au plus un intervalle
  plus tard ».

## Décisions

- **Volume d'état ajouté** (optionnel dans l'issue) : sans lui, un conteneur recréé
  (Watchtower) pendant une panne repart de `ok` et la notification « rétablie » ne part
  jamais — l'utilisateur resterait sur la dernière alerte d'échec.
- **Volume sous `./data/logs`** (choix utilisateur) : sans risque vis-à-vis de la règle
  #51, le conteneur tourne en root et plus aucun service ne chowne `./data/logs` depuis le
  retrait de `lmelp` (#71). `TestDockerComposeLogPathSeparation` couvre automatiquement
  le nouveau `_PATH`.
- **Pas de `NTFY_TOKEN`** : le backend ne l'utilise pas non plus.
- **Croissance de `publish-data-release.log` ignorée** (choix utilisateur) : 24 blocs/jour,
  sans rotation dans l'image, jugé négligeable.
- La contrainte « `nightly-sync.sh` fini avant 00:10 UTC » et la mise en garde sur `TZ`
  sont caduques : l'ordre des deux planifications n'importe plus, le retard est borné par
  `PUBLISH_INTERVAL`.

## Tests

- `tests/test_docker_compose.py::TestLmelpExportPublishLoopConfiguration` : entrées NTFY
  égales à celles du backend, `PUBLISH_INTERVAL` exact, volume d'état et son défaut,
  variables présentes dans les deux `.env.*.example`, chemin NAS absolu.
- `tests/test_nightly_sync.py::TestCalibreToMobileDocs` : la page mentionne
  `PUBLISH_INTERVAL`, `ntfy`, `last_status` ; `test_no_stale_anacron_schedule` interdit
  `anacrontab`, `/var/spool/anacron` et `00:10` dans la page, `nightly-sync.sh` et `CLAUDE.md`.
- Docstrings des tests de log existants : anacron → publish-loop.

## Pièges rencontrés

- Les tests `TestMongoDBImageContent` / `TestMongoDBImageBuild` échouent dans le
  devcontainer (pas de daemon Docker) — également sur `main`, sans lien avec ce travail.
- `docker compose config` fonctionne sans daemon ; il a servi à vérifier la résolution
  en n'affichant que les clés et la présence des valeurs (jamais `NTFY_TOPIC` en clair).
- `gh issue develop` base la branche sur `origin/main` : elle embarque `b8c2fc0` (#76),
  absent du `main` local.

## Déploiement

Mergeable avant #153 (variables ignorées par l'ancienne image). Après merge de #153 :
« Update the stack » dans Portainer (Watchtower ne relit pas le compose), vérifier
`Created`, puis attendre une notification ntfy à la prochaine publication.
