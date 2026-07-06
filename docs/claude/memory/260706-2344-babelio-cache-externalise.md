# Externalisation du cache Babelio (issue #43)

## Contexte

Le service `backend` (back-office-lmelp) dispose d'un cache disque Babelio avec circuit breaker
et fair-use. Sans volume externe, ce cache est perdu à chaque redéploiement Watchtower, ce qui
réintroduit la charge de requêtes et le risque de blocage 403/captcha.

## Ce qui a été fait

### `docker-compose.yml` — service `backend`

Ajout d'un volume externe pour le cache :
```yaml
- ${BABELIO_CACHE_PATH:-./data/cache/babelio}:/cache/babelio
```

Ajout de trois variables d'environnement :
```yaml
- BABELIO_CACHE_DIR=/cache/babelio
- BABELIO_FAIR_SEC=${BABELIO_FAIR_SEC:-2.0}
- BABELIO_CACHE_DAY=${BABELIO_CACHE_DAY:-30}
```

`BABELIO_CACHE_DIR` est **fixe** (pas de variable) car c'est le point de montage interne du
conteneur — seul le chemin hôte (`BABELIO_CACHE_PATH`) est configurable.

### `.env.example`

Deux ajouts :
- Dans la section "Chemins des Volumes" : `BABELIO_CACHE_PATH=./data/cache/babelio`
- Nouvelle section "Configuration Babelio" avec `BABELIO_FAIR_SEC=2.0` et `BABELIO_CACHE_DAY=30`

Le défaut de 30 jours a été choisi délibérément (au lieu du défaut 1.0 de back-office-lmelp
standalone) pour maximiser la persistance du cache en production.

### `data/cache/babelio/.gitkeep`

Répertoire créé avec `.gitkeep` pour que le point de montage existe dès le clone du repo
(cohérence avec `data/backups/`, `data/logs/`, `data/logs/mongodb/`).

### `tests/test_docker_compose.py`

Nouvelle classe `TestBabelioCacheConfiguration` (6 tests) validant :
- Présence des 3 variables d'environnement Babelio dans `backend`
- Valeur fixe de `BABELIO_CACHE_DIR=/cache/babelio`
- Présence d'un volume monté sur `/cache/babelio`
- Utilisation de la variable `BABELIO_CACHE_PATH` pour le chemin hôte

## Décisions techniques

- `BABELIO_CACHE_DAY=30` (pas 1.0) : en prod avec Watchtower, un cache de 30 jours réduit
  drastiquement les requêtes répétées vers Babelio entre deux redéploiements.
- Le chemin interne `/cache/babelio` est cohérent avec le déploiement standalone de
  `back-office-lmelp` (`docker/deployment/docker-compose.yml`).
- Approche TDD : tests RED écrits en premier, puis modifications `docker-compose.yml`.
