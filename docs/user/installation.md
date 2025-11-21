# Installation de la Stack LMELP

Ce guide vous accompagne dans l'installation complète de la stack LMELP (Le Masque et La Plume) sur votre système.

## Prérequis

### Logiciels requis

#### Docker et Docker Compose

La stack nécessite Docker et Docker Compose installés sur votre système.

#### Portainer (optionnel, recommandé)

Portainer fournit une interface web pour gérer vos stacks Docker.

Accéder à Portainer : `http://localhost:9000` ou `https://localhost:9443`

## Installation de la Stack LMELP

### Étape 1 : Cloner le repository

```bash
# Choisir un emplacement pour la stack
cd /path/to/your/installation

# Cloner le repository
git clone https://github.com/castorfou/docker-lmelp.git
cd docker-lmelp
```

### Étape 2 : Créer la structure des volumes

Les containers Docker ont besoin de répertoires sur l'hôte pour stocker les données persistantes.

```bash
# Créer la structure de répertoires
mkdir -p data/mongodb
mkdir -p data/backups
mkdir -p data/audios
mkdir -p data/logs

# Définir les permissions appropriées
chmod -R 755 data/
```

**Structure créée** :

```
docker-lmelp/
├── data/
│   ├── mongodb/    # Données MongoDB
│   ├── backups/    # Backups MongoDB
│   ├── audios/     # Fichiers audio LMELP
│   └── logs/       # Logs applicatifs
```

### Étape 3 : Configuration des variables d'environnement

Copier le template de configuration et le personnaliser :

```bash
cp .env.example .env
```

Éditer le fichier `.env` avec vos valeurs. Voir le [guide de configuration](configuration.md) pour les détails.

**Configuration minimale requise** :

```bash
# 1. Au moins une clé LLM (choisir selon votre préférence)
GEMINI_API_KEY=votre_cle_gemini_ici
# OU
OPENAI_API_KEY=votre_cle_openai_ici

# 2. Configuration MongoDB (valeurs par défaut fonctionnelles)
# ⚠️  IMPORTANT : Les mêmes valeurs doivent être dupliquées pour compatibilité
MONGO_HOST=localhost
MONGO_PORT=27018
MONGO_DATABASE=masque_et_la_plume

# Variables dérivées (garder les mêmes valeurs)
DB_HOST=localhost
DB_NAME=masque_et_la_plume
MONGODB_URL=mongodb://localhost:27018/masque_et_la_plume

# Les autres variables ont des valeurs par défaut dans docker-compose.yml
```

**Note** : Les variables MongoDB sont dupliquées pour des raisons de compatibilité entre les différentes images Docker. Assurez-vous que `DB_HOST=MONGO_HOST`, `DB_NAME=MONGO_DATABASE`, et que `MONGODB_URL` contient le bon `host:port/database`.

### Étape 4 : Initialiser la base de données (optionnel)

Si vous avez un backup existant à restaurer, placez-le dans `data/backups/` :

```bash
# Exemple : copier un backup existant
cp -r /path/to/backup_2024-11-20_10-00-00 data/backups/
```

Le script d'initialisation détectera automatiquement le backup le plus récent au premier démarrage.

### Étape 5 : Démarrer la stack

**Avec Docker Compose (ligne de commande)** :

```bash
# Démarrer tous les services
docker compose up -d

# Vérifier que les containers sont démarrés
docker compose ps

# Consulter les logs
docker compose logs -f
```

**Avec Portainer** :

Voir le [guide Portainer](portainer.md) pour déployer via l'interface web.

### Étape 6 : Vérifier le déploiement

Une fois les services démarrés, vérifier leur état.

#### Vérification automatique avec Health Checks

Docker Compose inclut des health checks automatiques pour tous les services. Pour voir l'état de santé :

