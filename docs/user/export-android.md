# Export vers Android

Le service `lmelp-export` permet d'exporter automatiquement la base de données MongoDB vers un téléphone Android via ADB. Cette fonctionnalité facilite la synchronisation des données avec l'application mobile LMELP.

## Prérequis

### Sur le laptop/PC

- **ADB (Android Debug Bridge)** installé
- Téléphone Android branché en USB avec le débogage USB activé
- Docker et docker compose fonctionnels

### Sur le téléphone Android

- Application LMELP Mobile installée
- Débogage USB activé (Paramètres → Options développeur)
- Câble USB connecté au laptop

### Installation d'ADB

=== "Linux (Ubuntu/Debian)"
    ```bash
    sudo apt-get update
    sudo apt-get install android-tools-adb
    ```

=== "macOS"
    ```bash
    brew install android-platform-tools
    ```

=== "Windows"
    Télécharger [Platform Tools](https://developer.android.com/tools/releases/platform-tools) et ajouter au PATH.

## Configuration

### Variables d'environnement

Le service utilise les variables suivantes dans le fichier `.env`:

```bash
# Configuration Calibre (optionnel - partagée avec le backend)
CALIBRE_HOST_PATH=/volume1/books/Calibre Library
CALIBRE_VIRTUAL_LIBRARY_TAG=guillaume

# Configuration ADB (optionnel - valeurs par défaut)
ADB_HOST=host-gateway
ADB_PORT=5037

# Log de la boucle de publication (publish-data-release.log)
LMELP_EXPORT_LOG_PATH=./data/logs/lmelp-export

# État ok/échec de la boucle de publication (last_status)
LMELP_EXPORT_STATE_PATH=./data/logs/lmelp-export-state

# Intervalle de publication automatique, en secondes (0 = désactivée)
# PUBLISH_INTERVAL=3600
```

**Valeurs par défaut**:

- `ADB_HOST=host-gateway`: Permet au container d'atteindre le daemon ADB du laptop
- `ADB_PORT=5037`: Port standard du daemon ADB
- `LMELP_EXPORT_LOG_PATH=./data/logs/lmelp-export`: Persiste sur l'hôte le log de la boucle de publication (`publish-data-release.log`), qui sans ce volume reste piégé dans le conteneur et disparaît à chaque recréation
- `LMELP_EXPORT_STATE_PATH=./data/logs/lmelp-export-state`: Persiste le dernier statut de publication (`last_status`), pour que la notification ntfy de rétablissement parte aussi après une recréation du conteneur
- `PUBLISH_INTERVAL=3600`: Délai entre deux publications automatiques (voir ci-dessous)

Ces valeurs conviennent dans la plupart des cas. Modifiez-les uniquement si vous avez une configuration ADB personnalisée.

`LMELP_EXPORT_LOG_PATH` et `LMELP_EXPORT_STATE_PATH` peuvent être placés sous `./data/logs` (contrairement à `MONGO_LOG_PATH`) : `lmelp-export` tourne en root, sans jamais dropper de privilège, et aucun service de la stack ne modifie l'ownership de `./data/logs`.

### Démarrage du service

Le service `lmelp-export` démarre automatiquement avec la stack Docker:

```bash
docker compose up -d
```

Pour vérifier que le service est actif:

```bash
docker compose ps lmelp-export
```

Vous devriez voir:

```
NAME            IMAGE                                        STATUS
lmelp-export    ghcr.io/castorfou/lmelp-mobile-export:latest Up (healthy)
```

## Utilisation

### Processus d'export complet

1. **Démarrer le daemon ADB** sur le laptop (avec flag `-a` pour écoute réseau):

    ```bash
    adb -a start-server
    ```

    Le flag `-a` est **obligatoire** pour que ADB écoute sur toutes les interfaces (0.0.0.0), permettant au container Docker d'y accéder.

2. **Vérifier la connexion du téléphone**:

    ```bash
    adb devices
    ```

    Vous devriez voir votre téléphone listé:

    ```
    List of devices attached
    ABC123XYZ    device
    ```

3. **Lancer l'export depuis Docker**:

    ```bash
    docker exec lmelp-export export-and-push
    ```

    Cette commande:
    - Exporte MongoDB vers SQLite (avec données Calibre si configuré)
    - Vérifie l'intégrité de la base exportée
    - Transfert via `adb push` vers le téléphone
    - Redémarre l'application Android pour charger les nouvelles données

### Fonctionnement technique

Le container `lmelp-export`:

1. **Reste actif en permanence** (daemon) mais ne consomme presque aucune ressource
2. **Attend des commandes** via `docker exec`
3. **Se connecte à MongoDB** via le réseau Docker (`mongo:27017`)
4. **Monte Calibre en lecture seule** (même configuration que le backend)
5. **Communique avec ADB** du laptop via `host-gateway`

```
┌─────────────────┐
│  Laptop/PC      │
│                 │
│  ADB Server     │ ←─────┐
│  (port 5037)    │        │
└─────────────────┘        │
         ↑                 │
         │ USB             │ host-gateway
         ↓                 │
┌─────────────────┐        │
│  Téléphone      │        │
│  Android        │        │
└─────────────────┘        │
                           │
┌──────────────────────────┼────────────────┐
│  Docker Network          │                │
│                          │                │
│  ┌───────────┐    ┌──────▼──────┐        │
│  │  MongoDB  │◄───│ lmelp-export│        │
│  └───────────┘    └─────────────┘        │
│                          ▲                │
│                          │ :ro            │
│                   ┌──────┴──────┐         │
│                   │   Calibre   │         │
│                   │   Library   │         │
│                   └─────────────┘         │
└───────────────────────────────────────────┘
```

## Publication automatique sur GitHub Release

En complément de l'export vers un téléphone Android, le container `lmelp-export` propose la commande `export-and-publish-release`, qui exporte `lmelp.db`, génère des métadonnées (taille, SHA-256, date d'export) et publie le tout comme asset de la GitHub Release `data-v{N}` du repo `castorfou/lmelp-mobile`, où `N` est la version du schéma Room courant de l'app (par exemple `data-v9`) :

