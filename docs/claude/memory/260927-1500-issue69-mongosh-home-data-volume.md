# Issue #69 — Logs mongosh écrits dans le volume `/data/db` (Hyper Backup en « partial success »)

## Contexte

Depuis le déploiement NAS (issue #47), la tâche Hyper Backup `rsync Docker` du DS923
vers le DS215 finissait en **partial success** à chaque exécution. `/var/log/rsync.error`
sur le NAS montrait des `file has vanished` (rsync code 24) sur
`/volume1/docker/lmelp/mongodb/.mongodb/mongosh/<ObjectId>_log`.

## Root cause

- Le healthcheck du service `mongo` lançait `mongosh` toutes les 10 s
  (horodatages des ObjectId espacés d'environ 11 s, soit un fichier par healthcheck).
- mongosh écrit un log de session par appel dans `$HOME/.mongodb/mongosh/` et purge
  lui-même les plus anciens.
- L'image officielle `mongo` définit `ENV HOME=/data/db`
  ([docker-library/mongo#524](https://github.com/docker-library/mongo/issues/524)) **et**
  donne `/data/db` comme home `passwd` au user `mongodb`. Or `/data/db` est le volume
  `MONGO_DATA_PATH`.
- Les scripts anacron (`scripts/backup_mongodb.sh`, `scripts/rotate_mongodb_logs.sh`)
  recalculent `HOME` via `getent passwd` (correctif #54), donc `/data/db` aussi.

Conséquence : un dossier qui change en permanence dans le volume de données, qui casse
toute sauvegarde au niveau fichiers. Reproduit aussi en local (`data/mongodb/.mongodb`).

## Piège évité pendant la conception

L'issue proposait, en option, de forcer `HOME=/tmp` à la fois dans le healthcheck et dans
les scripts. Mauvaise idée : le healthcheck tourne en **root** et créerait
`/tmp/.mongodb/mongosh` avant les scripts, qui tournent en **mongodb** après
`gosu`. Ces derniers retomberaient alors sur l'`EACCES` de l'issue #54.
**Règle : root et mongodb ne doivent pas partager le même HOME.**

## Correctif (3 couches indépendantes)

1. `docker-compose.yml` : healthcheck `mongo` en `CMD-SHELL`
   `HOME=/tmp mongosh --quiet --eval 'db.adminCommand("ping")' || exit 1`
   (timings inchangés : 10s/5s/5/20s). Utilisé seulement par root.
2. `mongodb.Dockerfile` : `/etc/mongosh.conf` (config globale mongosh) avec
   `mongosh:\n  disableLogging: true`, en 644. Coupe les logs de session pour tous les
   appelants : healthcheck, scripts, init de l'entrypoint, consoles Portainer.
3. `mongodb.Dockerfile` : `usermod -d /home/mongodb mongodb` (dossier créé et chowné
   `mongodb:mongodb` dans l'image). La ligne `getent` des scripts (#54) résout alors hors
   du volume **sans modifier les scripts**. `mongod` n'est pas impacté (il garde
   `ENV HOME=/data/db` et n'utilise pas HOME).

Le dossier `.mongodb` déjà présent dans le volume n'est **pas** supprimé
automatiquement : c'est une étape manuelle, documentée dans `docs/user/migration-nas.md`.

## Tests

- `tests/test_docker_compose.py::TestMongoHealthcheckHome` (statique) : `CMD-SHELL`,
  `HOME=/tmp mongosh`, pas de `/data/db`, ping + `|| exit 1`, timings.
- `tests/test_mongodb_image.py::TestMongoshHomeOutsideDataVolume` (statique sur le
  Dockerfile).
- `tests/test_mongodb_image.py::TestMongoDBImageContent` (image buildée) :
  - `/etc/mongosh.conf` lisible par `mongodb` avec `disableLogging: true` ;
  - home `passwd` = `/home/mongodb`, owned by 999 ;
  - end-to-end `test_mongosh_calls_leave_data_volume_untouched` : exécute la commande
    du healthcheck **lue depuis `docker-compose.yml`** plusieurs fois, puis
    `rotate_mongodb_logs.sh` en root. Vérifie que `/data/db/.mongodb` est absent et
    qu'aucun `EACCES` n'apparaît.

## Environnement de développement

Le daemon Docker n'était pas joignable depuis le devcontainer (socket monté,
docker-outside-of-docker, mais aucun daemon derrière). Les tests d'image ont été validés
**par la CI GitHub** (runners avec Docker, `pytest tests/` complet), sur décision de
l'utilisateur. L'image `ghcr.io/castorfou/lmelp-mongo:latest` n'est publiée que depuis
`main` (`.github/workflows/build-mongo-image.yml`), donc la validation NAS se fait
après le merge.

## Leçon générale

Dans une image dérivée de `mongo`, **tout outil qui écrit dans `$HOME`** (mongosh, et
potentiellement d'autres CLIs) écrit dans le volume de données, par défaut pour root comme
pour `mongodb`. À vérifier pour tout nouvel appel d'outil (healthcheck, script, sidecar).
