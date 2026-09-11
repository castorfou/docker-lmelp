# Migration vers un NAS Synology

Ce guide décrit la migration d'une stack `docker-lmelp` fonctionnant en local sur un
laptop (chemins relatifs `./data/...`) vers un NAS Synology, en conservant les données
existantes (MongoDB, audios, backups, cache Babelio).

!!! info "Déploiement neuf, sans données à migrer ?"
    Ce guide couvre une **migration** (données existantes à transférer). Pour un
    déploiement neuf sur Synology, voir la section "Déploiement sur NAS Synology" de
    [Déploiement Portainer](portainer.md).

## Prérequis

- **Container Manager** installé depuis le Package Center Synology (fournit le moteur
  Docker) et **Portainer** déployé dedans (voir [Déploiement Portainer](portainer.md)).
- **SSH activé** sur le NAS : Panneau de configuration → Terminal & SNMP.
- **Compatibilité des images** : les images `ghcr.io/castorfou/*` utilisées par cette
  stack sont publiées en `amd64` uniquement — vérifier que le NAS est bien un modèle
  x86_64 (`docker manifest inspect <image>` pour confirmer une image donnée).
- **Espace disque** : prévoir l'équivalent du volume actuel de `data/` sur le laptop
  (`du -sh data/*` pour le mesurer — typiquement quelques Go, essentiellement les
  fichiers audio).

## Étape 1 — Préparer l'arborescence sur le NAS

```bash
en tant qu'utilisateur simple (pour moi guillaume uid 1027)

créer depuis DSM (le chemin `/volume1` n'apparait pas) l'arborescence suivante:

- `/docker/lmelp`
- `/docker/{mongodb,backups,audios,logs/lmelp-export,mongodb-logs,cache/babelio,pgx-keys-backend}`
```