```bash
docker exec lmelp-export export-and-publish-release
```

Une boucle embarquée dans l'image (`publish-loop`) déclenche cette commande automatiquement au démarrage du conteneur, puis toutes les `PUBLISH_INTERVAL` secondes (1 h par défaut, `0` la désactive). La release n'est mise à jour que si le contenu exporté a changé.

Si `NTFY_SERVER_URL` / `NTFY_TOPIC` sont configurés (mêmes variables que le back-office), `lmelp-export` envoie une notification ntfy à chaque publication réelle, au premier échec et au retour à la normale, avec des titres préfixés `lmelp-mobile - `.

Le fonctionnement détaillé de la boucle, le délai entre une modification dans Calibre et l'app, et la procédure de diagnostic sont décrits dans [De Calibre à l'app mobile](calibre-vers-app-mobile.md).

### Configuration requise : `GH_TOKEN`

Cette commande utilise `gh release upload` en interne et nécessite un token GitHub :

```bash
# Token GitHub pour la publication automatique de release (optionnel)
GH_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
```

**Scope minimal recommandé** : Personal Access Token *fine-grained*, limité au repo `castorfou/lmelp-mobile`, permission `Contents: Read and write`.

Sans `GH_TOKEN`, le reste du service `lmelp-export` fonctionne normalement — seule la commande `export-and-publish-release` échoue.

#### Créer le token

