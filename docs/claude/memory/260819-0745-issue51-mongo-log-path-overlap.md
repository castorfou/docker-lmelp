# Issue #51 — Conflit de chemins LOG_PATH/MONGO_LOG_PATH cassant les logs anacron mongo

## Contexte

Suite (et conclusion) de l'investigation ouverte pendant la migration NAS (issue #47) :
`/var/log/mongodb/backup.log` et `logrotate.log` n'apparaissaient jamais sur le NAS
malgré des jobs anacron bien déclenchés, et étaient mal ownés (`ubuntu` puis `1027` au
lieu de `mongodb`/999) même sur le laptop de référence.

## Root cause (trouvée par l'utilisateur, pas par l'agent)

L'agent avait initialement conclu à tort à un mystère de remapping UID côté Container
Manager/Synology. **L'utilisateur a corrigé cette hypothèse** en remarquant qu'il
déploie toujours depuis `main` via Portainer, et que le seul changement entre les deux
observations était le merge de la PR #47 (câblage `PUID`/`PGID` pour `lmelp`/`backend`).

Vérification confirmée dans le vrai code de `castorfou/lmelp`
(`docker/build/entrypoint.sh`, PR #106) :
```bash
chown -R "$PUID:$PGID" /app/audios /app/db /app/logs
```
Ce chown est **récursif et inconditionnel à chaque démarrage** (migration transparente
des fichiers `root:root` hérités). Or `docker-compose.yml` de **ce** repo montait
`MONGO_LOG_PATH` en sous-dossier de `LOG_PATH` par défaut (`./data/logs/mongodb` sous
`./data/logs`) — le chown de `lmelp` sur son propre volume `/app/logs` réécrivait donc
récursivement l'ownership des logs mongo à chaque démarrage de `lmelp`, écrasant le
`mongodb:mongodb` que l'entrypoint mongo venait de poser.

`BACKUP_PATH` est aussi partagé entre `mongo` (`/backups`) et `lmelp`
(`/app/db-backup`), mais sans collision réelle : l'entrypoint `lmelp` ne chowne que
`/app/audios /app/db /app/logs`, pas `/app/db-backup`.

## Correctif (`docker-compose.yml`, `.env.example`, `.env.nas.example`, `mongodb.Dockerfile`)

1. **`MONGO_LOG_PATH`** déplacé sur un chemin frère non imbriqué : `./data/mongodb-logs`
   (au lieu de `./data/logs/mongodb`). **Cassant** pour les déploiements existants —
   nécessite de renommer le dossier et mettre à jour `.env`/`.env.nas` réels avant
   redéploiement.
2. **Watchdog d'ownership dédié** dans l'entrypoint mongo, indépendant de la boucle
   anacron : réapplique `chown -R mongodb:mongodb /backups /var/log/mongodb` toutes les
   `CHOWN_WATCHDOG_INTERVAL` secondes (défaut 300s). Auto-répare toute dérive future,
   quelle qu'en soit la cause — pas seulement celle identifiée ici.

### Détail TDD notable : pourquoi une boucle dédiée plutôt que dans la boucle anacron

Première itération : le chown défensif avait été ajouté *dans* la boucle
`(while true; do gosu mongodb anacron -d; sleep "$ANACRON_LOOP_INTERVAL"; done)`. Le
test comportemental Docker associé a échoué **en CI** (pas testable en local, pas de
Docker dans ce devcontainer) : `anacron -d` **bloque plusieurs minutes** en interne, le
temps d'attendre le délai configuré de chaque job dans `/etc/anacrontab` (`1 5` et
`1 10` = 5 et 10 minutes) avant de l'exécuter réellement. Le chown ne repassait donc
jamais dans une fenêtre de test de 15s. Correction : boucle de chown totalement séparée
de la boucle anacron, avec son propre intervalle configurable
(`CHOWN_WATCHDOG_INTERVAL`). Leçon générale : un correctif "réappliquer X avant Y" ne
suffit pas si Y peut bloquer arbitrairement longtemps — il faut découpler.

## Correctif collatéral : `pyproject.toml` ruff `extend-select` → `select`

Bloquait le premier commit localement (`pre-commit run` échouait avec 27 erreurs
`PLW1510` sur des `subprocess.run` **préexistants**, pas seulement les nouveaux).
Diagnostic : `.pre-commit-config.yaml` épingle `ruff 0.16.3`, le `ruff` local de ce
devcontainer est en `0.14.5` — `extend-select` hérite silencieusement du jeu de règles
par défaut de la version épinglée, bien plus large (59→413 règles dans un cas similaire).
**Même correctif déjà appliqué dans `castorfou/back-office-lmelp#260`** — signe que ce
problème de dérive de version ruff via pre-commit est récurrent dans l'écosystème de
repos de l'utilisateur ; à surveiller sur les autres repos (`lmelp`, `lmelp-mobile`) qui
utilisent probablement le même pattern `extend-select`.

## Contrainte de session : pas d'accès Docker dans ce devcontainer

Confirmé plusieurs fois (`pytest tests/test_mongodb_image.py` échoue avec "Cannot
connect to the Docker daemon"). Tous les tests comportementaux Docker de ce repo ont dû
être validés via la CI GitHub Actions (push + `gh run watch`) plutôt qu'en itération
locale RED/GREEN classique — donc plus lent (push nécessaire à chaque itération), mais
fonctionnel. Pattern réutilisable pour tout futur travail sur `mongodb.Dockerfile` ou
`tests/test_mongodb_image.py` dans ce devcontainer.

## Fichiers modifiés

`docker-compose.yml`, `.env.example`, `.env.nas.example`, `mongodb.Dockerfile`,
`tests/test_mongodb_image.py`, `pyproject.toml`, `README.md`, `CLAUDE.md`,
`docs/user/configuration.md`, `docs/user/mongodb-log-rotation.md`,
`docs/user/portainer.md`, `docs/user/migration-nas.md`,
`docs/dev/mongodb-custom-image.md`.

PR : castorfou/docker-lmelp#53 (branche
`51-logs-backuplogrotate-mongo-anacron-ownership-incohérent-ubuntu-au-lieu-de-mongodb-absents-sur-nas`).
Validation en conditions réelles (laptop + NAS) prévue par l'utilisateur après merge,
au prochain redéploiement habituel depuis `main`.
