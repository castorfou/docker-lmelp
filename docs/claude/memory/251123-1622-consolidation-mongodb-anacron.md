# Consolidation des services MongoDB avec anacron et publication sur ghcr.io

**Date** : 23 novembre 2025
**Issue** : #14
**Contexte** : Architecture Docker du projet docker-lmelp

## Décision architecturale

Consolidation de tous les services de maintenance MongoDB (rotation des logs + backup) dans une unique image Docker `lmelp-mongo`, utilisant anacron au lieu de cron.

### Avant

**5 conteneurs** :
- `lmelp-mongo` : MongoDB + rotation des logs (anacron)
- `lmelp-mongo-backup` : Service de backup séparé (cron)
- `lmelp` : Front-office
- `lmelp-backend` : Back-office backend
- `lmelp-frontend` : Back-office frontend

### Après

**4 conteneurs** :
- `lmelp-mongo` : MongoDB + rotation des logs + backup (anacron)
- `lmelp` : Front-office
- `lmelp-backend` : Back-office backend
- `lmelp-frontend` : Back-office frontend

## Justification

1. **Cohérence architecturale** : Un seul conteneur pour MongoDB et tous ses services de maintenance
2. **Anacron partout** : Solution homogène compatible avec les machines non 24/7 (NAS, PC personnels)
3. **Simplification** : Suppression d'un conteneur dédié
4. **Publication** : Image disponible sur ghcr.io comme les autres images du projet

## Implémentation technique

### Modifications du Dockerfile MongoDB

**Fichier** : `mongodb.Dockerfile`

Ajouts :
- Script de backup copié dans `/scripts/backup_mongodb.sh`
- Création du dossier `/etc/anacron.weekly`
- Job anacron hebdomadaire pour le backup (tous les 7 jours, délai de 10 min après boot)
- Configuration des variables d'environnement dans le script anacron

```dockerfile
# Create anacron job file for backup (weekly)
RUN echo '#!/bin/bash' > /etc/anacron.weekly/mongodb-backup && \
    echo 'MONGO_HOST=${MONGO_HOST:-localhost}' >> /etc/anacron.weekly/mongodb-backup && \
    echo 'MONGO_PORT=${MONGO_PORT:-27017}' >> /etc/anacron.weekly/mongodb-backup && \
    echo 'MONGO_DATABASE=${MONGO_DATABASE:-masque_et_la_plume}' >> /etc/anacron.weekly/mongodb-backup && \
    echo 'BACKUP_RETENTION_WEEKS=${BACKUP_RETENTION_WEEKS:-7}' >> /etc/anacron.weekly/mongodb-backup && \
    echo 'export MONGO_HOST MONGO_PORT MONGO_DATABASE BACKUP_RETENTION_WEEKS' >> /etc/anacron.weekly/mongodb-backup && \
    echo '/scripts/backup_mongodb.sh >> /var/log/mongodb/backup.log 2>&1' >> /etc/anacron.weekly/mongodb-backup && \
    chmod +x /etc/anacron.weekly/mongodb-backup

# Weekly backup (every 7 days, wait 10 minutes after boot)
RUN echo '7 10 mongodb-backup /etc/anacron.weekly/mongodb-backup' >> /etc/anacrontab
```

### Docker Compose

**Fichier** : `docker-compose.yml`

Changements :
- Suppression complète du service `mongo-backup`
- Mise à jour de l'image vers `ghcr.io/castorfou/lmelp-mongo:latest`
- Conservation de la section `build` pour le développement local

### GitHub Actions

**Fichier** : `.github/workflows/build-mongo-image.yml` (nouveau)

Workflow de build et publication automatique sur ghcr.io :
- Déclencheurs : modification de `mongodb.Dockerfile`, `config/mongod.conf`, scripts de backup/rotation
- Tags : `latest`, versions sémantiques, SHA
- Publication uniquement sur main/master (pas sur PR)

### Tests

**Fichier** : `tests/test_mongodb_image.py` (nouveau)

10 tests d'intégration vérifiant :
- Build de l'image
- Présence d'anacron
- Présence des scripts backup et rotation
- Configuration correcte d'anacrontab (2 jobs)
- Exécutabilité des scripts

## Configuration anacron

### Rotation des logs
- **Fréquence** : Quotidienne (période 1 jour)
- **Délai** : 5 minutes après boot
- **Script** : `/etc/anacron.daily/mongodb-logrotate`
- **Logs** : `/var/log/mongodb/logrotate.log`
- **Rétention** : 30 jours (compressés avec gzip)

### Backup
- **Fréquence** : Hebdomadaire (période 7 jours)
- **Délai** : 10 minutes après boot
- **Script** : `/etc/anacron.weekly/mongodb-backup`
- **Logs** : `/var/log/mongodb/backup.log`
- **Rétention** : 7 semaines (configurable via `BACKUP_RETENTION_WEEKS`)

## Images du projet

Toutes les images sont maintenant publiées sur ghcr.io :
- `ghcr.io/castorfou/lmelp-mongo:latest` (MongoDB + maintenance complète)
- `ghcr.io/castorfou/lmelp:latest` (Front-office)
- `ghcr.io/castorfou/lmelp-backend:latest` (Back-office backend)
- `ghcr.io/castorfou/lmelp-frontend:latest` (Back-office frontend)

## Apprentissages techniques

### Anacron dans Docker

Anacron fonctionne bien dans un conteneur Docker car :
- Il détecte automatiquement les jobs manqués au démarrage
- Adapté aux conteneurs qui ne tournent pas 24/7
- Pas besoin de daemon permanent (contrairement à cron)

### Variables d'environnement dans anacron

Les variables d'environnement du conteneur Docker doivent être explicitement exportées dans le script anacron :

```bash
MONGO_HOST=${MONGO_HOST:-localhost}
export MONGO_HOST
```

Cela permet au script de backup d'accéder aux variables définies dans le `docker-compose.yml`.

### Docker Compose V2

Le projet utilise Docker Compose V2 (intégré à Docker) :
- Commande : `docker compose` (avec espace)
- Ancien : `docker-compose` (avec tiret) est obsolète

## Outils et technologies

- **Anacron** : Planificateur de tâches tolérant aux arrêts système
- **Docker Multi-stage** : Non utilisé ici, mais image optimisée avec nettoyage apt
- **GitHub Container Registry** : Alternative gratuite à Docker Hub
- **pytest** : Tests d'intégration pour l'infrastructure Docker

## Références

- Issue #3 : Backup automatique de la base MongoDB
- Issue #9 : Rotation des logs MongoDB avec anacron (implémentation initiale)
- Issue #13 : Publication de l'image MongoDB sur ghcr.io
- Issue #14 : Epic de consolidation (cette implémentation)

## Commandes utiles

```bash
# Rebuilder et relancer MongoDB
docker compose down
docker compose build mongo
docker compose up -d mongo

# Vérifier les logs anacron
docker compose logs -f mongo

# Vérifier la configuration anacron
docker exec lmelp-mongo cat /etc/anacrontab

# Tester manuellement le backup
docker exec lmelp-mongo /scripts/backup_mongodb.sh

# Vérifier les backups existants
docker exec lmelp-mongo ls -lh /backups
```
