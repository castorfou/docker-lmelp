# Backend Healthcheck: Migration vers /health endpoint

**Date**: 2025-11-26 14:43
**Issue**: [#24](https://github.com/castorfou/docker-lmelp/issues/24)
**Branch**: `24-backend-mettre-à-jour-healthcheck-pour-utiliser-health-au-lieu-de`

## Contexte

Le service backend FastAPI dispose maintenant d'un endpoint `/health` dédié (implémenté dans [back-office-lmelp PR #116](https://github.com/castorfou/back-office-lmelp/pull/116)). Cet endpoint est exclu du logging et optimisé pour les healthchecks Docker.

## Problème identifié

Le healthcheck Docker du backend utilisait l'endpoint racine `/` ce qui causait :
- **Pollution des logs** : ~120 lignes par heure de healthcheck (toutes les 30s)
- **Masquage des vraies requêtes** : Difficile d'identifier les vraies requêtes utilisateur
- **Non-conformité** : `/health` est le standard industriel pour les healthchecks

## Solution implémentée

### Modification principale
**Fichier**: `docker-compose.yml` (ligne 108)

```yaml
# AVANT
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/"]

# APRÈS
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
```

### Tests ajoutés
**Fichier**: `tests/test_docker_compose.py` (nouveau fichier)

Suite complète de 6 tests vérifiant :
1. Existence du fichier docker-compose.yml
2. Présence du service backend
3. Configuration du healthcheck
4. **Utilisation de l'endpoint /health** (test principal)
5. Paramètres de timing (interval: 30s, timeout: 10s, retries: 3, start_period: 30s)
6. Best practice check pour le frontend

### Approche TDD suivie

1. **RED** : Écriture des tests qui échouent
   - Test `test_backend_healthcheck_uses_health_endpoint` échouait avec `/` endpoint

2. **GREEN** : Implémentation du fix
   - Modification de docker-compose.yml ligne 108
   - Tests passent (16/16 tests OK)

3. **REFACTOR** : Nettoyage
   - Fix du commentaire ERA001 (linting)
   - Formatage avec ruff

## Points techniques importants

### Choix de l'URL
- ✅ `localhost:8000` : Le curl s'exécute **dans** le container backend lui-même
- ❌ `backoffice-backend:8000` : Serait nécessaire si curl était dans un autre container

### Timing parameters conservés
Les paramètres existants sont appropriés :
- `interval: 30s` : Vérification toutes les 30 secondes
- `timeout: 10s` : Timeout raisonnable
- `retries: 3` : 3 tentatives avant échec
- `start_period: 30s` : Temps de démarrage avant premier check

## Bénéfices

1. **Logs propres** : L'endpoint `/health` est exclu du logging backend
2. **Performance** : `/health` répond rapidement (<100ms, pas de check MongoDB)
3. **Standards** : Suit les best practices industrielles
4. **Cohérence** : Même approche que le frontend ([issue #111](https://github.com/castorfou/back-office-lmelp/issues/111))

## Prérequis de déploiement

⚠️ **CRITIQUE** : L'endpoint `/health` doit exister dans le backend avant cette modification.

Vérifier que [back-office-lmelp PR #116](https://github.com/castorfou/back-office-lmelp/pull/116) est déployée en production.

## Vérification post-déploiement

```bash
# Les logs ne doivent PLUS contenir de healthcheck
docker compose logs -f backend | grep health
# Résultat attendu : AUCUNE ligne

# Vérifier que le container est healthy
docker compose ps
# backend devrait montrer "healthy" dans la colonne STATUS
```

## Workflow de test

Pour ce projet avec déploiement Portainer :
1. Tests locaux (pytest, ruff) → OK
2. Push sur branche feature → OK
3. CI/CD GitHub Actions → Vérification
4. Merge sur main → Validation PR
5. **Test réel** : Portainer pull + update stack
6. **Vérification** : Logs backend propres

## Apprentissages

### Pattern de healthcheck Docker
```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:PORT/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 30s
```

### Test de configuration docker-compose
Utilisation de `yaml.safe_load()` pour parser et tester la configuration :
```python
with open("docker-compose.yml") as f:
    config = yaml.safe_load(f)
backend = config["services"]["backend"]
healthcheck_test = backend["healthcheck"]["test"]
```

### Linting ERA001
Ruff détecte les commentaires ressemblant à du code commenté. Solution :
- Reformuler les commentaires pour qu'ils soient clairement documentaires
- Éviter les structures qui ressemblent à du code dans les commentaires

## Références

- Issue backend : https://github.com/castorfou/back-office-lmelp/issues/115
- PR backend : https://github.com/castorfou/back-office-lmelp/pull/116
- Issue frontend : https://github.com/castorfou/back-office-lmelp/issues/111
- Documentation backend : [251126-1241-issue115-backend-health-logging.md](https://github.com/castorfou/back-office-lmelp/blob/main/docs/claude/memory/251126-1241-issue115-backend-health-logging.md)
