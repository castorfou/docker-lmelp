# Configuration de la Stack LMELP

Ce guide détaille toutes les variables de configuration disponibles pour personnaliser votre déploiement LMELP.

## Fichier de configuration

Toutes les variables de configuration sont définies dans le fichier `.env` à la racine du projet.

```bash
# Créer votre fichier de configuration depuis le template
cp .env.example .env

# Éditer avec votre éditeur préféré
nano .env
# ou
vim .env
```

## Variables MongoDB

### Configuration réseau

La stack utilise un **réseau Docker bridge** nommé `lmelp-network`. Les services communiquent entre eux via les noms de services Docker (ex: `mongo`, `backend`).

### Configuration de base

```bash
# Port exposé sur l'hôte (27018 par défaut pour éviter conflit avec instance existante)
MONGO_PORT=27018

# Nom de la base de données
MONGO_DATABASE=masque_et_la_plume

# Activer les logs de requêtes MongoDB
DB_LOGS=true
```

**Note sur le port** : Le port par défaut est **27018** (au lieu de 27017 standard) pour permettre de faire tourner cette stack en parallèle d'une instance MongoDB existante. Une fois la migration terminée, vous pouvez revenir au port 27017 en modifiant `MONGO_PORT=27017` dans `.env`.

**Accès à MongoDB** :
- **Depuis les containers** : `mongodb://mongo:27017/masque_et_la_plume` (port interne 27017)
- **Depuis l'hôte** : `mongodb://localhost:27018/masque_et_la_plume` (port mappé via MONGO_PORT)

## Variables LMELP Application

### Configuration de base

```bash
# Port d'accès à l'application Streamlit
LMELP_PORT=8501

# Nom de la base de données
DB_NAME=masque_et_la_plume

# Activer les logs de requêtes MongoDB
DB_LOGS=true

# URL du flux RSS
RSS_LMELP_URL=https://radiofrance-podcast.net/podcast09/rss_14007.xml

# Mode de l'application
LMELP_MODE=web
```

### API Keys LLM (Large Language Models)

LMELP supporte plusieurs fournisseurs de LLM. **Au moins une clé API doit être configurée** pour utiliser l'application.

#### Google Gemini (recommandé)

```bash
GEMINI_API_KEY=your_gemini_api_key_here
```

**Obtenir une clé** :

