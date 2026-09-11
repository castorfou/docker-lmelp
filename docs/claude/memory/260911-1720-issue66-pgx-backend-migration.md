# Issue #66 — Migration de la configuration PGX du service lmelp vers backend

## Contexte

`back-office-lmelp#302` a porté le pipeline de transcription automatisée PGX (station GPU
dédiée, accès SSH/SCP) depuis `lmelp` (page Streamlit **PGX**) vers le service `backend`
de ce déploiement Docker (page `/transcription-pgx`, endpoints `/api/pgx/*`). `lmelp` ne
pilote donc plus la transcription, mais `docker-lmelp` n'avait encore aucune configuration
PGX côté `backend` — seul `lmelp` en avait une (issue #58).

## Décision clé : coexistence plutôt que suppression

Le titre de l'issue ("migrer... vers backend") et les instructions de mise à jour doc
("remplacer, pas étendre") suggéraient une migration complète (suppression de la conf PGX
de `lmelp`). Mais le "À faire" de l'issue ne listait explicitement que des **ajouts** côté
`backend`, sans mention de suppression côté `lmelp`. Question posée à l'utilisateur avant
implémentation (`AskUserQuestion`) : réponse **coexistence** — la conf PGX historique de
`lmelp` (`PGX_KEYS_PATH`, `pgx_lmelp_ed25519`) reste dans `docker-compose.yml`
(non fonctionnelle côté appli mais inoffensive), les tests existants `TestPgxConfiguration`
(issue #58) restent inchangés. Seule la **documentation** (qui décrit l'état fonctionnel
actuel du système, pas l'historique des variables techniques) remplace toutes les
références à la page Streamlit **PGX** par `/transcription-pgx`.

Distinction retenue : la conf `docker-compose.yml` peut légitimement garder du legacy
inoffensif, alors que la doc utilisateur doit décrire uniquement l'état fonctionnel actuel
(cohérent avec la règle "décrire l'état actuel, jamais l'historique" de `CLAUDE.md`).

## Modifications apportées

- `docker-compose.yml` :
  - `backend` : nouveau volume `${PGX_BACKEND_KEYS_PATH:-./data/pgx-keys-backend}:/app/keys`
    + 5 variables d'environnement (`PGX_HOST`, `PGX_USER`,
    `PGX_SSH_KEY_PATH=/app/keys/pgx_ed25519` fixe, `PGX_REMOTE_AUDIO_ROOT`,
    `PGX_REMOTE_TRANSCRIPTION_ROOT`) — réutilise les **mêmes** variables hôte
    `PGX_HOST`/`PGX_USER`/`PGX_REMOTE_*` que `lmelp` (valeurs partagées, seule la clé SSH
    diffère : `pgx_ed25519` vs `pgx_lmelp_ed25519`).
  - `lmelp` : inchangé.
  - `pgx-keys-watchdog` (issue #61) : **étendu** (pas de second service dupliqué) — monte
    en plus `${PGX_BACKEND_KEYS_PATH:-./data/pgx-keys-backend}:/keys-backend` et chmod
    `600`/`644` sur `pgx_ed25519`(`.pub`) en plus de la clé `lmelp` existante. Conforme au
    pattern déjà documenté dans `CLAUDE.md` : "un sidecar watchdog étendu plutôt qu'un
    second service dupliqué".
- Tests (`tests/test_docker_compose.py`, TDD RED puis GREEN) : nouvelle classe
  `TestBackendPgxConfiguration` (7 tests, miroir de `TestPgxConfiguration` mais sur
  `backend`) + extension de `TestPgxKeysWatchdogConfiguration` (2 tests : montage du
  volume backend, chmod de la clé backend — avec vérification explicite que
  `pgx_ed25519` apparaît comme chemin `/pgx_ed25519` et pas seulement comme
  sous-chaîne de `pgx_lmelp_ed25519`).
- `.env.example` / `.env.nas.example` : nouvelle variable `PGX_BACKEND_KEYS_PATH`
  (défaut `./data/pgx-keys-backend`, absolu sur `.env.nas.example`), liens vers le guide
  déplacés de `castorfou.github.io/lmelp/...` vers
  `castorfou.github.io/back-office-lmelp/user/transcription-pgx/`.
- `.gitignore` + `data/pgx-keys-backend/.gitkeep` : miroir du mécanisme d'auto-création
  déjà en place pour `data/pgx-keys/` (issue #58) — **point manqué dans le premier commit
  puis corrigé dans un second commit séparé** après relecture du pattern établi en
  rédigeant la mémoire de session (ne pas refaire cette omission pour un futur volume
  `data/` avec chemin par défaut relatif).
- `docs/user/configuration.md` : section "Variables PGX" réécrite pour décrire le flux
  fonctionnel actuel (backend/`transcription-pgx`), avec un encart `info` explicite sur la
  configuration historique `lmelp` conservée en coexistence ; le paragraphe watchdog
  précise qu'il couvre désormais les deux clés.
- `docs/user/migration-nas.md` : remplacement de toutes les références à la page
  Streamlit **PGX** de `lmelp` par la page `/transcription-pgx` du back-office (étape 1
  liste des répertoires → `pgx-keys-backend`, étape 7 procédure d'autorisation de la clé
  SSH, checklist finale, section "Pipeline de transcription PGX" des limitations connues).
- `README.md` : description du service `pgx-keys-watchdog` et arborescence `data/`
  mises à jour pour mentionner les deux répertoires de clés.

## Process

Spécification détaillée conservée en commentaire sur l'issue avant implémentation
(`gh issue comment 66`), incluant explicitement la décision de coexistence actée avec
l'utilisateur — conforme à l'étape 3 du workflow `/fix-issue`.
