# Issue #64 — Volume audio backend + variables RSS sync + doc Automatisch

## Contexte

`back-office-lmelp#295` ajoute `POST /api/rss/sync` côté backend : synchronisation du
flux RSS "Le Masque et la Plume" avec téléchargement du fichier audio de chaque nouvel
épisode "livres" — déclenché manuellement (bouton UI) ou via un workflow Automatisch
externe hébergé sur le même NAS. Le service `backend` de `docker-lmelp` ne montait
aucun volume audio et ne connaissait aucune des variables nécessaires à cette
fonctionnalité.

## Modifications (commit `5a37967`)

### `docker-compose.yml` — service `backend`

- Nouveau volume : `${AUDIO_PATH:-./data/audios}:/app/audios` — **même variable hôte
  `AUDIO_PATH` que le service `lmelp`**, pour partager le même répertoire et éviter la
  duplication de fichiers audio. Vérifié : pas de nesting (chemin identique, pas un
  sous-dossier de l'un dans l'autre) et même `PUID`/`PGID` par défaut (1000/1000) sur
  les deux services → pas de conflit d'ownership au sens de la règle CLAUDE.md sur les
  volumes imbriqués qui se chownent chacun.
- Nouvelles variables d'environnement :
  ```yaml
  - AUDIO_STORAGE_PATH=/app/audios
  - RSS_MASQUE_ET_LA_PLUME_URL=${RSS_MASQUE_ET_LA_PLUME_URL:-https://radiofrance-podcast.net/podcast09/rss_14007.xml}
  - RSS_DUREE_MINI_MINUTES=${RSS_DUREE_MINI_MINUTES:-15}
  - NTFY_SERVER_URL=${NTFY_SERVER_URL:-}
  - NTFY_TOPIC=${NTFY_TOPIC:-}
  ```
  `AUDIO_STORAGE_PATH` est fixe (même logique que `AUDIO_BASE_PATH` sur `lmelp`), les
  autres suivent le pattern `${VAR:-défaut}` déjà utilisé pour `RSS_LMELP_URL`.

### Tests (TDD) — `tests/test_docker_compose.py`

Nouvelle classe `TestBackendAudioSyncConfiguration` (7 tests), écrite en RED avant la
modification de `docker-compose.yml`, GREEN après. Suit le même style que
`TestPgxConfiguration`/`TestBabelioCacheConfiguration` déjà présentes dans ce fichier
(pattern de test bien établi pour valider `docker-compose.yml` via `yaml.safe_load`,
sans avoir besoin d'un daemon Docker).

### Documentation

- `.env.example` / `.env.nas.example` : nouveau bloc "Synchronisation RSS automatisée"
  (variables commentées par défaut sauf l'URL RSS), commentaire mis à jour sur
  `AUDIO_PATH` pour signaler le partage entre `lmelp` et `backend`.
- `docs/user/configuration.md` : nouvelle sous-section "Synchronisation RSS
  automatisée" sous "Variables Back-Office".
- `docs/user/migration-nas.md` : nouvelle "Étape 10 — Automatiser la synchronisation
  RSS via Automatisch" (action HTTP Request → Custom request vers `/api/rss/sync`,
  réponse JSON attendue, note sur la déduplication `episodes: []`).

## Apprentissage clé pour le déploiement réel

**Le merge de la PR ne suffit pas à appliquer les changements côté NAS.** C'est le même
piège que celui documenté dans CLAUDE.md pour le cache Babelio (issue #45) : Watchtower
ne surveille que les nouvelles images, il ne relit jamais `docker-compose.yml`. Ce
changement ajoutant un nouveau volume + de nouvelles variables d'env sur `backend`,
l'utilisateur doit, après le merge :
1. Récupérer le `docker-compose.yml` à jour sur le NAS (git pull / recopie manuelle)
2. Ajouter les nouvelles variables dans le `.env` de la stack sur le NAS
3. Recréer explicitement le conteneur `backend` (Portainer "Update the stack", ou CLI
   `docker compose up -d --force-recreate backend`)

Validation en conditions réelles prévue par l'utilisateur : rechargement du `.env`,
configuration du workflow Automatisch, puis un nouvel épisode attendu dans le flux RSS
la nuit suivante déclenchera le premier test de bout en bout.

## Environnement de dev — limite connue

`pytest` complet échoue sur `tests/test_mongodb_image.py` (build d'image Docker) dans ce
devcontainer car aucun daemon Docker n'y est accessible (`Cannot connect to the Docker
daemon at unix:///var/run/docker.sock`). Confirmé pré-existant (indépendant de ce
changement) via `git stash` sur la branche de base. Ne pas s'alarmer si ces tests
échouent en local — ils passent en CI où le daemon Docker est disponible.
