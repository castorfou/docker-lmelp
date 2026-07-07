# Diagnostic issue #45 — Le cache Babelio ne se remplit pas

**Date**: 2026-07-07 01:00
**Issue**: #45 - le cache babelio ne se remplit pas
**Branch**: `45-le-cache-babelio-ne-se-remplit-pas`

## Problème initial

Après le merge de la PR #44 (issue #43, externalisation du volume + variables d'env
`BABELIO_CACHE_DIR`/`BABELIO_FAIR_SEC`/`BABELIO_CACHE_DAY` pour le service `backend`), le
répertoire hôte `data/cache/babelio/` restait vide, alors que la page de contrôle Babelio du
back-office affichait bien des entrées de cache.

## Diagnostic

`docker-compose.yml` était **correct** dès le départ (volume
`${BABELIO_CACHE_PATH:-./data/cache/babelio}:/cache/babelio` + env `BABELIO_CACHE_DIR=/cache/babelio`
sur `backend`) — pas de bug de configuration dans ce repo.

Investigation du code applicatif de `back-office-lmelp` (repo séparé, lu via GitHub car le code
n'est pas vendored ici) :
- `back_office_lmelp/settings.py::babelio_cache_dir` lit `BABELIO_CACHE_DIR`, avec un défaut
  interne `<cwd>/data/processed/babelio_cache` si la variable est absente.
- `back_office_lmelp/app.py` (lifespan) attache `babelio_service.cache_service =
  BabelioCacheService(cache_dir=settings.babelio_cache_dir, ...)` au démarrage ; les endpoints
  `/api/babelio/status` et `/api/babelio/cache/entries` lisent ce même `cache_service`.

**Preuve terrain** (inspection directe du conteneur `backend` par l'utilisateur) : `/cache`
n'existait pas du tout dans le conteneur, et les `.json` du cache étaient bien présents sous
`/app/data/processed/babelio_cache` — le chemin de repli interne. Le conteneur `backend` en cours
d'exécution ne connaissait donc pas encore `BABELIO_CACHE_DIR`.

**Root cause confirmée** : depuis le merge de la PR #44, seul **Watchtower** avait tourné (mise à
jour de l'image `backend`), sans redéploiement manuel de la stack. Watchtower ne fait que
surveiller les nouvelles images et recrée le conteneur avec **la configuration Docker déjà en
place** (mêmes volumes, mêmes variables d'env) — il ne relit jamais `docker-compose.yml`. Un
changement structurel du compose file (nouveau volume, nouvelles variables d'env) nécessite donc
un redéploiement complet de la stack, pas juste une mise à jour d'image.

## Complication rencontrée lors de la correction en prod

La stack Portainer (`lmelp-stack`) était en statut **"Limited" / "created outside of Portainer"**,
rendant le bouton "Update the stack" peu fiable. Contournement CLI testé et validé :

```bash
# 1. Retrouver le nom du projet Compose utilisé par Portainer pour cette stack
docker inspect lmelp-mongo --format '{{index .Config.Labels "com.docker.compose.project"}}'
# → lmelp-stack

# 2. Recréer uniquement le backend avec ce nom de projet
docker compose -p lmelp-stack up -d --force-recreate backend
```

⚠️ Sans `-p lmelp-stack`, `docker compose up -d` dérive le nom de projet du nom du dossier
courant (`docker-lmelp`), différent du nom utilisé par Portainer — ce qui crée un nouveau réseau
et provoque un conflit sur les noms de conteneurs fixes (`container_name: lmelp-mongo`, etc.)
déjà utilisés par le projet `lmelp-stack`.

## Modifications apportées

Pas de changement à `docker-compose.yml` ni `.env.example` (déjà corrects, déjà couverts par
`TestBabelioCacheConfiguration` dans `tests/test_docker_compose.py`). Le fix est purement
documentaire :

- `docs/user/configuration.md` : nouvel encart d'avertissement dans la section "Cache Babelio"
  (limite de Watchtower, commandes de vérification `docker exec`/`docker inspect`, contournement
  CLI pour le cas Portainer "Limited" avec le nom de projet Compose).
- `CLAUDE.md` : nouveau paragraphe "Watchtower ne réapplique pas les changements de
  `docker-compose.yml`", à la suite de la section "Méthodologie de debugging" existante (qui
  documentait déjà un piège similaire pour la résolution des chemins Portainer).
- `.gitignore` : ajout de `data/cache/*` (commit de l'utilisateur, hors session Claude, suite à
  son test local qui a rempli `data/cache/babelio/` de vrais fichiers de cache) — complété par
  `!data/cache/babelio/.gitkeep` pour rester cohérent avec le pattern déjà utilisé pour
  `data/mongodb/`, `data/backups/`, `data/audios/` et `data/logs/` (garder la structure, ignorer
  le contenu).

## Apprentissages

### Deuxième variante du piège "Portainer résout la config différemment"

Le projet documentait déjà dans `CLAUDE.md` le piège des chemins relatifs résolus différemment
par Portainer (issue MongoDB logs). Cette issue révèle une **deuxième variante** du même type de
piège opérationnel, orthogonale à la première : ce n'est pas la résolution de chemin qui pose
problème ici, mais le fait que **Watchtower et Portainer ne partagent pas la même vision de la
configuration** — Watchtower recrée un conteneur à l'identique (sauf l'image), Portainer peut
perdre le tracking d'une stack (cf. `251126-0009-portainer-stack-detachment-fix.md` pour un
précédent lié, mais avec un mécanisme différent : directive `build:` causant un détachement du
conteneur `mongo` seul). Dans ce cas-ci, c'est la stack entière qui est passée en "Limited".

### Investigation cross-repo

Ce repo (`docker-lmelp`) ne contient que l'orchestration Docker ; le code applicatif du cache
Babelio vit dans `back-office-lmelp` (repo séparé). Pour diagnostiquer une issue dont le symptôme
touche un volume de ce repo mais dont la cause peut être applicative, il a été nécessaire de lire
le code source de `back-office-lmelp` via `gh search code` / `curl` sur `raw.githubusercontent.com`
(pas de submodule, pas de vendoring local) — `back_office_lmelp/settings.py`,
`back_office_lmelp/app.py`, `back_office_lmelp/services/babelio_cache_service.py`.

### Valeur de la preuve terrain avant de conclure

L'hypothèse initiale (Watchtower + pas de redéploiement) reposait sur la lecture de code et un
raisonnement par déduction. Elle n'a été confirmée qu'après que l'utilisateur a directement
inspecté le conteneur en prod (`docker exec` puis `ls /` et `ls /app/data/processed/`). Cette
preuve terrain a évité de partir sur un fix incorrect (ex. modifier `docker-compose.yml` alors
qu'il n'y avait rien à corriger côté configuration).

### Pas de test pytest pour un simple avertissement de prose

J'avais initialement ajouté un `tests/test_documentation.py` avec 3 assertions `in content` sur
`docs/user/configuration.md`, en RED/GREEN. L'utilisateur l'a supprimé : "ça n'ajoute rien ce
test". Un test qui vérifie juste la présence de mots-clés dans de la documentation prose n'a pas
de valeur réelle (il ne prévient d'aucune régression fonctionnelle, il est fragile si le texte est
reformulé). Ne pas reproduire ce réflexe de "TDD partout" pour des changements purement
documentaires — le TDD RED/GREEN de ce workflow s'applique au code, pas à la prose.

## Références

- Issue : #45
- Commentaire de diagnostic posté sur l'issue :
  https://github.com/castorfou/docker-lmelp/issues/45#issuecomment-4898292602
- Fichiers modifiés :
  - `docs/user/configuration.md` (avertissement Cache Babelio)
  - `CLAUDE.md` (paragraphe Watchtower)
  - `.gitignore` (négation `.gitkeep` pour `data/cache/babelio/`)
- Mémoire liée : `260706-2344-babelio-cache-externalise.md` (PR #44),
  `251126-0009-portainer-stack-detachment-fix.md` (précédent lié aux pertes de tracking Portainer)
