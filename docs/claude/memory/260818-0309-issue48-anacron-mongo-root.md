# Fix issue #48 — anacron mongo écrivait les backups/logs en root

## Contexte

Découvert pendant l'investigation de la migration NAS Synology (issue #47) : sur le laptop,
`find data ! -user guillaume` remontait `data/backups/backup_*/masque_et_la_plume/*.bson` et
`data/logs/mongodb/{backup,logrotate}.log` appartenant à **root**, alors que le reste des
fichiers gérés par mongod est en UID 999 (`mongodb`). Confirmé sur deux runs de backup réels
distincts avant le fix.

## Cause racine

Dans `mongodb.Dockerfile`, l'entrypoint custom `/docker-entrypoint-anacron.sh` lançait la
boucle anacron en arrière-plan **avant** d'`exec`er l'entrypoint officiel Mongo :

```bash
(while true; do anacron -d; sleep 3600; done) &
exec /usr/local/bin/docker-entrypoint.sh "$@"
```

C'est l'entrypoint officiel qui droppe les privilèges vers `mongodb` (via `gosu`), pas le
script custom. La boucle anacron restait donc dans le contexte root du process d'init du
conteneur, et tous les jobs qu'elle déclenche (`backup_mongodb.sh` → `/backups`,
`rotate_mongodb_logs.sh` → `/var/log/mongodb`) écrivaient en root.

## Deux pièges supplémentaires trouvés en creusant (au-delà du simple `gosu mongodb anacron -d`)

1. **`/var/spool/anacron`** (bookkeeping interne d'anacron, créé par `apt-get install anacron`,
   appartient à root par défaut) doit être accessible en écriture par `mongodb`, sinon anacron
   ne peut plus mettre à jour ses timestamps de dernière exécution une fois invoqué en non-root.

2. **`/backups` est un bind-mount dont le propriétaire du dossier de premier niveau dépend de
   l'hôte**, pas de l'image. Preuve réelle sur le laptop : `/backups` lui-même appartenait à
   `1000:1000` (mode 755) — seul le propriétaire pouvait y créer des sous-dossiers. root
   contournait ça (root ignore les permissions Unix), mais `mongodb` (UID 999, ni propriétaire
   ni root) ne le pourrait pas sans chown préalable. Leçon générale : **quand un process dans
   un conteneur doit écrire dans un volume bind-mounté après un drop de privilège, il faut
   chowner le point de montage explicitement au démarrage (pendant qu'on est encore root) —
   ne jamais supposer que l'ownership baked dans l'image au build survit au runtime, un
   bind-mount écrase toujours ce qui est dans l'image.**

## Fix appliqué

Dans `mongodb.Dockerfile`, le bloc générant `/docker-entrypoint-anacron.sh` fait maintenant,
avant de lancer la boucle anacron :

```bash
mkdir -p /backups /var/log/mongodb /var/spool/anacron
chown -R mongodb:mongodb /backups /var/log/mongodb
chown mongodb:mongodb /var/spool/anacron
(while true; do gosu mongodb anacron -d; sleep 3600; done) &
exec /usr/local/bin/docker-entrypoint.sh "$@"
```

Points de design :
- `chown -R` (récursif) sur `/backups` et `/var/log/mongodb`, pas seulement le dossier de
  premier niveau : corrige aussi les fichiers déjà mal attribués historiquement (pas seulement
  les futurs), puisque l'entrypoint tourne déjà en root à ce moment précis. Volumes concernés
  petits (34 Mo + 35 Mo mesurés) → coût négligeable, exécuté à chaque démarrage du conteneur,
  comportement auto-réparant.
- `mkdir -p` avant chaque `chown` : nécessaire pour ne pas casser les tests existants qui font
  `docker run --rm lmelp-mongo:test <cmd>` **sans** monter `/backups` (le chemin n'existe alors
  pas du tout dans l'image de base) — sans le `mkdir -p`, `chown` échouerait et `set -e` ferait
  planter tout l'entrypoint.
- `gosu` déjà présent dans l'image de base `mongo:latest` (utilisé par son propre entrypoint
  officiel pour dropper les privilèges) — aucune nouvelle dépendance à installer.

## Tests ajoutés (`tests/test_mongodb_image.py`)

1. `TestMongoDBEntrypointOwnership::test_entrypoint_runs_anacron_loop_as_mongodb_user` — test
   statique (lit `mongodb.Dockerfile` en texte, vérifie la présence de `gosu mongodb anacron`
   dans la ligne de boucle). Exécutable sans Docker.

2. `TestMongoDBImageContent::test_entrypoint_chowns_backups_and_logs_to_mongodb` — test
   comportemental : build réel de l'image, démarre un conteneur avec `/backups` monté sur un
   dossier temporaire pré-rempli d'un fichier appartenant à un UID différent de 999 (simule le
   cas réel constaté), poll pendant 15s max que `docker exec ... stat -c '%u' /backups` et le
   fichier pré-existant deviennent bien `999`. Nécessite Docker.

## Contrainte d'environnement rencontrée pendant le fix

Aucun daemon Docker disponible dans le sandbox devcontainer utilisé pour cette session (`docker
ps` → `Cannot connect to the Docker daemon`, confirmé à plusieurs reprises, `dockerd` absent des
process malgré la présence de `/var/run/docker.sock`). Conséquence : seul le test statique a pu
être vérifié RED→GREEN localement dans ce sandbox ; le test comportemental Docker ne peut être
exercé que par la CI GitHub Actions (`ubuntu-latest`, Docker disponible nativement) ou par
l'utilisateur sur sa vraie machine.

**Validation manuelle faite par l'utilisateur sur son laptop réel** (Docker fonctionnel) :
build de l'image + conteneur avec `/backups` monté sur un dossier temporaire pré-rempli d'un
fichier appartenant à son UID personnel → confirmé après démarrage que `/backups` et le fichier
pré-existant appartenaient bien à `999:999` (`mongodb:mongodb`). Effet de bord positif observé :
le fichier de test n'était ensuite plus supprimable sans `sudo` par l'utilisateur (`rm: Permission
denied`) — preuve supplémentaire, quoique surprenante sur le moment, que le chown avait bien eu
lieu.

## Vérification finale en conditions réelles (à faire après merge + republication de l'image)

```bash
find data/backups data/logs/mongodb ! -user guillaume
```

Ne devrait plus rien remonter après redéploiement de la stack avec la nouvelle image (grâce au
`chown -R`, y compris pour l'historique déjà présent, pas seulement les nouveaux fichiers). Pour
ne pas attendre le prochain backup hebdomadaire (anacron), on peut en forcer un manuellement :
`docker exec lmelp-mongo bash -c "FORCE_BACKUP=1 /scripts/backup_mongodb.sh"`.

## Liens

- Issue : castorfou/docker-lmelp#48
- Issue parente (migration NAS) : castorfou/docker-lmelp#47
- Mémoire liée : `251123-1622-consolidation-mongodb-anacron.md` (introduction initiale de
  l'anacron interne au conteneur, avant ce fix)
