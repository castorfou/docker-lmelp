# Configuration Calibre

Cette page explique comment intégrer votre bibliothèque Calibre existante au back-office LMELP.

## Vue d'ensemble

L'intégration Calibre permet d'accéder à votre bibliothèque de livres numériques directement depuis l'interface web du back-office. Cette fonctionnalité est **entièrement optionnelle** : le système fonctionne normalement sans Calibre.

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    NAS Synology (ou PC)                     │
│                                                             │
│  ┌────────────────────────────────────────────────────┐   │
│  │  Bibliothèque Calibre (sur l'hôte)                 │   │
│  │  /volume1/books/Calibre Library/                   │   │
│  │    ├── metadata.db (SQLite)                        │   │
│  │    └── Author/Book Title (ID)/...                  │   │
│  └──────────────────┬─────────────────────────────────┘   │
│                     │ Montage volume Docker (:ro)          │
│                     ▼                                       │
│  ┌────────────────────────────────────────────────────┐   │
│  │  Backend Container (FastAPI)                        │   │
│  │  /calibre/ (lecture seule)                         │   │
│  │    └── metadata.db ← Lecture directe via SQLite    │   │
│  └────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Caractéristiques

- **Lecture seule** : Le volume est monté en `:ro` pour éviter toute modification de votre bibliothèque Calibre
- **Pas d'installation requise** : Le backend lit directement le fichier `metadata.db` via SQLite, aucune installation de Calibre n'est nécessaire dans le conteneur
- **Optionnel** : Le système continue de fonctionner normalement si Calibre n'est pas configuré
- **Accès concurrent sécurisé** : Calibre peut continuer à utiliser la bibliothèque en même temps (lecture seule depuis Docker)

## Configuration

### 1. Prérequis

- Une bibliothèque Calibre existante et fonctionnelle
- Connaître le chemin absolu de votre bibliothèque Calibre sur l'hôte

### 2. Édition du fichier .env

Ouvrez votre fichier `.env` et ajoutez la section Calibre selon votre plateforme :

#### NAS Synology

```bash
# Calibre Integration
CALIBRE_HOST_PATH=/volume1/books/Calibre Library
```

#### Linux

```bash
# Calibre Integration
CALIBRE_HOST_PATH=/home/user/Calibre Library
```

#### Mac

```bash
# Calibre Integration
CALIBRE_HOST_PATH=/Users/username/Calibre Library
```

#### Windows (WSL2 ou Docker Desktop)

```bash
# Calibre Integration
CALIBRE_HOST_PATH=/mnt/c/Users/username/Calibre Library
```

#### Bibliothèque virtuelle (optionnel)

Si vous utilisez des tags dans Calibre pour organiser vos livres, vous pouvez filtrer l'affichage :

```bash
# Tag de bibliothèque virtuelle
CALIBRE_VIRTUAL_LIBRARY_TAG=guillaume
```

### 3. Important pour Portainer

⚠️ **Si vous déployez via Portainer**, vous **DEVEZ** utiliser des chemins absolus.

Portainer résout les chemins relatifs depuis son propre répertoire de travail (`/data/compose/X/`), pas depuis le répertoire du `docker-compose.yml`. Un chemin relatif comme `./data/calibre` sera transformé en `/data/compose/X/data/calibre` au lieu du chemin attendu.

**Exemple correct pour Portainer** :

```bash
# ✅ BON (chemin absolu)
CALIBRE_HOST_PATH=/volume1/books/Calibre Library

# ❌ MAUVAIS (chemin relatif - ne fonctionnera pas dans Portainer)
CALIBRE_HOST_PATH=./data/calibre
```

### 4. Redémarrage des services

Après avoir modifié le fichier `.env`, redémarrez la stack :

```bash
docker compose down
docker compose up -d
```

Ou via Portainer : cliquez sur "Update the stack" puis "Pull and redeploy".

## Vérification

### 1. Vérifier le montage du volume

Vérifiez que le volume Calibre est bien monté dans le conteneur backend :

```bash
docker exec lmelp-backoffice-backend ls -la /calibre
```

Vous devriez voir le contenu de votre bibliothèque Calibre, notamment le fichier `metadata.db`.

### 2. Vérifier l'API Calibre

Vérifiez que l'API Calibre répond correctement :

```bash
# Status de Calibre
curl http://localhost:8000/api/calibre/status

# Statistiques de la bibliothèque
curl http://localhost:8000/api/calibre/statistics

# Liste des livres (10 premiers)
curl "http://localhost:8000/api/calibre/books?limit=10"
```

### 3. Vérifier l'interface web

Accédez à l'interface web du back-office : `http://localhost:8080`

Vous devriez voir un nouvel onglet "Calibre" avec :
- Barre de recherche temps réel
- Filtres : tous les livres / lus / non lus
- Options de tri
- Liste des livres avec mise en surbrillance des termes de recherche

## Fonctionnalités disponibles

### API REST

Le backend expose trois endpoints principaux :

- **`/api/calibre/status`** : Vérifie si Calibre est configuré et accessible
- **`/api/calibre/statistics`** : Statistiques de la bibliothèque (nombre de livres, livres lus, etc.)
- **`/api/calibre/books`** : Liste des livres avec support de la recherche, pagination et filtres

### Interface web

L'interface web offre :
- **Recherche en temps réel** : Recherche par titre, auteur, tags
- **Filtres** : Tous les livres / Lus / Non lus
- **Tri** : Par titre, auteur, date d'ajout
- **Mise en surbrillance** : Les termes de recherche sont surlignés en jaune
- **Colonnes personnalisées** : Support de `#read`, `#paper`, `#text`

## Troubleshooting

### Le backend ne démarre pas après avoir activé Calibre

**Symptômes** : Le conteneur backend redémarre en boucle ou affiche des erreurs dans les logs.

**Causes possibles** :
1. Le chemin `CALIBRE_HOST_PATH` est incorrect ou n'existe pas
2. Le répertoire n'est pas accessible (permissions)
3. Le chemin est relatif dans Portainer

**Solutions** :
1. Vérifiez que le chemin existe sur l'hôte : `ls -la "/volume1/books/Calibre Library"`
2. Vérifiez les permissions du répertoire
3. Si vous utilisez Portainer, assurez-vous d'utiliser un **chemin absolu**
4. Consultez les logs du backend : `docker logs lmelp-backoffice-backend`

### L'API Calibre renvoie "Calibre not configured"

**Symptômes** : `GET /api/calibre/status` renvoie `{"configured": false}`

**Causes possibles** :
1. La variable `CALIBRE_HOST_PATH` n'est pas définie dans `.env`
2. Le volume n'est pas monté correctement
3. Le fichier `metadata.db` n'existe pas dans la bibliothèque

**Solutions** :
1. Vérifiez que `CALIBRE_HOST_PATH` est bien défini dans `.env`
2. Vérifiez le montage : `docker exec lmelp-backoffice-backend ls -la /calibre`
3. Vérifiez que `metadata.db` existe : `docker exec lmelp-backoffice-backend ls -la /calibre/metadata.db`

### Les livres n'apparaissent pas dans l'interface web

**Symptômes** : L'interface Calibre s'affiche mais la liste des livres est vide.

**Causes possibles** :
1. Le tag de bibliothèque virtuelle est trop restrictif
2. Tous les livres sont filtrés par un critère de recherche
3. La bibliothèque Calibre est réellement vide

**Solutions** :
1. Supprimez ou modifiez `CALIBRE_VIRTUAL_LIBRARY_TAG` dans `.env`
2. Réinitialisez les filtres de recherche dans l'interface web
3. Vérifiez les statistiques via `/api/calibre/statistics`

### Erreur "database is locked"

**Symptômes** : Erreur SQLite "database is locked" dans les logs du backend.

**Cause** : Calibre est en train d'écrire dans `metadata.db` en même temps que Docker tente de le lire.

**Solution** :
- Ce problème est temporaire et se résout automatiquement
- Le montage en lecture seule (`:ro`) empêche Docker de modifier la base de données
- Calibre peut continuer à utiliser la bibliothèque normalement
- Si le problème persiste, fermez Calibre temporairement et redémarrez le backend

## Considérations de sécurité

### Lecture seule

Le volume Calibre est monté en **lecture seule** (`:ro`) dans Docker. Cela signifie que :
- Le backend ne peut **jamais** modifier votre bibliothèque Calibre
- Vos données sont protégées contre toute modification accidentelle
- Vous pouvez continuer à utiliser Calibre normalement sur votre PC/NAS

### Accès concurrent

Calibre et Docker peuvent accéder à la bibliothèque simultanément :
- **Calibre sur PC/NAS** : Lecture et écriture normales
- **Docker (backend)** : Lecture seule via SQLite

Limitations :
- Si Calibre écrit dans `metadata.db` pendant que Docker lit, une erreur "database is locked" peut survenir temporairement
- Cette erreur est normale et se résout automatiquement après quelques secondes
- Pour une expérience optimale, évitez d'éditer massivement la bibliothèque Calibre pendant que le backend l'utilise

## Désactivation de Calibre

Pour désactiver l'intégration Calibre :

1. Commentez ou supprimez `CALIBRE_HOST_PATH` dans votre fichier `.env` :

```bash
# CALIBRE_HOST_PATH=/volume1/books/Calibre Library
```

2. Redémarrez la stack :

```bash
docker compose down
docker compose up -d
```

L'onglet Calibre disparaîtra de l'interface web et les endpoints API renverront `{"configured": false}`.

## Références

- [Documentation Calibre officielle](https://calibre-ebook.com/)
- [Format de base de données Calibre](https://manual.calibre-ebook.com/db_api.html)
- [Dépôt back-office-lmelp](https://github.com/castorfou/back-office-lmelp)
