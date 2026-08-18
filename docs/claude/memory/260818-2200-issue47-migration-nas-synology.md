# Migration NAS Synology (issue #47) — guide vivant + corrections découvertes en conditions réelles

## Contexte

L'issue #47 documentait déjà toutes les décisions de migration de `docker-lmelp` d'un
laptop vers un NAS Synology DS923+, mais sans procédure exécutable. Cette session a
produit un guide de migration actionnable, rédigé et corrigé **au fil de l'eau** pendant
que l'utilisateur exécutait réellement la migration sur son NAS — pas un cycle TDD
classique (pas de code applicatif testé unitairement), mais une boucle
rédaction-guide → exécution réelle → diagnostic → correction, répétée plusieurs fois.

À la fin de cette session, **rien n'est encore committé** : tous les changements sont
dans l'arbre de travail sur la branche
`47-déployer-la-stack-docker-lmelp-sur-un-nas-synology-migration-depuis-le-laptop`. Le
commit `8c8645420396a982548211b91c7f01f88e28fd1b` ("rebuild avec todo claude code",
`.devcontainer/`) préexistait déjà sur `main` avant cette session et n'a rien à voir
avec ce travail.

## Fichiers modifiés/créés (non committés)

- `docs/user/migration-nas.md` (nouveau) : guide pas-à-pas complet — arborescence NAS,
  migration Mongo via mongodump/mongorestore, migration audios/cache via zip + File
  Station (le compte NAS de l'utilisateur a un shell `nologin`, donc pas de
  rsync/scp possible), configuration `.env.nas`, déploiement Portainer, reverse proxy
  DSM, checklist de validation, section "Sous-issues liées" avec statuts en temps réel.