```bash
# Voir l'état de tous les services
docker compose ps

# Sortie attendue :
# NAME                        STATUS
# lmelp-mongo                 Up (healthy)
# lmelp-app                   Up (healthy)
# lmelp-backoffice-backend    Up (healthy)
# lmelp-backoffice-frontend   Up (healthy)
# lmelp-mongo-backup          Up
```

Les services devraient afficher **"Up (healthy)"** une fois complètement opérationnels. Les health checks vérifient automatiquement :

- **MongoDB** : Commande `ping` via mongosh
- **LMELP App** : Endpoint Streamlit `/_stcore/health`
- **Backend API** : Endpoint `/health`
- **Frontend** : Disponibilité du serveur web

**Temps de démarrage** : Attendez 30-60 secondes après `docker compose up` pour que tous les services passent à l'état "healthy".

#### Vérification manuelle (optionnelle)

Si vous souhaitez tester manuellement l'accessibilité :

**LMELP Application** :
```bash
curl http://localhost:8501
# Ou ouvrir dans le navigateur : http://localhost:8501
```

**Back-Office Frontend** :
```bash
curl http://localhost:8080
# Ou ouvrir dans le navigateur : http://localhost:8080
```

**Back-Office API** :
```bash
curl http://localhost:8000/health
# Devrait retourner : {"status":"healthy"}
```

**MongoDB** :
```bash
# Installer mongosh si nécessaire
mongosh --host localhost --port 27018

# Vérifier les bases de données
show dbs
use masque_et_la_plume
show collections
```

## Résolution des problèmes courants

### Les containers ne démarrent pas

```bash
# Vérifier les logs détaillés
docker compose logs

# Vérifier les erreurs par service
docker compose logs mongo
docker compose logs lmelp
docker compose logs backoffice-backend
docker compose logs backoffice-frontend
```

### Problèmes de permissions

```bash
# Réinitialiser les permissions des volumes
sudo chown -R $USER:$USER data/
chmod -R 755 data/
```

### MongoDB n'est pas accessible

Vérifier la variable `DB_HOST` dans `.env` :

- **Linux** : `DB_HOST=172.17.0.1` ou `localhost`
- **NAS avec MongoDB containerisé** : `DB_HOST=mongo`

### Port déjà utilisé

Si un port est déjà utilisé (8501, 8080, 8000), modifier dans `.env` :

```bash
LMELP_PORT=8502
FRONTEND_PORT=8081
BACKEND_PORT=8001
```

**Note** : Le port MongoDB par défaut est déjà **27018** pour éviter les conflits avec une instance existante. Une fois la migration terminée, vous pouvez revenir au port standard 27017 en modifiant `MONGO_PORT=27017`.

## Mise à jour de la stack

### Mise à jour automatique avec Watchtower

Si Watchtower tourne sur votre système, les images seront automatiquement mises à jour.

### Mise à jour manuelle

```bash
# Arrêter la stack
docker compose down

# Télécharger les dernières images
docker compose pull

# Redémarrer la stack
docker compose up -d
```

## Désinstallation

### Arrêter et supprimer les containers

```bash
# Arrêter tous les services
docker compose down

# Supprimer les volumes (⚠️ supprime toutes les données)
docker compose down -v
```

### Supprimer les données sur l'hôte

```bash
# ⚠️ ATTENTION : Cette commande supprime toutes les données
rm -rf data/
```

### Supprimer les images Docker

```bash
# Lister les images
docker images | grep lmelp

# Supprimer les images
docker rmi ghcr.io/castorfou/lmelp:latest
docker rmi ghcr.io/castorfou/lmelp-frontend:latest
docker rmi ghcr.io/castorfou/lmelp-backend:latest
docker rmi mongo:latest
```

## Prochaines étapes

- [Configuration détaillée](configuration.md) : Personnaliser votre installation
- [Gestion des backups](backup-restore.md) : Sauvegarder et restaurer vos données
- [Déploiement Portainer](portainer.md) : Utiliser l'interface graphique
