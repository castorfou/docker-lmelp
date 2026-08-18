# Image MongoDB personnalisée

Cette documentation détaille les choix de conception pour l'image Docker MongoDB personnalisée utilisée dans la stack LMELP.

## Contexte

L'image officielle MongoDB ne gère pas nativement :
- La rotation automatique des logs (risque de fichiers de plusieurs dizaines de Go)
- Les backups automatisés de la base de données

Pour résoudre ces problèmes, une image custom a été créée avec anacron intégré pour gérer à la fois la rotation des logs et les backups.

## Choix de conception

### 1. Extension de l'image officielle

```dockerfile
FROM mongo:latest
```

**Raison** : Partir de l'image officielle garantit :
- Compatibilité avec MongoDB
- Mises à jour de sécurité automatiques (via Watchtower)
- Pas de réinvention de la roue

### 2. Utilisation d'anacron au lieu de cron

```dockerfile
RUN apt-get update && \
    apt-get install -y \
        anacron \
        gzip \
    && rm -rf /var/lib/apt/lists/*
```

**Raisons** :
- **Portables/desktops** : Anacron exécute les tâches manquées au prochain démarrage
- **Pas de dépendance horaire stricte** : Si la machine est éteinte la nuit, la rotation s'exécute au prochain boot
- **Simplicité** : Pas besoin de système externe sur l'hôte

**Alternative rejetée** : Cron classique
- Ne fonctionne que si le conteneur tourne au moment prévu
- Problématique pour les portables/PC personnels

### 3. Configuration MongoDB embarquée

```dockerfile
COPY config/mongod.conf /etc/mongod.conf
RUN chmod 644 /etc/mongod.conf && \
    chown mongodb:mongodb /etc/mongod.conf
```

**Raisons** :
- **Permissions correctes** : Le fichier appartient à l'utilisateur `mongodb` (UID 999)
- **Immuable** : La configuration ne change pas entre les redémarrages
- **Pas de volume pour la config** : Évite les problèmes de permissions lors des montages

