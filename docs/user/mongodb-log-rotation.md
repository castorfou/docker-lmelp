# Rotation des logs MongoDB - Installation container (Docker)

La stack LMELP inclut un système automatique de rotation des logs MongoDB pour empêcher les fichiers de logs de consommer trop d'espace disque.

## Fonctionnement automatique

### Configuration par défaut

La rotation des logs MongoDB s'effectue automatiquement via **anacron** :

- **Fréquence** : Quotidienne (5 minutes après le démarrage du conteneur, puis tous les jours)
- **Compression** : Les logs rotés sont compressés automatiquement avec gzip
- **Rétention** : 30 jours
- **Emplacement** : `./data/logs/mongodb/`

### Anacron vs Cron

Le système utilise **anacron** au lieu de cron classique car il est adapté aux machines qui ne tournent pas 24h/24 (comme les portables) :

- Anacron exécute les tâches manquées au prochain démarrage
- Pas de perte de rotation même si la machine est éteinte la nuit

## Installation initiale

### Créer le répertoire de logs avec les bonnes permissions

Avant le premier démarrage, créez le répertoire de logs avec les permissions correctes :

```bash
# Créer le répertoire
mkdir -p data/logs/mongodb

# Définir les bonnes permissions (UID 999 = utilisateur mongodb dans le conteneur)
sudo chown -R 999:999 data/logs/mongodb

# Alternative sans sudo (permissions ouvertes)
chmod 777 data/logs/mongodb
```

### Démarrer la stack

```bash
docker compose up -d
```

## Rotation manuelle

Vous pouvez déclencher une rotation manuelle des logs à tout moment :

```bash
# Rotation simple
docker exec lmelp-mongo /scripts/rotate_mongodb_logs.sh

# Rotation avec compression et rétention personnalisée
docker exec lmelp-mongo /scripts/rotate_mongodb_logs.sh --compress --keep-days 60
```

### Options disponibles

- `--compress` : Compresse les logs rotés avec gzip
- `--keep-days N` : Conserve les logs pendant N jours (défaut : 30)

## Vérification

### Vérifier qu'anacron fonctionne

```bash
docker exec lmelp-mongo ps aux | grep anacron
```

Vous devriez voir un processus anacron actif.

### Lister les fichiers de logs

```bash
ls -lh data/logs/mongodb/
```

Vous verrez :
- `mongod.log` : Fichier de log actuel
- `mongod.log.2025-11-23T01-08-47` : Logs rotés (si rotation effectuée)
- `mongod.log.2025-11-22T02-00-00.gz` : Logs compressés

### Consulter les logs de rotation

Les logs de la rotation automatique sont dans :

```bash
docker exec lmelp-mongo cat /var/log/mongodb/logrotate.log
```

## Taille des logs

### Vérifier l'espace disque utilisé

```bash
# Total pour tous les logs MongoDB
du -sh data/logs/mongodb/

# Détail par fichier
du -h data/logs/mongodb/* | sort -h
```

### Libérer de l'espace

Si vous manquez d'espace disque, vous pouvez :

1. **Réduire la rétention** : Modifier le script anacron pour garder moins de jours
2. **Supprimer manuellement les vieux logs** :

```bash
# Supprimer les logs de plus de 7 jours
find data/logs/mongodb/ -name "mongod.log.*" -mtime +7 -delete
```

## Personnalisation

### Modifier la fréquence de rotation

La rotation est configurée dans l'image Docker. Pour la modifier, vous devez reconstruire l'image :

1. Éditer `mongodb.Dockerfile` et modifier la ligne anacron
2. Reconstruire l'image :

```bash
docker compose build mongo
docker compose up -d mongo
```

### Modifier la rétention

Modifier le paramètre `--keep-days` dans le Dockerfile, ligne :

```bash
echo '/scripts/rotate_mongodb_logs.sh --compress --keep-days 30 ...'
```

Changez `30` par le nombre de jours souhaité, puis reconstruisez.

## Dépannage

### Les logs ne se rotent pas automatiquement

1. Vérifier qu'anacron tourne :
```bash
docker exec lmelp-mongo ps aux | grep anacron
```

2. Vérifier les logs d'anacron dans les logs du conteneur :
```bash
docker compose logs mongo | grep anacron
```

3. Tester la rotation manuelle pour identifier le problème :
```bash
docker exec lmelp-mongo /scripts/rotate_mongodb_logs.sh
```

### Erreur de permissions

Si vous obtenez des erreurs de permissions, vérifiez les permissions du répertoire :

```bash
ls -la data/logs/mongodb/
```

Le répertoire doit appartenir à l'UID 999 (utilisateur mongodb).

Correction :
```bash
sudo chown -R 999:999 data/logs/mongodb
```

### Le conteneur ne démarre pas

Vérifiez les logs :
```bash
docker compose logs mongo
```

Erreurs courantes :
- Permissions incorrectes sur `/var/log/mongodb`
- Configuration MongoDB invalide

## Pour aller plus loin

- [Configuration MongoDB](configuration.md) : Personnaliser la configuration MongoDB
- [Gestion des backups](backup-restore.md) : Sauvegarder et restaurer les données
