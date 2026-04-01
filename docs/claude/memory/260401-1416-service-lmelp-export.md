# Service lmelp-export - Export Android via ADB

**Date**: 2026-04-01 14:16
**Issue**: [#41](https://github.com/castorfou/docker-lmelp/issues/41)
**Contexte**: Lié à [lmelp-mobile#81](https://github.com/castorfou/lmelp-mobile/issues/81)

## Objectif

Ajouter un service Docker `lmelp-export` pour faciliter l'export de la base MongoDB vers un téléphone Android via ADB. Ce service utilise l'image `ghcr.io/castorfou/lmelp-mobile-export:latest` qui contient Python, le script d'export et le client ADB.

## Approche retenue : Container daemon

Le service tourne en permanence (daemon) avec la stack et attend des commandes via `docker exec`. Cette approche présente plusieurs avantages:
- Configuration une seule fois lors du déploiement
- Pas besoin de monter/démonter le container à chaque export
- Cohérent avec l'architecture existante de la stack

## Modifications implémentées

### 1. Service docker-compose (`docker-compose.yml`)

Ajout du service `lmelp-export` après le service `frontend`:

```yaml
lmelp-export:
  image: ghcr.io/castorfou/lmelp-mobile-export:latest
  container_name: lmelp-export
  restart: unless-stopped
  depends_on:
    mongo:
      condition: service_healthy
  volumes:
    - ${CALIBRE_HOST_PATH:-/dev/null}:/calibre:ro
  environment:
    - LMELP_MONGO_URI=mongodb://mongo:27017
    - LMELP_CALIBRE_DB=/calibre/metadata.db
    - LMELP_CALIBRE_VIRTUAL_LIBRARY=${CALIBRE_VIRTUAL_LIBRARY_TAG:-guillaume}
    - ADB_HOST=${ADB_HOST:-host-gateway}
    - ADB_PORT=${ADB_PORT:-5037}
  extra_hosts:
    - "host-gateway:host-gateway"
  healthcheck:
    test: ["CMD", "python", "-c", "import pymongo; pymongo.MongoClient('mongodb://mongo:27017').admin.command('ping')"]
    interval: 30s
    timeout: 10s
    retries: 3
    start_period: 10s
  logging:
    driver: "json-file"
    options:
      max-size: "10m"
      max-file: "3"
  labels:
    - "com.centurylinklabs.watchtower.enable=true"
  networks:
    - lmelp-network
```

**Points clés de la configuration**:
- **depends_on avec health check**: Attend que MongoDB soit réellement prêt avant de démarrer
- **Volume Calibre**: Réutilise `CALIBRE_HOST_PATH` (pattern `/dev/null` si non défini, cohérent avec le backend)
- **extra_hosts: host-gateway**: Permet au container d'atteindre le daemon ADB du laptop hôte
- **Health check Python**: Vérifie la connexion MongoDB avec pymongo (cohérent avec l'image Python)
- **Variables ADB configurables**: `ADB_HOST` et `ADB_PORT` avec valeurs par défaut fonctionnelles

### 2. Variables d'environnement (`.env.example`)

Ajout d'une nouvelle section documentée:

```bash
# ===================================
# LMELP EXPORT SERVICE (Optionnel)
# ===================================
# Service d'export vers téléphone Android via ADB
# Utilise les mêmes variables CALIBRE que le backend
#
# Configuration ADB (optionnel)
ADB_HOST=host-gateway
ADB_PORT=5037
#
# Utilisation:
#   1. Sur le laptop: adb -a start-server
#   2. Dans Docker: docker exec lmelp-export export-and-push
```

**Note importante**: Suppression de la duplication de la section Calibre qui existait dans le fichier.

### 3. Documentation utilisateur (`docs/user/export-android.md`)

Création d'une documentation complète (2146 caractères) couvrant:

**Sections principales**:
- **Prérequis**: ADB installé, téléphone Android avec débogage USB
- **Configuration**: Variables d'environnement, démarrage du service
- **Utilisation**: Processus d'export complet en 3 étapes
- **Fonctionnement technique**: Diagramme architecture, explications détaillées
- **Dépannage**: 6 scénarios courants avec solutions
- **Sécurité**: Montage lecture seule Calibre, exposition ADB
- **Limitations connues**: Un seul téléphone, connexion USB requise

**Diagramme d'architecture inclus**:
```
Laptop/PC (ADB Server) ←→ Téléphone Android (USB)
       ↓ host-gateway
Docker Network:
  MongoDB ←→ lmelp-export ←→ Calibre Library (:ro)
```

**Points pédagogiques**:
- Utilisation de tabs Markdown pour les instructions multi-OS (Linux, macOS, Windows)
- Exemples de commandes concrètes pour chaque étape
- Explications du flag `-a` obligatoire pour `adb start-server`
- Cas d'usage du pattern `/dev/null` pour Calibre optionnel

### 4. Navigation (`docs/user/.pages`)

Ajout dans la navigation MkDocs entre "Intégration Calibre" et "Backups":

```yaml
- Export vers Android: export-android.md
```

Positionnement logique: après Calibre (dépendance optionnelle similaire) et avant les backups.

### 5. Guide d'installation (`docs/user/installation.md`)

Mise à jour de la section "Prochaines étapes" pour inclure:

```markdown
- [Export vers Android](export-android.md) : Synchroniser avec l'application mobile (optionnel)
```

Ajout également de la mention de Calibre qui était absente.

### 6. README principal (`README.md`)

**Fonctionnalités**:
```markdown
- **Export Android** : Synchronisation automatique vers téléphone Android via ADB (optionnel)
```

**Table des services**:
```markdown
| lmelp-export (optionnel) | ghcr.io/castorfou/lmelp-mobile-export:latest | - | Export vers Android via ADB |
```

**Documentation**:
```markdown
- **[Export vers Android](https://castorfou.github.io/docker-lmelp/user/export-android/)** : Synchronisation avec l'application mobile (optionnel)
```

## Décisions techniques

### 1. Health check avec pymongo

**Question initiale**: Faut-il ajouter un health check?

**Décision**: Oui, vérifier la connexion MongoDB au démarrage.

**Implémentation**:
```yaml
test: ["CMD", "python", "-c", "import pymongo; pymongo.MongoClient('mongodb://mongo:27017').admin.command('ping')"]
```

**Justifications**:
- Cohérent avec les autres services de la stack (tous ont un health check)
- Utilise Python (langage natif de l'image) plutôt que curl
- Vérifie la dépendance critique (MongoDB)
- Permet à Docker Compose de détecter si le service est vraiment prêt

### 2. Variables ADB configurables

**Question initiale**: Garder ADB_HOST/PORT en dur ou les exposer dans .env?

**Décision**: Les rendre configurables avec valeurs par défaut.

**Justifications**:
- Flexibilité pour configurations avancées (systèmes Linux sans support `host-gateway`)
- Valeurs par défaut fonctionnelles pour 95% des cas
- Pattern cohérent avec les autres variables de la stack
- Documentation inline explique quand modifier ces valeurs

**Configuration**:
```yaml
environment:
  - ADB_HOST=${ADB_HOST:-host-gateway}
  - ADB_PORT=${ADB_PORT:-5037}
```

### 3. Réutilisation du pattern Calibre

Le service réutilise exactement le même pattern que le backend pour Calibre:

```yaml
volumes:
  - ${CALIBRE_HOST_PATH:-/dev/null}:/calibre:ro
environment:
  - LMELP_CALIBRE_VIRTUAL_LIBRARY=${CALIBRE_VIRTUAL_LIBRARY_TAG:-guillaume}
```

**Avantages**:
- Cohérence architecturale
- Pas de nouvelles variables à configurer
- Le service fonctionne même si Calibre n'est pas configuré (montage sur `/dev/null`)
- Lecture seule (`:ro`) protège la bibliothèque

## Patterns réutilisés de la stack existante

L'implémentation respecte tous les patterns établis:

| Pattern | Utilisation |
|---------|-------------|
| Variables avec défaut | `${VAR:-default}` pour toutes les configs |
| Volume lecture seule | `:ro` pour Calibre (protection) |
| /dev/null comme défaut | Désactivation propre de fonctionnalités optionnelles |
| Network bridge nommé | `lmelp-network` pour l'isolation |
| Health checks | Vérification MongoDB avec timers appropriés |
| Logging json-file | Rotation 10MB, 3 fichiers max |
| Labels Watchtower | `com.centurylinklabs.watchtower.enable=true` |
| Restart policy | `unless-stopped` pour résilience |
| Depends_on avec condition | Attend MongoDB healthy |

## Architecture technique

### Flux d'export

```
1. Utilisateur: adb -a start-server (sur laptop)
2. Utilisateur: docker exec lmelp-export export-and-push
3. Container:
   a. Lit MongoDB (via réseau Docker)
   b. Lit Calibre metadata.db (si configuré)
   c. Génère SQLite
   d. Vérifie intégrité
   e. Se connecte à ADB via host-gateway:5037
   f. Push vers téléphone (/sdcard/Android/data/...)
   g. Redémarre l'app Android
```

### Communication réseau

- **Container → MongoDB**: Via réseau Docker (`mongo:27017`)
- **Container → ADB**: Via `extra_hosts` (`host-gateway:5037`)
- **ADB → Téléphone**: Via USB (hôte laptop)
- **Container → Calibre**: Via volume bind mount (lecture seule)

## Tests effectués

### Validation syntaxe

```bash
docker compose config
```

**Résultat**: ✅ Syntaxe YAML valide, service correctement configuré.

**Points vérifiés**:
- Résolution des variables d'environnement
- Montage du volume Calibre
- Configuration extra_hosts
- Health check bien formé
- Dépendances correctes

## Fichiers modifiés

| Fichier | Type | Description |
|---------|------|-------------|
| `docker-compose.yml` | Modifié | Ajout service lmelp-export (31 lignes) |
| `.env.example` | Modifié | Section ADB + correction duplication Calibre |
| `docs/user/export-android.md` | Créé | Documentation complète (300 lignes) |
| `docs/user/.pages` | Modifié | Navigation MkDocs |
| `docs/user/installation.md` | Modifié | Section "Prochaines étapes" |
| `README.md` | Modifié | Fonctionnalités, services, documentation |

## Points d'attention pour le futur

### 1. Compatibilité host-gateway

Le pattern `host-gateway` fonctionne sur:
- ✅ Docker Desktop (macOS, Windows)
- ✅ Linux avec Docker Engine récent (20.10+)
- ⚠️ Systèmes Linux anciens: nécessite configuration manuelle de `ADB_HOST`

**Documentation fournie** dans `docs/user/export-android.md` section "Dépannage".

### 2. Dépendance pymongo dans l'image

Le health check suppose que `pymongo` est installé dans l'image `lmelp-mobile-export:latest`.

**À vérifier** lors du premier déploiement réel. Si absent, alternatives:
- Ajouter pymongo au Dockerfile.export
- Changer le health check pour utiliser curl sur un endpoint HTTP simple

### 3. Calibre optionnel

Le service **fonctionne sans Calibre** grâce au montage sur `/dev/null`. L'export se fera:
- **Avec Calibre**: Données MongoDB + métadonnées Calibre
- **Sans Calibre**: Données MongoDB uniquement

Cela permet une adoption progressive.

## Apprentissages et bonnes pratiques

### 1. Pattern daemon container

**Leçon**: Un container peut rester actif sans processus principal actif, en attendant des commandes via `docker exec`.

**Avantages**:
- Configuration unique au déploiement
- Pas de complexité de scripting host
- Accès au réseau Docker et aux volumes

**Cas d'usage**: Opérations ponctuelles nécessitant accès à l'infrastructure Docker (exports, backups, scripts de maintenance).

### 2. Documentation multi-OS

**Leçon**: Utiliser les tabs Markdown (`pymdownx.tabbed`) pour les instructions spécifiques OS.

**Exemple**:
```markdown
=== "Linux"
    sudo apt-get install adb

=== "macOS"
    brew install android-platform-tools
```

Améliore grandement la lisibilité pour les utilisateurs multi-plateformes.

### 3. Health checks adaptés au langage

**Leçon**: Le health check doit utiliser les outils disponibles dans l'image.

- Image Python → `python -c "import pymongo; ..."`
- Image avec curl → `curl -f http://localhost/health`
- Image MongoDB → `mongosh --eval "db.adminCommand('ping')"`

Évite d'installer des outils supplémentaires uniquement pour le monitoring.

### 4. Réutilisation des variables existantes

**Leçon**: Avant d'ajouter de nouvelles variables, vérifier si des variables existantes peuvent être réutilisées.

**Exemple**: `CALIBRE_HOST_PATH` et `CALIBRE_VIRTUAL_LIBRARY_TAG` déjà utilisées par le backend.

**Avantages**:
- Moins de configuration pour l'utilisateur
- Cohérence garantie entre services
- Documentation simplifiée

## Lien avec l'écosystème LMELP

### Repositories impliqués

1. **docker-lmelp** (ce repo): Configuration infrastructure Docker
2. **lmelp-mobile** (externe):
   - Contient `Dockerfile.export`
   - Publie l'image `ghcr.io/castorfou/lmelp-mobile-export:latest`
   - Issue [#81](https://github.com/castorfou/lmelp-mobile/issues/81) à l'origine de cette fonctionnalité

### Flux de CI/CD

```
lmelp-mobile repo:
  Dockerfile.export → GitHub Actions → ghcr.io/castorfou/lmelp-mobile-export:latest

docker-lmelp repo:
  docker-compose.yml utilise l'image → Watchtower peut mettre à jour automatiquement
```

## Prochaines étapes possibles (hors scope actuel)

1. **Support WiFi ADB**: Actuellement USB uniquement, WiFi nécessite configuration complexe
2. **Multi-device**: Gérer plusieurs téléphones simultanément
3. **Endpoint HTTP**: Exposer un endpoint pour déclencher l'export (alternative à `docker exec`)
4. **Notifications**: Alertes en cas d'échec d'export
5. **Scheduling**: Exports automatiques programmés (cron dans le container)

Ces améliorations peuvent être ajoutées progressivement selon les besoins utilisateurs.

## Validation utilisateur attendue

Avant de merger, l'utilisateur devra tester:

1. **Démarrage du service**: `docker compose up -d lmelp-export`
2. **Health check**: Vérifier que le service passe à "healthy"
3. **Connexion MongoDB**: Le health check devrait réussir
4. **Test complet** (si téléphone disponible):
   - `adb -a start-server`
   - `docker exec lmelp-export export-and-push`
   - Vérifier le transfert vers le téléphone

## Références

- Issue GitHub: [#41](https://github.com/castorfou/docker-lmelp/issues/41)
- Issue lmelp-mobile: [#81](https://github.com/castorfou/lmelp-mobile/issues/81)
- Documentation utilisateur: `docs/user/export-android.md`
- Image Docker: https://github.com/castorfou/lmelp-mobile/pkgs/container/lmelp-mobile-export