1. Aller sur [github.com/settings/personal-access-tokens/new](https://github.com/settings/personal-access-tokens/new) (Fine-grained tokens).
2. **Token name** : par exemple `lmelp-export-publish-release`.
3. **Expiration** : au choix (pensez à renouveler avant expiration, sous peine de voir échouer `export-and-publish-release` ; avec `NTFY_TOPIC` configuré, le premier échec est notifié).
4. **Resource owner** : votre compte (`castorfou` ou équivalent).
5. **Repository access** : `Only select repositories` → sélectionner uniquement `lmelp-mobile`.
6. **Permissions** → **Repository permissions** → `Contents` → `Read and write` (laisser le reste à `No access`).
7. **Generate token**, puis copier la valeur (`github_pat_...`) immédiatement — elle n'est affichée qu'une fois.
8. Coller cette valeur dans `GH_TOKEN=` du fichier `.env` (laptop) ou `.env.nas` (NAS), puis redéployer le service `lmelp-export` (`docker compose up -d --force-recreate lmelp-export`) pour que le nouveau token soit pris en compte.

### Checklist de validation en conditions réelles (NAS)

Ces vérifications nécessitent un déploiement réel sur le NAS et ne peuvent pas être automatisées en tests unitaires :

- [ ] Après un redémarrage du NAS ou une recréation du conteneur, confirmer qu'une nouvelle ligne `=== <date> : ok ===` apparaît dans `${LMELP_EXPORT_LOG_PATH}/publish-data-release.log` (par défaut `./data/logs/lmelp-export/publish-data-release.log`) : la boucle exporte dès le démarrage.
- [ ] Vérifier que `${LMELP_EXPORT_STATE_PATH}/last_status` existe sur l'hôte et contient `ok`.
- [ ] Vérifier qu'un asset a bien été publié sur la release `data-v{N}` de `castorfou/lmelp-mobile` après une modification des données (`gh release list --repo castorfou/lmelp-mobile` pour identifier le tag courant, puis `gh release view data-v9 --repo castorfou/lmelp-mobile`).
- [ ] Avec `NTFY_TOPIC` configuré, confirmer la réception d'une notification `lmelp-mobile - nouvelles données publiées (data-v{N})` lors de cette publication.

## Dépannage

### Le service ne démarre pas

**Vérifier les logs**:

```bash
docker compose logs lmelp-export
```

**Erreur courante**: MongoDB non accessible

```
pymongo.errors.ServerSelectionTimeoutError
```

**Solution**: Vérifier que MongoDB est healthy:

```bash
docker compose ps mongo
```

### ADB ne trouve pas le téléphone

**Depuis le container**:

```bash
docker exec lmelp-export adb devices
```

Si vide, vérifier:

1. **ADB server démarré avec `-a`**:

    ```bash
    # Arrêter
    adb kill-server

    # Redémarrer avec flag réseau
    adb -a start-server
    ```

2. **Débogage USB activé** sur le téléphone

3. **Autorisation accordée** sur le téléphone (popup "Autoriser le débogage USB?")

### Le push échoue

**Vérifier les permissions sur le téléphone**:

L'application LMELP Mobile doit avoir les permissions de stockage.

**Vérifier l'espace disque**:

```bash
adb shell df -h
```

### Configuration Calibre non détectée

Si `CALIBRE_HOST_PATH` n'est pas défini ou pointe vers un chemin invalide:

- Le service **fonctionne quand même**
- L'export se fait **sans les données Calibre**
- Volume monté sur `/dev/null` (pas d'erreur)

**Vérifier le montage**:

```bash
docker exec lmelp-export ls -la /calibre
```

Devrait montrer le contenu de votre bibliothèque Calibre, notamment `metadata.db`.

### Erreur "host-gateway not found"

Sur certains systèmes Linux anciens, `host-gateway` n'est pas supporté.

**Solution**: Configurer l'IP de l'hôte manuellement dans `.env`:

```bash
# Trouver l'IP de l'interface docker0
ip addr show docker0

# Configurer dans .env
ADB_HOST=172.17.0.1  # Remplacer par votre IP docker0
```

## Sécurité

### Lecture seule sur Calibre

Le volume Calibre est monté en **lecture seule** (`:ro`):

```yaml
volumes:
  - ${CALIBRE_HOST_PATH}:/calibre:ro
```

Cela garantit que:

- La bibliothèque Calibre ne peut **jamais être modifiée** par le container
- Protection contre les bugs ou erreurs de code
- Cohérence avec le pattern utilisé par le backend

### Exposition ADB

Le daemon ADB du laptop est accessible au container via `host-gateway`. Cela ne pose pas de risque car:

- ADB écoute sur localhost ou réseau privé
- Le container est sur le même réseau bridge Docker (isolé)
- Aucune exposition sur Internet

## Désactivation du service

Pour désactiver temporairement le service sans le supprimer:

```bash
docker compose stop lmelp-export
```

Pour le supprimer complètement du déploiement, commenter ou retirer la section `lmelp-export` dans `docker-compose.yml`.

## Limitations connues

- **Un seul téléphone à la fois**: ADB ne peut pusher que vers un seul appareil connecté
- **Connexion USB requise**: Le transfert WiFi ADB n'est pas supporté (nécessite configuration complexe)
- **Permissions téléphone**: L'utilisateur doit accepter le débogage USB manuellement

## Voir aussi

- [Installation](installation.md) - Configuration initiale de la stack
- [Configuration](configuration.md) - Détails des variables d'environnement
- [Calibre Setup](calibre-setup.md) - Intégration Calibre
- [De Calibre à l'app mobile](calibre-vers-app-mobile.md) - Chaîne complète jusqu'à l'app et diagnostic
- [lmelp-mobile#81](https://github.com/castorfou/lmelp-mobile/issues/81) - Issue originale
