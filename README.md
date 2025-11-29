# docker-lmelp

Stack Docker complète pour déployer [LMELP (Le Masque et La Plume)](https://github.com/castorfou/lmelp) avec MongoDB, Back-Office, et système de backup automatisé.

**Déployable facilement** via Docker Compose ou Portainer sur NAS (Synology, QNAP) ou PC personnel.

[![CI](https://github.com/castorfou/docker-lmelp/actions/workflows/ci.yml/badge.svg)](https://github.com/castorfou/docker-lmelp/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/castorfou/docker-lmelp/branch/main/graph/badge.svg)](https://codecov.io/gh/castorfou/docker-lmelp)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Code style: ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)

## ✨ Fonctionnalités

- **Stack complète** : MongoDB + LMELP App + Back-Office (Frontend + Backend)
- **Intégration Calibre** : Accès optionnel à votre bibliothèque Calibre existante depuis le back-office
- **Backups automatisés** : Sauvegardes hebdomadaires de MongoDB avec anacron (adapté aux NAS/PC non 24/7)
- **Rotation des logs** : Rotation automatique quotidienne des logs MongoDB
- **Image MongoDB personnalisée** : Disponible sur ghcr.io avec backup et rotation intégrés
- **Scripts de restauration** : Restauration facile depuis n'importe quel backup
- **Prêt pour Portainer** : Déploiement en un clic via interface graphique
- **Watchtower ready** : Mises à jour automatiques des images Docker
- **Multi-LLM** : Support de plusieurs fournisseurs (Gemini, OpenAI, Azure, LiteLLM)

## 🚀 Démarrage rapide

### Prérequis

- Docker et Docker Compose installés


### Installation

```bash
# 1. Cloner le repository (la structure data/ est créée automatiquement)
git clone https://github.com/castorfou/docker-lmelp.git
cd docker-lmelp

# 2. Créer le répertoire de logs MongoDB avec les bonnes permissions
mkdir -p data/logs/mongodb
sudo chown -R 999:999 data/logs/mongodb
# Alternative sans sudo : chmod 777 data/logs/mongodb

# 3. Configurer les variables d'environnement
cp .env.example .env
nano .env  # Ajouter au moins GEMINI_API_KEY ou OPENAI_API_KEY

# 4. Démarrer la stack
docker compose up -d

# 5. Vérifier l'état (attendez que tous les services soient "healthy")
docker compose ps
```

**Note** : Les services incluent des health checks automatiques. Attendez 30-60 secondes pour que tous les services affichent **"Up (healthy)"** au lieu de simplement "Up".

### Accès aux services

- **LMELP App** (Streamlit) : http://localhost:8501
- **Back-Office Frontend** : http://localhost:8080
- **Back-Office API** : http://localhost:8000
- **MongoDB** : localhost:27018

## 📦 Services inclus

| Service | Image | Port | Description |
|---------|-------|------|-------------|
| **mongo** | ghcr.io/castorfou/lmelp-mongo:latest | 27018 | MongoDB + backup + rotation logs (anacron) |
| **lmelp** | ghcr.io/castorfou/lmelp:latest | 8501 | Application Streamlit |
| **backoffice-backend** | ghcr.io/castorfou/lmelp-backend:latest | 8000 | API Backend |
| **backoffice-frontend** | ghcr.io/castorfou/lmelp-frontend:latest | 8080 | Interface web |

## 📚 Documentation complète

La documentation complète est disponible sur **[castorfou.github.io/docker-lmelp](https://castorfou.github.io/docker-lmelp)**

- **[Installation](https://castorfou.github.io/docker-lmelp/user/installation/)** : Guide d'installation détaillé
- **[Configuration](https://castorfou.github.io/docker-lmelp/user/configuration/)** : Variables d'environnement et personnalisation
- **[Intégration Calibre](https://castorfou.github.io/docker-lmelp/user/calibre-setup/)** : Accès à votre bibliothèque Calibre (optionnel)
- **[Backups & Restauration](https://castorfou.github.io/docker-lmelp/user/backup-restore/)** : Gestion des sauvegardes
- **[Rotation des logs MongoDB](https://castorfou.github.io/docker-lmelp/user/mongodb-log-rotation/)** : Gestion automatique des logs
- **[Déploiement Portainer](https://castorfou.github.io/docker-lmelp/user/portainer/)** : Installation via interface graphique

## 🔧 Configuration minimale

Fichier `.env` minimal pour démarrer :

```bash
# 1. Au moins une clé LLM requise (choisir selon votre préférence)
GEMINI_API_KEY=votre_cle_gemini_ici
# OU
OPENAI_API_KEY=votre_cle_openai_ici

# 2. Configuration MongoDB (valeurs par défaut fonctionnelles)
# ⚠️ Les variables sont dupliquées pour compatibilité entre images
MONGO_HOST=localhost
MONGO_PORT=27018
MONGO_DATABASE=masque_et_la_plume
DB_HOST=localhost
DB_NAME=masque_et_la_plume
MONGODB_URL=mongodb://localhost:27018/masque_et_la_plume

# Chemins des volumes (valeurs par défaut)
MONGO_DATA_PATH=./data/mongodb
BACKUP_PATH=./data/backups
AUDIO_PATH=./data/audios
LOG_PATH=./data/logs
MONGO_LOG_PATH=./data/logs/mongodb
```

**Notes importantes** :
- Les variables MongoDB apparaissent plusieurs fois car différentes images Docker utilisent des noms différents. À terme, cela sera rationalisé dans les applications sources.
- **Sur Portainer** : Utilisez des chemins absolus pour tous les volumes. Les chemins relatifs sont transformés par Portainer.

## 🗂️ Structure du projet

```
docker-lmelp/
├── docker-compose.yml      # Configuration Docker Compose
├── .env.example            # Template de configuration
├── mongodb.Dockerfile      # Image MongoDB custom avec anacron
├── config/                 # Configuration MongoDB
│   └── mongod.conf         # Configuration avec rotation logs
├── scripts/                # Scripts de gestion MongoDB
│   ├── backup_mongodb.sh   # Backup avec rétention
│   ├── restore_mongodb.sh  # Restauration depuis backup
│   ├── rotate_mongodb_logs.sh # Rotation manuelle des logs
│   └── init_mongo.sh       # Initialisation base de données
├── cron/                   # Configuration cron/anacron
│   ├── backup-cron         # Planification backups hebdomadaires
│   └── mongodb-logrotate.anacron # Rotation logs (optionnel host)
├── data/                   # Données persistantes (non versionnées)
│   ├── mongodb/            # Données MongoDB
│   ├── backups/            # Backups MongoDB
│   ├── audios/             # Fichiers audio LMELP
│   └── logs/               # Logs applicatifs et MongoDB
└── docs/                   # Documentation MkDocs
    └── user/               # Documentation utilisateur
        ├── installation.md
        ├── configuration.md
        ├── backup-restore.md
        └── portainer.md
```

## 🔄 Gestion des backups

### Backups automatiques

Par défaut : **backup hebdomadaire** (tous les 7 jours) avec anacron, rétention de **7 semaines**.

**Anacron** : Contrairement à cron, anacron exécute les tâches manquées au prochain démarrage, idéal pour les machines non 24/7 (NAS, PC personnels).

```bash
# Voir les backups existants
ls -lh data/backups/

# Forcer un backup manuel
docker exec lmelp-mongo /scripts/backup_mongodb.sh

# Vérifier les logs de backup
docker exec lmelp-mongo cat /var/log/mongodb/backup.log
```

### Restauration

```bash
# Lister les backups disponibles
docker exec -it lmelp-mongo /scripts/restore_mongodb.sh

# Restaurer un backup spécifique
docker exec -it lmelp-mongo /scripts/restore_mongodb.sh backup_2024-11-21_02-00-00
```

Voir la [documentation complète des backups](https://castorfou.github.io/docker-lmelp/user/backup-restore/) pour plus de détails.

## 🐳 Déploiement Portainer

Portainer fournit une interface graphique pour gérer la stack :

1. Accéder à Portainer : http://localhost:9000
2. **Stacks** → **+ Add stack**
3. Nom : `lmelp-stack`
4. Repository : `https://github.com/castorfou/docker-lmelp`
5. Upload du fichier `.env`
6. Cliquer sur **Deploy the stack**

Guide complet : [Déploiement Portainer](https://castorfou.github.io/docker-lmelp/user/portainer/)

## 🛠️ Commandes utiles

```bash
# Démarrer la stack
docker compose up -d

# Voir l'état des services
docker compose ps

# Consulter les logs
docker compose logs -f

# Arrêter la stack
docker compose down

# Mettre à jour les images
docker compose pull && docker compose up -d

# Redémarrer un service spécifique
docker compose restart lmelp
```

## 🤝 Contribution

Contributions bienvenues ! Pour contribuer :

1. Fork le repository
2. Créer une branche feature : `git checkout -b feature/ma-fonctionnalite`
3. Installer les hooks pre-commit : `pre-commit install`
4. Commiter les changements : `git commit -m 'feat: ajouter fonctionnalité'`
5. Pusher la branche : `git push origin feature/ma-fonctionnalite`
6. Ouvrir une Pull Request

### Développement de la documentation

```bash
# Installer les dépendances de documentation
uv sync --extra docs

# Prévisualiser localement
uv run mkdocs serve

# La documentation sera accessible à http://127.0.0.1:8000/docker-lmelp/
```

## 📄 Licence

Ce projet est sous licence MIT. Voir le fichier [LICENSE](LICENSE) pour plus de détails.

## 🔗 Liens utiles

- **Projet LMELP** : https://github.com/castorfou/lmelp
- **Back-Office LMELP** : https://github.com/castorfou/back-office-lmelp
- **Documentation complète** : https://castorfou.github.io/docker-lmelp
- **Issues** : https://github.com/castorfou/docker-lmelp/issues

## ⭐ Support

Si ce projet vous est utile, n'hésitez pas à lui donner une étoile ⭐ sur GitHub !
