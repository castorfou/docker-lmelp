# Gestion des Backups MongoDB

Ce guide détaille la gestion des sauvegardes et restaurations de la base de données MongoDB pour LMELP.

## Vue d'ensemble

La stack LMELP inclut un système de backup automatisé qui :

- Crée des backups hebdomadaires de MongoDB avec **anacron**
- Conserve les backups selon une politique de rétention (7 semaines par défaut)
- Permet la restauration manuelle depuis n'importe quel backup
- Fournit des scripts pour l'initialisation et la restauration
- **Adapté aux NAS et PC personnels** : anacron exécute les backups manqués au prochain démarrage

## Backups automatiques

### Configuration par défaut

Le backup est intégré dans le conteneur MongoDB avec anacron :

- **Fréquence** : Vérification quotidienne, exécution si le dernier backup a > 7 jours
- **Délai après démarrage** : 10 minutes
- **Rétention** : 7 semaines (49 jours)
- **Emplacement** : `./data/backups/` (configurable via `BACKUP_PATH`)
- **Format** : `backup_YYYY-MM-DD_HH-MM-SS/`

**Avantage d'anacron** : Contrairement à cron, anacron exécute les tâches manquées. Si votre machine était éteinte au moment prévu, le backup s'exécutera au prochain démarrage.

### Vérifier l'état des backups

#### Lister les backups existants

```bash
# Voir tous les backups
ls -lh data/backups/

# Afficher avec dates de création
ls -lth data/backups/
```

#### Consulter les logs de backup

```bash
# Logs du conteneur MongoDB (inclut les logs anacron)
docker compose logs -f mongo

# Logs de backup spécifiques
docker exec lmelp-mongo cat /var/log/mongodb/backup.log
```

### Forcer un backup manuel

Exécuter le script de backup manuellement (utiliser `FORCE_BACKUP=1` pour ignorer la vérification de date) :

```bash
# Depuis l'hôte
docker exec -e FORCE_BACKUP=1 lmelp-mongo /scripts/backup_mongodb.sh

# Ou entrer dans le container
docker exec -it lmelp-mongo bash
FORCE_BACKUP=1 /scripts/backup_mongodb.sh
```

### Modifier la planification

La logique de planification est double :
1. **Anacron** (dans `mongodb.Dockerfile`) lance le script de backup **tous les jours**.
2. **Le script de backup** (`scripts/backup_mongodb.sh`) vérifie si le dernier backup a plus de 7 jours.

Pour modifier la fréquence réelle (ex: passer à 3 jours) :
1. Modifier le script `scripts/backup_mongodb.sh` pour changer la condition de vérification (actuellement 7 jours).
2. Rebuilder l'image :

```bash
docker compose build mongo
docker compose up -d mongo
```

**Note** : Anacron assure que le script est lancé quotidiennement et à chaque redémarrage du conteneur, garantissant qu'aucun backup n'est manqué si la machine était éteinte.

### Modifier la rétention

Changer la durée de conservation des backups dans `.env` :

```bash
# Conserver les backups pendant 12 semaines
BACKUP_RETENTION_WEEKS=12
```

Redémarrer MongoDB pour appliquer :

```bash
docker compose restart mongo
```

## Restauration depuis un backup

### Lister les backups disponibles

```bash
# Utiliser le script de restauration sans argument
docker exec -it lmelp-mongo /scripts/restore_mongodb.sh
```

Affiche :

```
Available backups:

  backup_2024-11-21_02-00-00
    Size: 1.2G
    Date: 2024-11-21 02:00:15

  backup_2024-11-14_02-00-00
    Size: 1.1G
    Date: 2024-11-14 02:00:12

Usage: /scripts/restore_mongodb.sh <backup_name>
```

### Restaurer un backup spécifique

**⚠️ ATTENTION** : La restauration **supprime et remplace** la base de données existante.

```bash
# Restaurer un backup spécifique
docker exec -it lmelp-mongo-backup /scripts/restore_mongodb.sh backup_2024-11-21_02-00-00
```

Le script demande une confirmation :

