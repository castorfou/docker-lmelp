# Fix Portainer Stack Detachment - Issue #22

**Date**: 2025-11-26 00:09
**Issue**: #22 - MongoDB container detaches from Portainer stack after ~10 minutes
**Branch**: `22-portainer-lmelp-mongo-quitte-le-stack-lmelp-stack-apres-quelque-temps`

## Problème Initial

Le container `lmelp-mongo` se détachait systématiquement de la stack Portainer après environ 10 minutes :
- Les 3 autres containers (backend, frontend, frontoffice) restaient attachés à la stack
- MongoDB continuait de fonctionner (l'application restait opérationnelle)
- Impossible de redéployer la stack car le container orphelin créait un conflit de nom

## Diagnostic

### Hypothèses explorées

1. **Dual-process avec anacron** (❌ rejetée) :
   - J'ai d'abord pensé que le processus anacron en background pouvait causer des changements d'état
   - L'utilisateur m'a justement challengé : "Comment fais-tu le lien entre détachement de stack et dual-process ?"
   - Cette hypothèse était incorrecte - le container ne crashait pas, il se détachait juste de la stack Portainer

2. **Watchtower** (❌ rejetée) :
   - Watchtower était actif sur le système
   - Mais les mises à jour d'images sont beaucoup moins fréquentes que le délai de ~10 minutes observé

3. **Directive `build:` dans docker-compose.yml** (✅ cause probable) :
   - Seul MongoDB avait une directive `build:` en plus de `image:`
   - Les 3 autres services utilisaient uniquement `image:`
   - Portainer peut builder l'image localement puis perdre le tracking car les métadonnées diffèrent de l'image du registry

## Solution Implémentée

**Modification dans `docker-compose.yml`** :

```yaml
# AVANT
mongo:
  build:
    context: .
    dockerfile: mongodb.Dockerfile
  image: ghcr.io/castorfou/lmelp-mongo:latest

# APRÈS
mongo:
  image: ghcr.io/castorfou/lmelp-mongo:latest
```

**Rationale** : Utiliser uniquement l'image du registry (comme les 3 autres services qui ne se détachent jamais) devrait résoudre le problème de tracking Portainer.

## Correction Bonus

**Ajout dans `pyproject.toml`** :

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
norecursedirs = ["data", "data/*", ".git", ".venv", "dist", "build", "*.egg"]
```

Les tests pytest échouaient car ils tentaient d'explorer `data/mongodb/` qui contient des fichiers avec des permissions restrictives (créés par le container MongoDB). Cette configuration exclut explicitement le dossier `data/` de la découverte de tests.

## Apprentissages

### Méthodologie de debugging

**Importance de challenger les hypothèses** :
- Ma première hypothèse (anacron dual-process) était trop technique et mal fondée
- L'utilisateur m'a justement demandé d'expliquer le lien de causalité
- Cela m'a forcé à reconsidérer et à chercher une cause plus directe

**Approche méthodique** :
1. Observer les **différences concrètes** entre ce qui fonctionne et ce qui ne fonctionne pas
2. MongoDB (problème) vs autres services (OK) → différence = directive `build:`
3. Tester la solution la plus simple qui explique cette différence

### Spécificités Portainer

**Tracking de stack** :
- Portainer utilise des labels Docker pour tracker les containers d'une stack
- Quand une image est buildée localement vs pullée depuis un registry, les métadonnées peuvent différer
- Cela peut causer une perte de tracking même si le container fonctionne normalement

**Test requis** :
- Cette modification nécessite un test réel dans Portainer (pas possible avec `docker compose up` local)
- L'utilisateur devra redéployer la stack et observer si le détachement persiste

## Validation

- ✅ Syntax docker-compose.yml validée (`docker compose config --quiet`)
- ✅ Tests pytest passent (10/10)
- ✅ Linting ruff passe
- ⏳ Test utilisateur dans Portainer en attente
- ⏳ CI/CD à vérifier après push

## Références

- Issue: #22
- Fichiers modifiés:
  - `docker-compose.yml` (suppression directive `build:`)
  - `pyproject.toml` (ajout config pytest)