!!! info "`pgx-keys-backend` (optionnel, transcription PGX)"
    Répertoire destiné à la clé SSH dédiée à la transcription automatisée via PGX,
    pilotée depuis le back-office (page `/transcription-pgx`, générée et persistée
    automatiquement au premier démarrage du conteneur `backend`, voir
    [Variables PGX](configuration.md#variables-pgx-transcription-automatisee)). À créer
    même si la fonctionnalité n'est pas utilisée immédiatement : sans ce volume, une
    nouvelle clé serait régénérée à chaque recréation du conteneur, invalidant toute
    autorisation SSH déjà déployée côté PGX. Le répertoire `pgx-keys` (historique, clé
    dédiée à `lmelp`) reste optionnel — la transcription ne passe plus par ce service.

!!! warning "`PGX_HOST` : un nom `.local` qui marche sur laptop peut échouer sur NAS (issue #60)"
    Cas vécu : `PGX_HOST=thinkstationpgx-d7ba.local` fonctionnait depuis le laptop mais
    échouait depuis le conteneur `backend` sur le NAS (*"Machine joignable —
    thinkstationpgx-d7ba.local ne répond pas sur le port 22"*), alors qu'un
    `ping` du même nom depuis le laptop répondait normalement. Cause : le conteneur résout
    ce nom via le DNS système hérité de sa machine hôte — le routeur LAN côté laptop
    connaît les baux DHCP locaux et peut résoudre les noms `.local`, alors que le DNS
    configuré dans DSM sur le NAS ne les connaît généralement pas. Voir
    [Variables PGX](configuration.md#variables-pgx-transcription-automatisee) : toujours
    utiliser l'IP directe de PGX pour `PGX_HOST`, jamais un nom `.local` ou un nom court.

!!! warning "`mongodb-logs` ne doit pas être un sous-dossier de `logs` (issue #51)"
    Le conteneur `lmelp` chowne récursivement son propre volume `LOG_PATH` à chaque
    démarrage (utilisateur non-root configurable) — si `mongodb-logs` était imbriqué
    dedans, ça écraserait l'ownership `mongodb` des logs Mongo et casserait les jobs
    anacron (backup/rotation). D'où deux dossiers frères distincts, pas un parent/enfant.

## Étape 2 — Arrêter la stack sur le laptop

Pour migrer un état cohérent des données, arrêter la stack avant le transfert :

Depuis portainer laptop, aller sur la stack lmelp-stack, selectionner tous les containers et cliquer sur Stop

![alt text](image.png)


## Étape 3 — Migrer MongoDB (mongodump / mongorestore)

!!! warning "Ne pas `rsync` le dossier `data/mongodb` brut"
    Les fichiers internes de MongoDB (WiredTiger) ne sont pas destinés à être copiés
    tels quels entre deux installations — utiliser `mongodump`/`mongorestore` évite
    tout problème de compatibilité ou de propriétaire de fichiers.

```bash
# Sur le laptop : redémarrer uniquement mongo le temps du dump

# depuis portainer start le container lmelp-mongo

docker exec lmelp-mongo mongodump --db=masque_et_la_plume --out=/backups/migration_nas
sudo chown -R guillaume:guillaume /home/guillaume/git/docker-lmelp/data/backups/migration_nas
# depuis portainer stop le container lmelp-mongo

# Transférer le dump vers le NAS

# depuis DSM, aller dans /docker/lmelp/backups
# creer le repertoire migration_nas/masque_et_la_plume
# upload (Upload - Overwrite) le contenu de /home/guillaume/git/docker-lmelp/data/backups/migration_nas/masque_et_la_plume vers /docker/lmelp/backups/migration_nas/masque_et_la_plume
```

## Étape 4 — Migrer le reste des données (audios, cache)

On passe par une archive zip et
l'interface DSM (File Station) :

```bash
# Depuis le laptop, stack arrêtée
cd /home/guillaume/git/docker-lmelp/data
zip -r audios_cache.zip audios cache
```

Puis, depuis DSM :

1. **File Station** → `/docker/lmelp` → **Upload** → `audios_cache.zip` (10 Go en aout 2026)
2. Clic droit sur `audios_cache.zip` → **Extraire vers...** → `/docker/lmelp` (avec
   écrasement si des fichiers existent déjà)
3. Vérifier l'arborescence obtenue : `/docker/lmelp/audios` et
   `/docker/lmelp/cache/babelio`
4. Supprimer `audios_cache.zip` une fois le contenu vérifié du Nas et du laptop

## Étape 5 — Configurer `.env.nas` pour le NAS

Le repository fournit un template pré-rempli avec les chemins NAS :

```bash
# Sur le laptop, dans le clone du repository
cd /home/guillaume/git/docker-lmelp
cp .env.nas.example .env.nas
nano .env.nas  # compléter les clés API (à recopier depuis le .env du laptop)
```

`.env.nas` est gitignoré au même titre que `.env` (il contient vos vraies clés API) —
seul `.env.nas.example` est versionné.

Points d'attention :

- **Chemins absolus obligatoires** pour Portainer (voir la note dans `CLAUDE.md` sur la
  résolution des chemins relatifs par Portainer) — déjà le cas dans `.env.nas.example`.
- `CALIBRE_HOST_PATH` pointe vers la bibliothèque Calibre-Web-Automated déjà présente
  sur ce NAS (`/volume1/docker/calibre-web-automated/books`), montée en lecture seule.
- `PUID`/`PGID` : câblés dans `docker-compose.yml` pour les services `lmelp` et
  `backend` (utilisateur non-root configurable, castorfou/lmelp#105 et
  castorfou/back-office-lmelp#258). Valeur `1027` déjà renseignée dans
  `.env.nas.example` (UID réel de `guillaume` sur ce NAS) — les fichiers audios/cache
  déjà `root:root` d'un précédent déploiement sont repris automatiquement au prochain
  redémarrage du conteneur, sans manipulation manuelle.

## Étape 6 — Déployer via Portainer

Suivre [Déploiement Portainer](portainer.md), en chargeant le `.env.nas` préparé à l'étape
précédente.


### Créer une nouvelle stack lmelp sur le NAS

1. Se connecter à Portainer
2. Aller dans **Stacks** dans le menu latéral
3. Cliquer sur **+ Add stack**

### Configurer la stack

[![](portainer-stack-small.png)](portainer-stack.png)
(cliquer pour zoomer)

**Name** : `lmelp-stack`

**Build method** : Sélectionner **Repository**

**Git Repository** :

```
Authentication: Ne Pas cocher
Repository URL: https://github.com/castorfou/docker-lmelp
Repository reference: refs/heads/main
Compose path: docker-compose.yml
```

**GitOps updates** : Cocher pour detecter les mises a jour de `docker-compose.yml`


**Environment Variables** : Cliquer sur Load variables from .env file et Selectionner le fichier `.env.nas`

### Déployer

1. Vérifier la configuration
2. Cliquer sur **Deploy the stack**

Une fois la stack démarrée, faire un `mongorestore`.



```bash
# Sur le NAS, depuis portainer entrer dans le container lmelp-mongo

mongorestore --db=masque_et_la_plume --drop /backups/migration_nas/masque_et_la_plume
```

### Tester chaque container

![alt text](image-1.png)

En naviguant sur chaque container :

- lmelp : http://nas923:8501/
- backoffice-lmelp : http://nas923:8081/

## Étape 7 — Autoriser la clé SSH PGX

Pour utiliser la transcription automatisée via PGX (voir
[Variables PGX](configuration.md#variables-pgx-transcription-automatisee)), le conteneur
`backend` génère automatiquement une clé SSH dédiée à son premier démarrage — cette clé
n'est cependant pas encore autorisée à se connecter sur PGX.

1. Ouvrir la page `/transcription-pgx` du back-office : elle affiche la clé publique
   générée (contenu de `pgx_ed25519.pub`) ainsi que la commande exacte à exécuter sur PGX
   pour l'autoriser (checklist de diagnostic, back-office-lmelp#302).
2. Sur PGX, ajouter cette clé publique au `authorized_keys` du compte `PGX_USER` :
   ```bash
   echo '<contenu de la clé publique affichée par /transcription-pgx>' >> ~/.ssh/authorized_keys
   ```
3. Rafraîchir la page `/transcription-pgx` (ou relancer les vérifications) : l'étape
   **Authentification SSH (clé dédiée)** doit passer au vert.

## Étape 8 — Reverse proxy DSM (accès intranet)

Pour un accès via un nom d'hôte sur le réseau local, configurer le reverse proxy natif
DSM : **Portail de connexion** → **Avancé** → **Proxy inversé**.

**lmelp**

- Reverse Proxy Name: lmelp
- Source
    - Protocol: HTTPS
    - Hostname: lmelp.ascot63.synology.me
    - Port: 443
    - Enable HSTS
    - Access control profile: reseau local
- Destination
    - Protocol: HTTP
    - Hostname: localhost
    - Port: 8501

!!! warning "Streamlit nécessite le support WebSocket"
    `lmelp` (Streamlit) communique via WebSocket (`/_stcore/stream`) pour rafraîchir la
    page — sans relai de ces en-têtes, l'application reste bloquée sur un écran de
    chargement vide derrière le reverse proxy (alors qu'un accès direct sur `:8501`
    fonctionne). Éditer la règle **lmelp** → onglet **Custom Header** → **Create** →
    préréglage **WebSocket** (ajoute `Upgrade: $http_upgrade` et
    `Connection: $connection_upgrade`). Pas nécessaire sur `lmelp-bo` (application HTTP
    classique).
    ![alt text](image-2.png)

**backoffice-lmelp**

- Reverse Proxy Name: lmelp-bo
- Source
    - Protocol: HTTPS
    - Hostname: lmelp-bo.ascot63.synology.me
    - Port: 443
    - Enable HSTS
    - Access control profile: reseau local
- Destination
    - Protocol: HTTP
    - Hostname: localhost
    - Port: 8081


## Étape 9 — Valider le déploiement

- [:white_check_mark:] Tous les containers sont `healthy` (`docker compose ps` ou Portainer)
- [:white_check_mark:] L'application LMELP est accessible et affiche les données migrées
- [:white_check_mark:] `docker exec lmelp-mongo mongosh masque_et_la_plume --eval "db.emissions.countDocuments()"` renvoie un nombre cohérent avec l'ancienne installation (fais en root depuis le container lmelp-mongo : `mongosh masque_et_la_plume --eval "db.emissions.countDocuments()"`)
- [:white_check_mark:] Un backup manuel fonctionne (`FORCE_BACKUP=1 /scripts/backup_mongodb.sh`, voir [Backups & Restauration](backup-restore.md))
- [:white_check_mark:] La bibliothèque Calibre est visible depuis le back-office (lecture seule)
- [:white_check_mark:] Le cache Babelio existant est bien pris en compte (pas de re-scraping à froid) :
      1. Vérifier via **File Station** que `/docker/lmelp/cache/babelio` contient bien
         des fichiers `.json` (non vide, cohérent avec ce qui a été zippé/uploadé à
         l'étape 4)
      2. Consulter dans le back-office une fiche livre/auteur déjà vue avant la
         migration : la réponse doit être quasi instantanée (un vrai scraping Babelio
         est ralenti par `BABELIO_FAIR_SEC`, ~2s)
- [:x:] (si utilisé) L'export Android fonctionne depuis le NAS — cf. limitations ci-dessous
- [:white_check_mark:] (si utilisé) La transcription PGX fonctionne : page
  `/transcription-pgx` du back-office, toutes les étapes de diagnostic au vert (clé SSH
  autorisée à l'étape 7, `PGX_HOST` configuré en IP directe — voir
  [Variables PGX](configuration.md#variables-pgx-transcription-automatisee))

## Étape 10 — Automatiser la synchronisation RSS via Automatisch

Le backend expose `POST /api/rss/sync`, qui synchronise le flux RSS "Le Masque et la
Plume" et télécharge le fichier audio de chaque nouvel épisode "livres" détecté. Cette
étape ajoute une action "HTTP Request" dans un workflow Automatisch (hébergé sur le même
NAS) pour déclencher cette synchronisation automatiquement, sans intervention manuelle.

Dans le workflow Automatisch concerné, ajouter une nouvelle étape :

| Champ           | Valeur                                                                                                                                                                                                                |
| --------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| App             | `HTTP Request`                                                                                                                                                                                                        |
| Event           | `Custom request`                                                                                                                                                                                                      |
| Method          | `POST`                                                                                                                                                                                                                |
| URL             | `http://192.168.50.207:8000/api/rss/sync`                                                                                                                                                                             |
| Headers         | `Content-Type: application/json`                                                                                                                                                                                      |
| Data (raw JSON) | `{"trigger": "api"}` (optionnel — `"api"` est déjà la valeur par défaut côté serveur si le champ est omis, mais l'expliciter clarifie l'origine du déclenchement dans l'historique consultable sur `/rss-monitoring`) |

### Réponse attendue

```json
{
  "started_at": "...",
  "finished_at": "...",
  "trigger": "api",
  "status": "success",
  "feed_url": "...",
  "episodes": [...],
  "notification_sent": false,
  "error_message": null
}
```

Un `status: "success"` avec `episodes: []` est normal si aucun nouvel épisode n'est
disponible depuis le dernier connu en base (déduplication automatique). Chaque épisode
traité indique un `outcome` : `downloaded`, `skipped_not_book`, `already_exists`,
`skipped_too_short` ou `error`.

Cette étape Automatisch peut se substituer ou compléter le clic manuel sur "🔄 Rafraîchir
Episodes" de la page `/rss-monitoring` de back-office-lmelp — l'historique des
synchronisations, qu'elles soient déclenchées manuellement ou via Automatisch, reste
consultable sur cette même page.

## Étape 11 — Automatiser la transcription PGX via Automatisch

### Section Overview

Sur le modèle de l'étape 10 (synchronisation RSS), la transcription PGX peut
être déclenchée automatiquement par Automatisch via l'endpoint
`POST /api/pgx/transcription/start`. Contrairement à `/api/rss/sync`
(synchrone, faible volume), cet endpoint est **fire-and-forget** :
Automatisch appelle l'endpoint **une seule fois** (à sa fréquence propre,
par exemple une fois par jour), et le backend prend en charge tout le reste
— y compris un **retry automatique toutes les heures pendant 24h** si PGX
est éteinte au moment de l'appel. Pas besoin de programmer un cron répété
côté Automatisch.

### Configuration Details

**Ajout d'une étape dans le workflow Automatisch :**

| Champ           | Valeur                                                   |
| --------------- | -------------------------------------------------------- |
| App             | `HTTP Request`                                           |
| Event           | `Custom request`                                         |
| Method          | `POST`                                                   |
| URL             | `http://192.168.50.207:8000/api/pgx/transcription/start` |
| Headers         | `Content-Type: application/json`                         |
| Data (raw JSON) | `{"trigger": "api"}`                                     |

**Important** : ne pas omettre `"trigger": "api"` — sans ce paramètre (ou
avec `"trigger": "manual"`), le comportement reste celui du bouton UI :
échec immédiat et définitif si PGX est injoignable, sans retry.

### Expected Response

Réponse immédiate (l'endpoint ne bloque jamais jusqu'à la fin du
traitement, qui peut durer plusieurs minutes à plusieurs heures selon le
nombre d'épisodes et la disponibilité de PGX) :

```json
{"status": "started", "episode_count": 2}
```

Autres réponses possibles :

```json
{"status": "nothing_to_do"}
```
Aucun épisode en attente de transcription — normal si tout est déjà à jour.

```json
{"status": "already_running"}
```
Un cycle est déjà en cours (traitement actif, ou retry en attente d'une
prochaine tentative horaire) — évite les doublons si Automatisch se
redéclenche pendant qu'un cycle précédent tourne encore.

### Suivre le résultat

Le déclenchement étant asynchrone, consultez l'historique pour connaître
l'issue réelle du cycle :

```bash
curl http://192.168.50.207:8000/api/pgx/logs | jq
```

Chaque document représente un cycle complet (du déclenchement au succès ou
à l'abandon) :

```json
{
  "_id": "...",
  "started_at": "...",
  "finished_at": "...",
  "trigger": "api",
  "status": "success",
  "episode_ids": ["..."],
  "episodes": [
    {"episode_id": "...", "titre": "...", "success": true, "error": null}
  ],
  "retry_attempts": [],
  "notification_sent": true,
  "error_message": null
}
```

`status` peut valoir :

- `success` — tous les épisodes traités avec succès.
- `partial_error` — au moins un épisode a échoué, cycle terminé quand même.
- `error` — erreur inattendue ayant interrompu tout le pipeline.
- `pgx_unreachable_abandoned` — PGX est restée injoignable au-delà du
  délai maximal de retry (24h par défaut) ; `episodes` est vide dans ce
  cas, mais `episode_ids` conserve la liste des épisodes qui attendaient
  d'être traités, et `retry_attempts` détaille chaque tentative horaire.

L'historique complet (y compris les cycles déclenchés manuellement depuis
`/transcription-pgx`) est aussi consultable dans le back-office, section
"📋 Historique des transcriptions" de cette page.

### Notifications ntfy.sh

Si `NTFY_SERVER_URL`/`NTFY_TOPIC` sont configurés (mêmes variables que pour
RSS), deux notifications sont envoyées automatiquement, sans action
supplémentaire côté Automatisch :

- **Dès le premier échec de joignabilité** déclenchant le retry — pour
  savoir qu'il faut allumer PGX, sans attendre 24h en silence.
- **En fin de cycle** — succès, erreur partielle/totale, ou abandon
  définitif après épuisement du délai de retry.

Aucune notification n'est envoyée à chaque tentative de retry individuelle
(pas de bruit répété toutes les heures).

### Key Notes

- Cette étape Automatisch peut remplacer ou compléter le bouton
  "▶️ Lancer la transcription" du back-office `/transcription-pgx`.
- Le retry (jusqu'à 24 fois par défaut, à raison d'une tentative par
  heure) est entièrement géré côté backend — Automatisch n'a pas besoin de
  relancer l'appel tant que le cycle précédent n'est pas terminé.
- Les délais de retry sont configurables via `PGX_TRANSCRIPTION_RETRY_INTERVAL_HOURS`
  (défaut `1`) et `PGX_TRANSCRIPTION_RETRY_MAX_HOURS` (défaut `24`).
- Un appel Automatisch pendant qu'un cycle est déjà en cours (traitement
  actif ou retry en attente) renvoie simplement `{"status":
  "already_running"}` — sans effet indésirable, sans doublon.

## Limitations connues

- **Export Android (ADB)** : `lmelp-export` se connecte à un serveur ADB en TCP — cela
  nécessite qu'un serveur ADB tourne quelque part joignable par le conteneur (NAS via
  SSH + `platform-tools`, ou conteneur ADB dédié). Le débogage sans fil Android peut être
  instable dans la durée ; réserver une IP DHCP fixe au téléphone est recommandé.
  À valider en conditions réelles sur le NAS. On a documenté cela dans [castorfou/lmelp-mobile#116 - Repenser la séparation mise à jour appli / mise à jour données pour l'export mobile](https://github.com/castorfou/lmelp-mobile/issues/116)
- **Pipeline de transcription PGX** : la transcription automatisée ne dépend plus d'un
  chemin local au laptop — elle passe désormais par SSH depuis le conteneur `backend`
  lui-même, pilotée depuis la page `/transcription-pgx` du back-office (voir
  [Variables PGX](configuration.md#variables-pgx-transcription-automatisee)), ce qui
  fonctionne aussi bien depuis le NAS. Reste à valider en conditions réelles une fois le
  `backend` déployé sur le NAS (station PGX joignable sur le même réseau local que le
  NAS, clé SSH dédiée à autoriser côté PGX).
- **Contournement réseau Babelio non transférable au NAS** : c'est le conteneur
  `backend` (pas le navigateur) qui interroge Babelio pour enrichir les métadonnées.
  Quand Babelio bloque/rate-limite ou exige une IP spécifique, la solution actuelle est
  de changer de réseau/VPN **au niveau OS du laptop** — un contournement propre à cette
  machine précise, qui ne s'applique plus une fois le `backend` déplacé sur le NAS. Pas
  de solution équivalente côté NAS pour l'instant (suivi dans
  [castorfou/back-office-lmelp#259 - Support d'un proxy HTTP sortant pour les requêtes vers Babelio](https://github.com/castorfou/back-office-lmelp/issues/259)).
- **Logs backup/logrotate mongo (anacron) absents ou mal ownés** : `/var/log/mongodb/backup.log`
  et `logrotate.log` n'apparaissent pas sur le NAS malgré des jobs anacron bien
  déclenchés (`chown -R mongodb:mongodb` manuel dans la console du conteneur débloque
  la situation en attendant). Même symptôme d'ownership incohérent (`ubuntu` au lieu de
  `mongodb`) reproduit sur le laptop — donc pas spécifique à la migration NAS. Root
  cause non tranchée (nécessite un accès Docker direct pour investiguer) : suivi dans
  [castorfou/docker-lmelp#51 - Logs backup/logrotate mongo (anacron) : ownership incohérent (ubuntu au lieu de mongodb), absents sur NAS](https://github.com/castorfou/docker-lmelp/issues/51).

## Sous-issues liées

| Sous-issue                                                                                   | Sujet                                                                   | Statut    |
| -------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------- | --------- |
| [castorfou/docker-lmelp#48](https://github.com/castorfou/docker-lmelp/issues/48)             | Anacron mongo écrit les backups/logs en root                            | ✅ Fermée  |
| [castorfou/back-office-lmelp#258](https://github.com/castorfou/back-office-lmelp/issues/258) | Conteneur backend tourne en root (cache Babelio)                        | ✅ Fermée  |
| [castorfou/back-office-lmelp#259](https://github.com/castorfou/back-office-lmelp/issues/259) | Support proxy HTTP sortant pour Babelio                                 | 🔵 Ouverte |
| [castorfou/lmelp#105](https://github.com/castorfou/lmelp/issues/105)                         | Conteneur lmeSlp tourne en root (audios/transcriptions)                 | ✅ Fermée  |
| [castorfou/lmelp-mobile#116](https://github.com/castorfou/lmelp-mobile/issues/116)           | Repenser séparation appli/données + ADB NAS                             | 🔵 Ouverte |
| [castorfou/lmelp-mobile#117](https://github.com/castorfou/lmelp-mobile/issues/117)           | Adapter le pipeline Whisper/PGX au NAS                                  | 🔵 Ouverte |
| [castorfou/back-office-lmelp#261](https://github.com/castorfou/back-office-lmelp/issues/261) | Intégration Calibre échoue en lecture seule sur bibliothèque WAL active | ✅ Fermée  |
| [castorfou/docker-lmelp#51](https://github.com/castorfou/docker-lmelp/issues/51)             | Logs backup/logrotate mongo (anacron) : ownership incohérent            | 🔵 Ouverte |


## Historique

Ce guide fait suite à l'investigation menée dans
[l'issue #47](https://github.com/castorfou/docker-lmelp/issues/47), qui documente les
décisions prises point par point.