```
========================================
MongoDB Restore Started: 2024-11-21 10:30:00
========================================
Host: localhost:27017
Database: masque_et_la_plume
Backup: backup_2024-11-21_02-00-00

⚠️  WARNING: This will DROP the existing database 'masque_et_la_plume' and restore from backup!

Are you sure you want to continue? (yes/no):
```

Taper `yes` pour confirmer.

### Restaurer depuis l'hôte

Si vous préférez exécuter directement depuis l'hôte :

```bash
# S'assurer que MongoDB tourne
docker compose ps mongo

# Exécuter mongorestore
mongorestore \
  --host=localhost \
  --port=27017 \
  --db=masque_et_la_plume \
  --drop \
  data/backups/backup_2024-11-21_02-00-00/masque_et_la_plume
```

## Initialisation depuis un backup existant

### Au premier démarrage

Le script `init_mongo.sh` restaure automatiquement le backup le plus récent si :

1. La base de données n'existe pas encore
2. Des backups sont présents dans `data/backups/`

Pour initialiser avec un backup spécifique :

```bash
# Spécifier le backup à utiliser
INIT_BACKUP_NAME=backup_2024-11-21_02-00-00 docker compose up -d
```

### Initialisation manuelle

```bash
# Entrer dans le container
docker exec -it lmelp-mongo-backup bash

# Exécuter le script d'initialisation
/scripts/init_mongo.sh

# Ou avec un backup spécifique
INIT_BACKUP_NAME=backup_2024-11-21_02-00-00 /scripts/init_mongo.sh
```

## Copier des backups depuis un autre système

### Depuis un autre serveur (SSH)

```bash
# Copier un backup via SSH
scp -r user@old-server:/path/to/backup_2024-11-21_02-00-00 \
    ./data/backups/

# Ou utiliser rsync (recommandé pour grandes tailles)
rsync -avz --progress \
    user@old-server:/path/to/backup_2024-11-21_02-00-00 \
    ./data/backups/
```

### Depuis une sauvegarde locale

```bash
# Copier un backup depuis un disque externe
cp -r /mnt/usb/lmelp-backup/backup_2024-11-21_02-00-00 \
    data/backups/

# Vérifier les permissions
chmod -R 755 data/backups/backup_2024-11-21_02-00-00
```

### Depuis un NAS ou stockage réseau

```bash
# Monter le partage réseau
mount -t cifs //nas-server/backups /mnt/nas -o username=user

# Copier le backup
cp -r /mnt/nas/lmelp/backup_2024-11-21_02-00-00 data/backups/

# Démonter
umount /mnt/nas
```

## Export manuel de la base

### Export complet

```bash
# Créer un backup manuel avec mongodump
docker exec lmelp-mongo mongodump \
  --db=masque_et_la_plume \
  --out=/backups/backup_manual_$(date +%Y-%m-%d_%H-%M-%S)

# Vérifier la création
ls -lh data/backups/
```

### Export d'une collection spécifique

```bash
# Exporter une seule collection
docker exec lmelp-mongo mongodump \
  --db=masque_et_la_plume \
  --collection=emissions \
  --out=/backups/backup_emissions_$(date +%Y-%m-%d)
```

### Export en JSON

```bash
# Exporter en JSON lisible
docker exec lmelp-mongo mongoexport \
  --db=masque_et_la_plume \
  --collection=emissions \
  --out=/backups/emissions_$(date +%Y-%m-%d).json \
  --jsonArray \
  --pretty
```

## Compression des backups

Les backups peuvent occuper beaucoup d'espace. Compressez-les pour économiser du disque.

### Compresser un backup

```bash
# Compresser avec tar + gzip
cd data/backups
tar -czf backup_2024-11-21_02-00-00.tar.gz backup_2024-11-21_02-00-00/

# Vérifier la compression
ls -lh backup_2024-11-21_02-00-00*

# Supprimer le dossier original une fois compressé
rm -rf backup_2024-11-21_02-00-00/
```

### Décompresser un backup

```bash
# Décompresser avant restauration
cd data/backups
tar -xzf backup_2024-11-21_02-00-00.tar.gz

# Restaurer
docker exec -it lmelp-mongo-backup \
  /scripts/restore_mongodb.sh backup_2024-11-21_02-00-00
```

