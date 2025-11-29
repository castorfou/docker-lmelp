# Intégration Calibre dans docker-lmelp

**Date** : 2025-11-29
**Issue** : #27
**Contexte** : Intégration de la fonctionnalité Calibre développée dans back-office-lmelp (issue #119)

## Décision d'architecture

### Approche choisie : Montage volume lecture seule

L'intégration Calibre utilise un montage de volume en **lecture seule** (`:ro`) pour accéder à une bibliothèque Calibre existante depuis le back-office LMELP.

**Principes de conception** :
- **Optionnel** : Le système fonctionne normalement sans Calibre configuré
- **Lecture seule** : Montage `:ro` pour éviter toute corruption de la bibliothèque
- **Pas d'installation** : Pas besoin d'installer Calibre dans le conteneur (lecture directe SQLite)
- **Portable** : Support multi-plateforme (NAS Synology, Linux, Mac, Windows)

### Configuration Docker Compose

```yaml
backend:
  volumes:
    - ${CALIBRE_HOST_PATH:-/dev/null}:/calibre:ro
  environment:
    - CALIBRE_VIRTUAL_LIBRARY_TAG=${CALIBRE_VIRTUAL_LIBRARY_TAG:-}
```

**Détails importants** :
- `${CALIBRE_HOST_PATH:-/dev/null}` : Permet de désactiver Calibre si la variable n'est pas définie
- `:ro` : Montage en lecture seule obligatoire pour protéger la bibliothèque
- Pas de variable `CALIBRE_LIBRARY_PATH` : Le backend détecte automatiquement `/calibre` s'il est monté

## Leçon apprise : Portainer et chemins relatifs

**Problème identifié** : Portainer résout les chemins relatifs différemment de Docker Compose CLI.

- **Docker Compose CLI** : résout `./data/logs` depuis le répertoire du `docker-compose.yml`
- **Portainer** : résout `./data/logs` depuis son propre répertoire de travail (`/data/compose/X/`)

**Solution** : Toujours utiliser des **chemins absolus** dans les variables d'environnement pour Portainer.

**Documentation ajoutée** dans `.env.example` :
```bash
# ⚠️  IMPORTANT pour Portainer : Utiliser des chemins ABSOLUS
# Portainer résout les chemins relatifs depuis son propre répertoire de travail,
# pas depuis le répertoire du docker-compose.yml.
```

Cette leçon a été apprise lors de l'issue #27 sur les logs MongoDB et est maintenant appliquée systématiquement pour toutes les nouvelles variables de chemins.

## Fichiers modifiés

1. **docker-compose.yml** : Ajout volume et variable d'environnement au service backend
2. **.env.example** : Nouvelle section "Calibre Integration (Optionnel)" avec exemples par plateforme
3. **docs/user/calibre-setup.md** : Guide complet d'intégration (architecture, configuration, troubleshooting)
4. **docs/user/.pages** : Ajout de la page Calibre dans la navigation

## Fonctionnalités disponibles

Une fois Calibre configuré, le back-office offre :

### API REST
- `/api/calibre/status` : Statut de l'intégration
- `/api/calibre/statistics` : Statistiques de la bibliothèque
- `/api/calibre/books` : Liste des livres avec recherche, pagination et filtres

### Interface web
- Recherche en temps réel (titre, auteur, tags)
- Filtres : tous les livres / lus / non lus
- Tri par titre, auteur, date d'ajout
- Mise en surbrillance des termes de recherche
- Support des colonnes personnalisées Calibre (`#read`, `#paper`, `#text`)

## Considérations de sécurité

### Accès concurrent sécurisé

Calibre et Docker peuvent accéder à la bibliothèque simultanément :
- **Calibre sur PC/NAS** : Lecture et écriture normales
- **Docker (backend)** : Lecture seule via SQLite

**Limitation connue** : Si Calibre écrit dans `metadata.db` pendant que Docker lit, une erreur SQLite "database is locked" peut survenir temporairement. Cette erreur est normale et se résout automatiquement.

## Méthodologie de debugging appliquée

Ce projet a suivi le principe "Comprendre AVANT de contourner" documenté dans CLAUDE.md.

Au lieu d'appliquer des solutions de contournement (chmod 777, supprimer les volumes), nous avons :
1. **Observé** : Collecté les symptômes et logs
2. **Investigué** : Testé les hypothèses méthodiquement (inspect des mounts, vérification permissions)
3. **Compris** : Identifié la cause racine (comportement spécifique de Portainer)
4. **Corrigé** : Appliqué la solution appropriée (chemins absolus)
5. **Documenté** : Partagé l'apprentissage pour éviter que d'autres rencontrent le même problème

Cette approche a permis de découvrir un comportement important de Portainer qui s'applique à toutes les configurations futures.

## Références

- Issue source : castorfou/back-office-lmelp#119
- Documentation complète : https://castorfou.github.io/back-office-lmelp/deployment/calibre-setup/
- Documentation docker-lmelp : https://castorfou.github.io/docker-lmelp/user/calibre-setup/
