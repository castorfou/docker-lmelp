# Healthcheck Frontend - Endpoint dédié /health

**Date**: 2025-11-25 14:30
**Issue**: #5 - Le health check de lmelp-backoffice-frontend remplit les logs d'activité
**Résolution**: Modification du healthcheck pour utiliser l'endpoint `/health`

## Problème Initial

Le healthcheck Docker du service `lmelp-backoffice-frontend` s'exécutait toutes les 30 secondes avec `curl -f http://localhost:80/`, provoquant :
- Des entrées de log nginx toutes les 30 secondes
- Pollution des logs d'activité avec des requêtes non pertinentes

## Solution Mise en Place

### Côté back-office-lmelp (image frontend)
Dans le repository [castorfou/back-office-lmelp#111](https://github.com/castorfou/back-office-lmelp/issues/111) :
- Ajout d'un endpoint `/health` dans la configuration nginx
- Configuration avec `access_log off` pour ne pas logger ces requêtes
- L'endpoint retourne simplement `200 OK`

### Côté docker-lmelp (ce repository)
Modification du healthcheck dans `docker-compose.yml` ligne 136 :

```yaml
# Avant
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:80"]

# Après
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost/health"]
```

## Points Clés

1. **Séparation des préoccupations** : L'endpoint `/health` est dédié au monitoring, distinct des logs applicatifs
2. **Configuration nginx** : La directive `access_log off` empêche les healthchecks de polluer les logs
3. **Coordination entre repositories** :
   - Modification d'abord dans `back-office-lmelp` (image)
   - Puis dans `docker-lmelp` (orchestration)
4. **Pas de tests TDD** : Modification de configuration Docker, validation fonctionnelle manuelle requise

## Déploiement

Le service tournant sur Portainer sera automatiquement mis à jour au push sur la branche `main` grâce à Watchtower (configuré dans les labels Docker Compose).

## Pattern Réutilisable

Pour tout service avec healthcheck Docker :
1. Créer un endpoint dédié `/health` léger et rapide
2. Configurer le serveur web pour ne pas logger cet endpoint
3. Utiliser cet endpoint dans le healthcheck Docker Compose
4. Conserver les logs applicatifs normaux pour les vraies requêtes utilisateur