## Sauvegarde sur stockage externe

### Copie automatique vers NAS

Ajouter un script dans `cron/` pour copier les backups vers un NAS :

Créer `scripts/sync_backups_to_nas.sh` :

```bash
#!/bin/bash
# Synchroniser les backups vers un NAS

NAS_PATH="/mnt/nas/lmelp-backups"
BACKUP_PATH="./data/backups"

# Monter le NAS si nécessaire
if ! mountpoint -q /mnt/nas; then
    mount -t cifs //nas-server/backups /mnt/nas -o username=user,password=pass
fi

# Synchroniser
rsync -avz --delete "${BACKUP_PATH}/" "${NAS_PATH}/"

echo "Backups synchronized to NAS at $(date)"
```

Ajouter dans `cron/backup-cron` :

```cron
# Backup MongoDB puis copie sur NAS
0 2 * * 0 /scripts/backup_mongodb.sh && /scripts/sync_backups_to_nas.sh >> /var/log/backup-sync.log 2>&1
```

### Sauvegarde vers cloud (S3, GCS, etc.)

Utiliser `rclone` pour synchroniser vers un stockage cloud :

```bash
# Installer rclone dans le container de backup
# ou exécuter depuis l'hôte

# Configurer rclone
rclone config

# Synchroniser vers S3
rclone sync data/backups/ s3:my-bucket/lmelp-backups/

# Automatiser dans cron
0 3 * * 0 rclone sync /path/to/data/backups/ s3:my-bucket/lmelp-backups/ >> /var/log/cloud-backup.log 2>&1
```

## Vérification de l'intégrité

### Tester un backup

Restaurer sur une instance de test pour vérifier l'intégrité :

```bash
# Démarrer un MongoDB temporaire
docker run -d --name mongo-test -p 27018:27017 mongo:latest

# Restaurer le backup
mongorestore \
  --host=localhost \
  --port=27018 \
  --db=test_restore \
  data/backups/backup_2024-11-21_02-00-00/masque_et_la_plume

# Vérifier les données
mongosh --port 27018
> use test_restore
> db.getCollectionNames()
> db.emissions.countDocuments()

# Nettoyer
docker stop mongo-test
docker rm mongo-test
```

## Stratégie de backup recommandée

### Pour un usage personnel

- **Backups locaux** : Hebdomadaires (dimanche 2h)
- **Rétention** : 7 semaines
- **Copie externe** : Mensuelle vers disque USB/NAS

### Pour un usage professionnel

- **Backups locaux** : Quotidiens (3h du matin)
- **Rétention** : 4 semaines
- **Copie NAS** : Quotidienne (synchronisation après backup)
- **Copie cloud** : Hebdomadaire (dimanche après backup)
- **Test de restauration** : Mensuel

## Dépannage

### Le backup échoue

```bash
# Vérifier les logs
docker compose logs mongo-backup

# Vérifier l'espace disque
df -h data/backups/

# Vérifier les permissions
ls -la data/backups/

# Tester manuellement
docker exec lmelp-mongo-backup /scripts/backup_mongodb.sh
```

### La restauration échoue

```bash
# Vérifier que MongoDB est accessible
docker exec lmelp-mongo-backup mongosh --host localhost --eval "db.version()"

# Vérifier que le backup existe
docker exec lmelp-mongo-backup ls -lh /backups/

# Vérifier les permissions
docker exec lmelp-mongo-backup ls -la /backups/backup_2024-11-21_02-00-00/
```

### Espace disque insuffisant

```bash
# Supprimer les vieux backups manuellement
rm -rf data/backups/backup_2024-10-*

# Ou compresser
cd data/backups
for dir in backup_2024-10-*/; do
    tar -czf "${dir%/}.tar.gz" "$dir" && rm -rf "$dir"
done
```

## Prochaines étapes

- [Configuration](configuration.md) : Personnaliser la rétention et planification
- [Déploiement Portainer](portainer.md) : Gérer les backups via l'interface