1. Aller sur [Google AI Studio](https://console.cloud.google.com/apis/credentials)
2. Créer un projet ou sélectionner un projet existant
3. Activer l'API Gemini
4. Créer une clé API
5. Copier la clé dans `.env`

#### Google Vertex AI

```bash
GOOGLE_PROJECT_ID=your-gcp-project-id
GOOGLE_AUTH_FILE=/path/to/service-account.json
```

**Configuration** :

1. Créer un projet sur [Google Cloud Console](https://console.cloud.google.com)
2. Activer l'API Vertex AI
3. Créer un compte de service
4. Télécharger le fichier JSON d'authentification
5. Placer le fichier dans un volume accessible au container
6. Configurer `GOOGLE_AUTH_FILE` avec le chemin dans le container

#### OpenAI

```bash
OPENAI_API_KEY=sk-...your-openai-key
```

**Obtenir une clé** :

1. Créer un compte sur [OpenAI](https://platform.openai.com)
2. Aller dans [API Keys](https://platform.openai.com/api-keys)
3. Créer une nouvelle clé secrète
4. Copier la clé dans `.env`

#### Azure OpenAI

```bash
AZURE_API_KEY=your-azure-key
AZURE_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_API_VERSION=2024-02-15-preview
```

**Configuration** :

1. Créer une ressource Azure OpenAI
2. Obtenir la clé et l'endpoint depuis le portail Azure
3. Copier les valeurs dans `.env`

#### LiteLLM (modèles locaux)

```bash
LITELLM_API_KEY=your-litellm-key
```

Pour utiliser des modèles locaux (Ollama, LlamaCPP, etc.) via LiteLLM.

### Google Custom Search (recherche web)

```bash
GOOGLE_CUSTOM_SEARCH_API_KEY=your-search-api-key
SEARCH_ENGINE_ID=your-search-engine-id
```

**Configuration** :

1. Créer un projet sur [Google Cloud Console](https://console.cloud.google.com)
2. Activer l'API Custom Search
3. Créer des identifiants API
4. Créer un moteur de recherche sur [Programmable Search Engine](https://programmablesearchengine.google.com/)
5. Copier l'ID du moteur de recherche

Voir le [guide Google Search](https://github.com/castorfou/lmelp/blob/main/docs/readme_google.md) pour plus de détails.

## Variables Back-Office

### Backend API

```bash
# Port de l'API backend
BACKEND_PORT=8000

# URL de connexion MongoDB
MONGODB_URL=mongodb://localhost:27017/masque_et_la_plume
```

La variable `MONGODB_URL` doit correspondre à la configuration MongoDB (même hôte que `DB_HOST`).

### Frontend

```bash
# Port d'accès à l'interface web
FRONTEND_PORT=8080
```

## Chemins des volumes

Ces variables définissent où les données sont stockées sur l'hôte.

```bash
# Répertoire racine des données
DATA_PATH=./data

# Données MongoDB
MONGO_DATA_PATH=./data/mongodb

# Backups MongoDB
BACKUP_PATH=./data/backups

# Fichiers audio LMELP
AUDIO_PATH=./data/audios

# Logs applicatifs (pour logs LMELP app, pas logs Docker)
LOG_PATH=./data/logs
```

**Note sur les logs** :
- `LOG_PATH` est monté dans le container LMELP pour d'éventuels logs applicatifs
- Les logs Docker (stdout/stderr) sont gérés par Docker et accessibles via `docker compose logs`
- Configuration de rotation : 10MB max par fichier, 3 fichiers conservés

**Chemins personnalisés** :

Vous pouvez utiliser des chemins absolus pour stocker les données ailleurs :

```bash
# Exemple : stocker sur un disque dédié
MONGO_DATA_PATH=/mnt/storage/lmelp/mongodb
BACKUP_PATH=/mnt/storage/lmelp/backups
AUDIO_PATH=/mnt/storage/lmelp/audios
LOG_PATH=/mnt/storage/lmelp/logs
```

**Important** : Créer les répertoires avant de démarrer la stack :

```bash
mkdir -p /mnt/storage/lmelp/{mongodb,backups,audios,logs}
chmod -R 755 /mnt/storage/lmelp
```

## Configuration des backups

### Rétention des backups

```bash
# Nombre de semaines de rétention des backups
BACKUP_RETENTION_WEEKS=7
```

Les backups plus anciens que cette durée seront automatiquement supprimés lors de chaque nouveau backup.

### Planification des backups

La planification est définie dans `cron/backup-cron`. Par défaut : **chaque dimanche à 2h du matin**.

Pour modifier la planification, éditer `cron/backup-cron` :

```cron
# Format: minute heure jour_du_mois mois jour_de_la_semaine
0 2 * * 0 /scripts/backup_mongodb.sh >> /var/log/mongo-backup.log 2>&1
```

**Exemples de planifications** :

```cron
# Tous les jours à 3h du matin
0 3 * * * /scripts/backup_mongodb.sh >> /var/log/mongo-backup.log 2>&1

# Tous les lundis à 1h du matin
0 1 * * 1 /scripts/backup_mongodb.sh >> /var/log/mongo-backup.log 2>&1

# Le 1er de chaque mois à 2h
0 2 1 * * /scripts/backup_mongodb.sh >> /var/log/mongo-backup.log 2>&1

# Deux fois par semaine (mardi et vendredi à 2h)
0 2 * * 2,5 /scripts/backup_mongodb.sh >> /var/log/mongo-backup.log 2>&1
```

Après modification, recréer le container de backup :

```bash
docker compose up -d --force-recreate mongo-backup
```


## Validation de la configuration

Après modification du fichier `.env`, valider la configuration :

```bash
# Vérifier que toutes les variables sont définies
docker compose config

# Tester la syntaxe YAML
docker compose config --quiet && echo "Configuration OK" || echo "Erreur de configuration"
```

## Appliquer les modifications

Pour appliquer les changements de configuration :

```bash
# Redémarrer les services affectés
docker compose up -d

# Ou forcer la recréation de tous les containers
docker compose up -d --force-recreate
```

## Sécurité

### Protection du fichier .env

Le fichier `.env` contient des informations sensibles (clés API). **Ne jamais le committer dans Git**.

```bash
# Vérifier que .env est dans .gitignore
cat .gitignore | grep .env

# S'assurer que les permissions sont restrictives
chmod 600 .env
```

### Rotation des clés API

Changer régulièrement vos clés API et mettre à jour le fichier `.env` :

```bash
# Éditer .env avec les nouvelles clés
nano .env

# Redémarrer les services pour prendre en compte les nouvelles clés
docker compose restart lmelp
```

## Exemples de configurations

### Configuration minimale (développement local)

```bash
# MongoDB
MONGO_PORT=27018
MONGO_DATABASE=masque_et_la_plume

# LLM (une seule clé suffit pour tester)
GEMINI_API_KEY=your_key_here

# Chemins par défaut (optionnel, valeurs par défaut dans docker-compose.yml)
MONGO_DATA_PATH=./data/mongodb
BACKUP_PATH=./data/backups
AUDIO_PATH=./data/audios
LOG_PATH=./data/logs
```

### Configuration production (NAS)

```bash
# MongoDB
MONGO_PORT=27018
MONGO_DATABASE=masque_et_la_plume

# LLM (plusieurs clés pour redondance)
GEMINI_API_KEY=your_gemini_key
OPENAI_API_KEY=your_openai_key

# Chemins sur volumes dédiés
MONGO_DATA_PATH=/volume1/lmelp/mongodb
BACKUP_PATH=/volume1/lmelp/backups
AUDIO_PATH=/volume1/lmelp/audios
LOG_PATH=/volume1/lmelp/logs

# Backup avec rétention longue
BACKUP_RETENTION_WEEKS=12
```

## Prochaines étapes

- [Gestion des backups](backup-restore.md) : Sauvegarder et restaurer vos données
- [Déploiement Portainer](portainer.md) : Utiliser l'interface graphique