- `.env.nas.example` (nouveau, git-tracké) : template pré-rempli avec les chemins NAS
  réels confirmés (`/volume1/docker/lmelp/{mongodb,backups,audios,logs/mongodb,cache/babelio}`
  — **sans** sous-dossier `data/`, contrairement à une première hypothèse). `.env.nas`
  (le vrai fichier avec les secrets de l'utilisateur) a été ajouté à `.gitignore` par
  l'utilisateur lui-même en cours de session — il joue exactement le rôle de `.env` vis
  à vis de `.env.example`.
- `docker-compose.yml` : ajout de `PUID`/`PGID` (défaut 1000) dans les services `lmelp`
  et `backend` — jusque là ces variables n'étaient documentées nulle part alors que les
  images les supportent déjà (voir section PUID/PGID plus bas).
- `.env.example` : nouvelle section `PUID`/`PGID` documentée.
- `docs/user/portainer.md` : section "Déploiement sur NAS Synology" corrigée
  (`DB_HOST=localhost`/mode host supprimé — incohérent avec le réseau bridge réel ;
  référence à la copie de `cron/backup-cron`, supprimé, retirée ; renvoi ajouté vers
  `migration-nas.md`).
- `docs/user/backup-restore.md` : section "Copie automatique vers NAS" adaptée (ne
  référence plus le fichier `cron/backup-cron` supprimé, propose une crontab système
  autonome à la place).
- `cron/backup-cron`, `cron/mongodb-logrotate.anacron` : supprimés (artefacts obsolètes
  d'avant la consolidation anacron interne au conteneur mongo, PR #12/#15).
- `README.md` : arborescence mise à jour (retrait `cron/`, ajout `.env.nas.example` et
  `migration-nas.md`), lien ajouté dans la liste de documentation.

## Décisions/apprentissages non triviaux

### `.env.nas` vs `.env.nas.example`
Suit exactement le pattern `.env`/`.env.example` déjà en place dans le repo :
`.env.nas.example` est le template versionné (secrets vides, chemins NAS pré-remplis) ;
`.env.nas` est le fichier réel de l'utilisateur (vraies clés API, gitignoré). Erreur
évitée en cours de session : ne jamais déplacer/committer `.env.nas` une fois qu'il
contient de vrais secrets (l'utilisateur a explicitement rejeté un `mv` qui aurait
déplacé ce fichier vers `.env.nas.example`).

### Préférence forte : éviter la CLI/SSH sur le NAS
L'utilisateur a un compte NAS avec shell `nologin` — `rsync`/`scp` ne fonctionnent pas.
Toute la procédure privilégie DSM File Station (upload/extraction zip) et la console
Portainer (exec navigateur dans un conteneur) plutôt que SSH. `mongodump`/`mongorestore`
utilisent des exports/imports via fichiers uploadés en GUI, pas de streaming SSH.

### PUID/PGID maintenant réellement câblés
`castorfou/lmelp#105` et `castorfou/back-office-lmelp#258` (fermées, PR
`castorfou/lmelp#106` et `castorfou/back-office-lmelp#260`) ont ajouté un utilisateur
non-root configurable via `PUID`/`PGID` (convention linuxserver.io, défaut 1000,
`gosu` pour dropper les privilèges après un `chown -R` de migration au démarrage) dans
les images `lmelp` et `lmelp-backend`. `docker-compose.yml` de **ce** repo ne les
câblait pas encore — corrigé cette session. Valeur NAS confirmée : `PUID=1027`/`PGID=1027`
(UID réel de `guillaume` sur ce NAS spécifique).

### Trois bugs découverts en conditions réelles sur le NAS, avec sous-issues ouvertes
1. **Port 8080 déjà pris** (service `speedtest` existant sur le NAS) →
   `FRONTEND_PORT` changé à `8081` par défaut dans `.env.nas.example`.
2. **Streamlit (`lmelp`) derrière le reverse proxy DSM reste bloqué sur un écran de
   chargement** : communique en WebSocket (`/_stcore/stream`), non relayé par défaut
   par le reverse proxy Synology → nécessite d'activer le préréglage **WebSocket**
   dans l'onglet "Custom Header" de la règle reverse proxy DSM. Documenté dans
   `docs/user/migration-nas.md` (étape 7).
3. **Intégration Calibre échoue** sur la bibliothèque Calibre-Web-Automated **live**
   du NAS avec `sqlite3.OperationalError: unable to open database file`. Root cause
   précisément identifiée via la stack trace côté `back_office_lmelp/services/calibre_service.py:109` :
   `mode=ro` seul est insuffisant pour une base SQLite en mode journal WAL sur un
   montage Docker `:ro` (SQLite a besoin d'un accès en écriture au fichier `-shm` pour
   le verrouillage, même en lecture). Correctif identifié : ajouter `immutable=1` à
   l'URI de connexion. Fonctionnait sur laptop car la bibliothèque pointée là-bas
   n'était probablement pas activement écrite en WAL au même moment. →
   [castorfou/back-office-lmelp#261](https://github.com/castorfou/back-office-lmelp/issues/261)
   (créée cette session, avec diagnostic complet).
4. **Logs `backup.log`/`logrotate.log` de l'anacron mongo absents sur le NAS**, alors
   que les jobs anacron sont bien déclenchés. Investigation approfondie (voir
   `mongodb.Dockerfile` et `docker-entrypoint-anacron.sh`) : le `chown -R
   mongodb:mongodb /var/log/mongodb` de l'entrypoint fonctionne quand il est relancé
   manuellement en root dans la console, mais ne "tient" pas après un redémarrage
   complet du conteneur — le dossier revient à `ubuntu:ubuntu` (UID 1000). Même
   symptôme d'ownership incohérent reproduit sur le **laptop** (donc pas spécifique au
   NAS), où les fichiers sont au moins créés (juste mal ownés) contrairement au NAS où
   ils sont totalement absents. Root cause non tranchée — nécessite un accès Docker
   réel pour investiguer (indisponible dans ce devcontainer). →
   [castorfou/docker-lmelp#51](https://github.com/castorfou/docker-lmelp/issues/51)
   (créée cette session, avec tout le diagnostic : contenu exact de l'entrypoint,
   `ps aux`, comparaison laptop/NAS).

### Piège `mongosh` : base par défaut
`mongosh --eval "..."` sans argument se connecte à la base `test`, pas à
`masque_et_la_plume` — toujours préciser `mongosh masque_et_la_plume --eval "..."`
pour les vérifications post-restore.

## État des sous-issues liées à la migration (vérifié via `gh issue view --json state`)

Fermées : `castorfou/docker-lmelp#48`, `castorfou/back-office-lmelp#258`,
`castorfou/lmelp#105`.
Ouvertes : `castorfou/back-office-lmelp#259`, `castorfou/lmelp-mobile#116`,
`castorfou/lmelp-mobile#117`, `castorfou/back-office-lmelp#261` (nouvelle),
`castorfou/docker-lmelp#51` (nouvelle).

## Suite

Le guide `docs/user/migration-nas.md` reste un document vivant : la migration physique
sur le NAS n'est pas terminée (l'utilisateur continue à tester étape 8 et au-delà dans
de futures sessions). Prochaine étape immédiate de cette session : commit, vérification
CI, préparation de la PR — sans attendre la fin complète de la migration réelle.