**Alternative rejetée** : Monter `mongod.conf` via volume
- Problème : Le montage écrase le fichier avec des permissions root
- MongoDB (qui tourne en tant qu'utilisateur `mongodb`) ne peut pas le lire

### 4. Répertoire de logs avec volume

```dockerfile
RUN mkdir -p /var/log/mongodb && \
    chown -R mongodb:mongodb /var/log/mongodb && \
    chmod 755 /var/log/mongodb
```

**Raisons** :
- **Persistance** : Les logs survivent aux redémarrages du conteneur
- **Accès depuis l'hôte** : Facile à consulter sans `docker exec`
- **Permissions** : Le répertoire est créé avec les bonnes permissions dans l'image

**Permissions** : L'entrypoint custom (voir section 7) chowne automatiquement ce répertoire vers `mongodb:mongodb` à chaque démarrage du conteneur, y compris récursivement pour le contenu déjà présent — aucune action manuelle n'est nécessaire côté hôte, quelle que soit l'ownership initiale du bind-mount.

### 5. Script de rotation embarqué

```dockerfile
COPY scripts/rotate_mongodb_logs.sh /scripts/rotate_mongodb_logs.sh
RUN chmod +x /scripts/rotate_mongodb_logs.sh
```

**Raisons** :
- **Autonomie du conteneur** : Pas besoin de scripts externes
- **Testabilité** : Facile à tester manuellement
- **Flexibilité** : Peut être appelé manuellement ou via anacron

### 6. Job anacron créé dynamiquement

```dockerfile
RUN echo '#!/bin/bash' > /etc/anacron.daily/mongodb-logrotate && \
    echo '/scripts/rotate_mongodb_logs.sh --compress --keep-days 30 >> /var/log/mongodb/logrotate.log 2>&1' >> /etc/anacron.daily/mongodb-logrotate && \
    chmod +x /etc/anacron.daily/mongodb-logrotate
```

**Raisons** :
- **Simple** : Pas besoin de fichier séparé
- **Paramétrable** : Facile à modifier (keep-days, compress)
- **Logs de rotation** : La sortie est capturée dans `logrotate.log`

### 7. Entrypoint custom avec anacron

```dockerfile
RUN echo '#!/bin/bash' > /docker-entrypoint-anacron.sh && \
    echo 'set -e' >> /docker-entrypoint-anacron.sh && \
    echo '' >> /docker-entrypoint-anacron.sh && \
    echo 'mkdir -p /backups /var/log/mongodb /var/spool/anacron' >> /docker-entrypoint-anacron.sh && \
    echo 'chown -R mongodb:mongodb /backups /var/log/mongodb' >> /docker-entrypoint-anacron.sh && \
    echo 'chown mongodb:mongodb /var/spool/anacron' >> /docker-entrypoint-anacron.sh && \
    echo '' >> /docker-entrypoint-anacron.sh && \
    echo '# Start anacron in the background, as the mongodb user' >> /docker-entrypoint-anacron.sh && \
    echo '(while true; do gosu mongodb anacron -d; sleep 3600; done) &' >> /docker-entrypoint-anacron.sh && \
    echo '' >> /docker-entrypoint-anacron.sh && \
    echo '# Run the original MongoDB entrypoint' >> /docker-entrypoint-anacron.sh && \
    echo 'exec /usr/local/bin/docker-entrypoint.sh "$@"' >> /docker-entrypoint-anacron.sh && \
    chmod +x /docker-entrypoint-anacron.sh

ENTRYPOINT ["/docker-entrypoint-anacron.sh"]
CMD ["mongod"]
```

**Raisons** :
- **Deux processus** : MongoDB et anacron doivent tourner simultanément
- **Chown avant drop de privilège** : `/backups` et `/var/log/mongodb` sont des bind-mounts dont l'ownership dépend de l'hôte, pas de l'image — l'entrypoint les chowne (récursivement, pour corriger aussi le contenu déjà présent) vers `mongodb:mongodb` pendant qu'il tourne encore en root, avant de lancer quoi que ce soit en tant que `mongodb`
- **Anacron en tant que `mongodb`, pas root** : `gosu mongodb anacron -d` plutôt qu'`anacron -d` — sinon les jobs déclenchés (backup, rotation de logs) créent des fichiers appartenant à root sur les volumes montés, incohérent avec le reste des fichiers gérés par mongod (UID 999)
- **`/var/spool/anacron` chowné aussi** : anacron y stocke ses timestamps de dernière exécution ; sans ce chown, l'invocation en tant que `mongodb` ne pourrait pas les mettre à jour
- **Chaîne avec exec** : L'entrypoint MongoDB original prend le contrôle (PID 1)
- **Signal handling** : MongoDB reçoit correctement les signaux (SIGTERM, etc.)

**Alternative rejetée** : Supervisord
- Trop complexe pour juste 2 processus
- Dépendance supplémentaire

## Architecture de la rotation

```
┌─────────────────────────────────────────┐
│         Conteneur MongoDB               │
│                                         │
│  ┌──────────────────────────────────┐  │
│  │   Entrypoint custom              │  │
│  │                                  │  │
│  │   1. Lance anacron -d &          │  │
│  │   2. Exec mongod                 │  │
│  └──────────────────────────────────┘  │
│                                         │
│  ┌──────────────────────────────────┐  │
│  │   Anacron                        │  │
│  │                                  │  │
│  │   - Quotidien (5min après boot)  │  │
│  │   - Exécute mongodb-logrotate    │  │
│  └──────────────────────────────────┘  │
│                 │                       │
│                 ▼                       │
│  ┌──────────────────────────────────┐  │
│  │   rotate_mongodb_logs.sh         │  │
│  │                                  │  │
│  │   1. db.adminCommand({           │  │
│  │        logRotate: 1 })           │  │
│  │   2. Compress old logs (gzip)    │  │
│  │   3. Delete logs > 30 days       │  │
│  └──────────────────────────────────┘  │
│                 │                       │
│                 ▼                       │
│  ┌──────────────────────────────────┐  │
│  │   /var/log/mongodb/              │  │
│  │   (monté depuis l'hôte)          │  │
│  │                                  │  │
│  │   - mongod.log                   │  │
│  │   - mongod.log.2025-11-23...     │  │
│  │   - mongod.log.2025-11-22....gz  │  │
│  └──────────────────────────────────┘  │
└─────────────────────────────────────────┘
                 │
                 │ (volume mount)
                 ▼
        data/logs/mongodb/
        (sur l'hôte)
```

## Mécanisme de rotation MongoDB

MongoDB supporte nativement la rotation de logs via la commande admin `logRotate` :

```javascript
db.adminCommand({ logRotate: 1 })
```

Cette commande :
1. Ferme le fichier de log actuel
2. Le renomme avec un timestamp (ex: `mongod.log.2025-11-23T01-08-47`)
3. Crée un nouveau fichier `mongod.log`

Le paramètre `logRotate: reopen` dans `mongod.conf` indique à MongoDB d'utiliser ce mode.

## Considérations de sécurité

### Utilisateur MongoDB (UID 999)

MongoDB tourne avec l'utilisateur `mongodb` (UID 999, GID 999) et non en root :
- **Sécurité** : Principe du moindre privilège
- **Permissions** : Tous les fichiers doivent appartenir à cet utilisateur
- **Anacron aussi** : les jobs de backup et de rotation de logs, déclenchés par anacron, tournent également sous `mongodb` (via `gosu`) et non root — voir section 7

### Permissions des volumes

Les volumes `/backups` et `/var/log/mongodb` sont des bind-mounts : leur ownership dépend de
l'hôte, pas de l'image. L'entrypoint custom (section 7) les chowne automatiquement vers
`mongodb:mongodb` à chaque démarrage du conteneur, y compris récursivement pour le contenu déjà
présent — aucune action manuelle n'est nécessaire côté hôte, quelle que soit l'ownership initiale
du bind-mount.

## Performance

### Impact de la rotation

- **CPU** : Négligeable (quelques secondes par jour)
- **I/O** : Modéré lors de la compression (gzip)
- **Mémoire** : Faible (anacron + script bash)

### Impact d'anacron

- **CPU** : Quasi-nul (vérifie juste les timestamps)
- **Mémoire** : ~2-3 MB
- **Démarrage** : Aucun impact (lance en background)

## Backup automatisé intégré

Depuis la consolidation de l'architecture (issue #14), le backup MongoDB est intégré directement dans l'image custom au lieu d'utiliser un conteneur séparé.

### Configuration du backup

```dockerfile
# Copy the backup script
COPY scripts/backup_mongodb.sh /scripts/backup_mongodb.sh
RUN chmod +x /scripts/backup_mongodb.sh

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

**Raisons de l'intégration** :
- **Cohérence** : Tous les services de maintenance MongoDB au même endroit
- **Simplicité** : Un seul conteneur au lieu de deux
- **Anacron** : Exécution des backups manqués, adapté aux NAS/PC personnels
- **Variables d'environnement** : Accès aux paramètres du conteneur MongoDB

### Architecture du backup

```
┌─────────────────────────────────────────┐
│         Conteneur MongoDB               │
│                                         │
│  ┌──────────────────────────────────┐  │
│  │   Anacron                        │  │
│  │                                  │  │
│  │   - Quotidien (rotation logs)    │  │
│  │   - Hebdomadaire (backup)        │  │
│  └──────────────────────────────────┘  │
│                 │                       │
│                 ▼                       │
│  ┌──────────────────────────────────┐  │
│  │   backup_mongodb.sh              │  │
│  │                                  │  │
│  │   1. mongodump --db=...          │  │
│  │   2. Clean old backups (> 7w)    │  │
│  │   3. List current backups        │  │
│  └──────────────────────────────────┘  │
│                 │                       │
│                 ▼                       │
│  ┌──────────────────────────────────┐  │
│  │   /backups/                      │  │
│  │   (monté depuis l'hôte)          │  │
│  │                                  │  │
│  │   - backup_2025-11-23_02-00-00/  │  │
│  │   - backup_2025-11-16_02-00-00/  │  │
│  └──────────────────────────────────┘  │
└─────────────────────────────────────────┘
                 │
                 │ (volume mount)
                 ▼
        data/backups/
        (sur l'hôte)
```

### Avantage d'anacron pour le backup

**Scénario typique** : PC personnel éteint le week-end
- **Avec cron** : Le backup prévu dimanche 2h00 ne s'exécute jamais
- **Avec anacron** : Le backup s'exécute lundi matin au démarrage

Anacron garde une trace de la dernière exécution dans `/var/spool/anacron/` et vérifie si le délai est dépassé.

### Publication sur GitHub Container Registry

L'image est automatiquement construite et publiée sur `ghcr.io` via GitHub Actions (`.github/workflows/build-mongo-image.yml`) :

- **Déclencheurs** : Modification du Dockerfile, scripts, ou configuration
- **Tags** : `latest`, versions sémantiques, SHA du commit
- **Registry** : `ghcr.io/castorfou/lmelp-mongo:latest`

**Avantages** :
- Pas besoin de build local pour le déploiement
- Cohérent avec les autres images du projet
- Facilite le déploiement sur Portainer

## Évolutions possibles

### 1. Configuration via variables d'environnement

Actuellement, la rétention (30 jours) est hardcodée. On pourrait ajouter :

```dockerfile
ENV LOG_RETENTION_DAYS=30
ENV LOG_COMPRESS=true
```

### 2. Rotation basée sur la taille

Actuellement : rotation quotidienne. On pourrait ajouter une rotation basée sur la taille :

```bash
if [ $(stat -f%z /var/log/mongodb/mongod.log) -gt 1073741824 ]; then
    # Rotate if > 1GB
fi
```

### 3. Upload vers S3/cloud storage

Après compression, uploader les logs vers un stockage cloud :

```bash
aws s3 cp /var/log/mongodb/*.gz s3://bucket/mongodb-logs/
```

### 4. Métriques de rotation

Exporter des métriques Prometheus sur la rotation :
- Nombre de logs rotés
- Taille totale des logs
- Espace libéré

## Debugging

### Vérifier qu'anacron tourne

```bash
docker exec lmelp-mongo ps aux | grep anacron
```

### Vérifier l'ownership des fichiers de backup/logs

```bash
find data/backups data/logs/mongodb ! -user "$(id -un)"
```

Ne devrait rien remonter (hormis les fichiers internes de mongod lui-même dans `data/mongodb`,
qui appartiennent à l'utilisateur `mongodb` par conception — voir section "Considérations de
sécurité"). Si des fichiers `root:root` apparaissent dans `data/backups` ou
`data/logs/mongodb`, vérifier que l'entrypoint a bien pu chowner ces volumes au démarrage
(`docker compose logs mongo` en début de démarrage).

### Logs d'anacron

```bash
docker compose logs mongo | grep anacron
```

### Tester la rotation manuellement

```bash
docker exec lmelp-mongo /scripts/rotate_mongodb_logs.sh
```

### Vérifier la configuration MongoDB

```bash
docker exec lmelp-mongo cat /etc/mongod.conf
```

## Références

- [MongoDB Log Rotation](https://www.mongodb.com/docs/manual/tutorial/rotate-log-files/)
- [Anacron documentation](https://linux.die.net/man/8/anacron)
- [Docker multi-process containers](https://docs.docker.com/config/containers/multi-service_container/)
