# Issue #71 — Retrait du conteneur Streamlit `lmelp` et URL `lmelp-bo` → `lmelp`

## Contexte

back-office-lmelp remplace l'application Streamlit historique `lmelp`
([back-office-lmelp#302](https://github.com/castorfou/back-office-lmelp/issues/302)) et se
renomme « lmelp » (PWA, titres, icône,
[back-office-lmelp#315](https://github.com/castorfou/back-office-lmelp/issues/315)).
La stack ne doit plus exécuter le service `lmelp` / conteneur `lmelp-frontoffice`
(port 8501), et l'URL publique `lmelp.ascot63.synology.me` sert désormais le frontend du
back-office (`localhost:8081` sur le NAS). `lmelp-bo` disparaît de la doc.

Le reverse proxy DSM et la réinstallation de la PWA sont des **actions manuelles** côté
NAS : le repo ne fait que les documenter.

## Analyse de dépendances (avant suppression)

- `lmelp-export` ne dépend que de `mongo` (`depends_on: mongo: service_healthy`).
- Volumes du service `lmelp` : `AUDIO_PATH` (toujours monté par `backend`),
  `BACKUP_PATH` (toujours monté par `mongo`), `LOG_PATH` et `PGX_KEYS_PATH` (propres à
  `lmelp`, mais `PGX_KEYS_PATH` reste monté par `pgx-keys-watchdog`).
- Variables devenues orphelines : `LMELP_PORT`, `LMELP_MODE`, `DB_LOGS`,
  `RSS_LMELP_URL`, `DB_NAME`, `LOG_PATH`.
- Méthode : calcul en Python des `${VAR` référencées dans `docker-compose.yml` avant et
  après retrait du bloc `lmelp`, croisées avec les `VAR=` des `.env.*.example`. Un premier
  essai en `grep` shell donnait des faux positifs (échappement `\$\{` dans le motif).

## Décisions validées par l'utilisateur

- **Périmètre minimal** : on ne retire que les variables rendues orphelines par le retrait
  du service. Les variables *déjà* non consommées par le compose (`GEMINI_API_KEY`,
  `OPENAI_API_KEY`, `GOOGLE_*`, `LITELLM_API_KEY`, `SEARCH_ENGINE_ID`,
  `BACKUP_RETENTION_WEEKS`) restent dans les `.env.*.example`.
- **Clé PGX historique conservée** : `PGX_KEYS_PATH` / `pgx_lmelp_ed25519` restent dans
  `pgx-keys-watchdog` (commentaires requalifiés « clé historique »).
- **Chemin des logs `lmelp-export` inchangé** : défaut `./data/logs/lmelp-export`
  conservé pour éviter toute migration de données, même si `LOG_PATH` disparaît.

## Modifications

- `docker-compose.yml` : bloc `lmelp` supprimé ; commentaires du watchdog, du `backend`
  (plus de « volume partagé avec lmelp ») et de `lmelp-export` (justification de
  l'imbrication sous `./data/logs`) réécrits.
- `.env.example`, `.env.nas.example` : section « LMELP Application Configuration »
  remplacée par une section « PGX » ; `DB_LOGS`, `RSS_LMELP_URL`, `LMELP_MODE`,
  `LMELP_PORT`, `LOG_PATH` retirés ; commentaires PUID/PGID, `MONGO_LOG_PATH`, clés PGX
  et `AUDIO_PATH` nettoyés des mentions du conteneur `lmelp`.
- `docs/user/migration-nas.md` : étape 8 réduite à une règle `lmelp` HTTPS 443 →
  `localhost:8081`, sans l'avertissement WebSocket propre à Streamlit ; consigne de
  réinstallation de la PWA ; URLs de test des conteneurs ; PUID/PGID limités au `backend`.
- `docs/user/image-2.png` supprimée (capture du préréglage WebSocket DSM, plus référencée).

## Tests

- `tests/test_docker_compose.py` : `TestPgxConfiguration` (service `lmelp`) remplacée par
  `TestStreamlitServiceRemoved` : pas de service `lmelp`, pas de `lmelp-frontoffice`, pas
  de port 8501, plus de `${LMELP_PORT|LMELP_MODE|DB_LOGS|RSS_LMELP_URL|LOG_PATH` dans le
  compose ni dans les `.env.*.example`, aucune occurrence de `lmelp-bo` dans `README.md`
  et `docs/` (hors `docs/claude/memory/`), règle reverse proxy `lmelp` sur le port 8081.
- `TestLmelpExportLogVolumeConfiguration` : test renommé `test_log_volume_default_path`.
- `tests/test_mongodb_image.py::TestDockerComposeLogPathSeparation` : cherchait
  `${LOG_PATH:-…}`, qui disparaît. Généralisé : le défaut de `MONGO_LOG_PATH` ne doit être
  ni imbriqué dans, ni parent d'aucun autre défaut `${*_PATH:-./…}` du compose. La règle
  #51 reste ainsi protégée pour tout futur volume, sans dépendre du service `lmelp`.

## Points d'attention

- **Conteneur orphelin** : retirer un service du compose ne supprime pas son conteneur.
  CLI : `docker compose up -d --remove-orphans`. Portainer : cocher « Prune services »
  lors de « Update the stack », sinon supprimer `lmelp-frontoffice` à la main.
- **PWA** : une PWA installée depuis `lmelp-bo.…` reste liée à cette origine ; il faut la
  désinstaller puis la réinstaller depuis `https://lmelp.ascot63.synology.me`.
- **Tests d'image mongo** (`TestMongoDBImageBuild`, `TestMongoDBImageContent`) : ils
  échouent dans le devcontainer faute de démon Docker (`Cannot connect to the Docker
  daemon`), indépendamment de cette issue.
