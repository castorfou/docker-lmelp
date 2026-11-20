# Issue #94 — Service `pap` (lmelp-pap) dans la stack

Contexte : décision castorfou/lmelp-pap#58 (l'appli pap tourne sur le NAS, dans
docker-lmelp), image `ghcr.io/castorfou/lmelp-pap` livrée par castorfou/lmelp-pap#64.
Usage de l'image : [L'appli pap en conteneur et sur le NAS](https://castorfou.github.io/lmelp-pap/user/appli-docker-nas/).

## Ce qui a été fait

- `docker-compose.yml` : service `pap` (conteneur `lmelp-pap`), image `:latest`, label
  Watchtower, réseau `lmelp-network`, `depends_on: mongo` (Mongo pas encore utilisé,
  prévu par lmelp-pap#65), port `${PAP_PORT:-8090}:8090`, `PUID`/`PGID` partagés avec
  le backend, **volume unique** `${PAP_PATH_HOTE:-./data/pap}:/data`.
- Pas de healthcheck dans le compose : celui de l'image (`GET /health`) s'applique
  (vérifié par `test_pap_keeps_image_healthcheck`).
- `.env.example` (`./data/pap`) et `.env.nas.example` (`/volume1/docker/lmelp/pap`) :
  `PAP_PORT=8090`, `PAP_PATH_HOTE`. Commentaires PUID/PGID étendus à `pap`.
- `data/pap/.gitkeep` + `.gitignore`.
- Docs : `docs/user/migration-nas.md` (étape 1 : arborescence
  `pap/{cache,processed,audios,logs}` et amorçage depuis `data/raw/cache/` et
  `data/processed/` de lmelp-pap ; étape 8 : reverse proxy
  `pap.lmelp.ascot63.synology.me` → `localhost:8090` ; étape 9 : `pap` healthy,
  fichiers `1027:1027`), `docs/user/configuration.md` (section « Variables de l'appli
  pap »), `README.md`, `docs/user/portainer.md`, `docs/user/installation.md`.
- Tests : `tests/test_docker_compose.py::TestPapService` et `::TestPapNasDocumentation`.

## Décisions et points saillants

- **Nom de variable `PAP_PATH_HOTE`** (pas `PAP_PATH`, abandonné dans la version initiale
  de l'issue avec le montage en trois volumes). Conséquence : la regex du test historique
  `TestDockerComposeLogPathSeparation` (`[A-Z_]+_PATH`) ne voit pas cette variable ; les
  nouveaux tests utilisent `[A-Z_]*PATH[A-Z_]*`.
- **Règle #51 appliquée** : l'entrypoint de l'image chowne `/data` récursivement, donc le
  dossier hôte `pap/` n'est monté que dans `pap` et n'est imbriqué avec aucun autre
  volume (défaut du compose **et** chemins absolus de `.env.nas.example`, testés).
  `audios/` du back-office reste réservé aux intégraux valides ; les audios rapatriés de
  pap vivent dans `pap/audios/`.
- Vigilance chemin NAS : l'utilisateur a d'abord écrit `/volume1/docker/pap` en pensant
  `/volume1/docker/lmelp/pap` ; toujours confronter un chemin annoncé à `.env.nas.example`.

## Apprentissage : un `docker pull` « muet » n'est pas forcément bloqué

L'image fait ~609 Mo compressés (couches de 414 et 145 Mo) et le débit vers ghcr.io
depuis le devcontainer était ~1 Mo/s : ~10 min de pull. Le pull a été interrompu à tort
(timeouts de 100-120 s, puis arrêt de la tâche de fond) parce que `| tail -3` masquait
toute progression. Le log du daemon (`/tmp/dockerd.log`) montrait pourtant des couches
téléchargées puis `Not continuing with pull after error: context canceled` au moment de
l'arrêt.

Diagnostic rapide à réutiliser :
- taille réelle : manifeste via `https://ghcr.io/token?scope=repository:<repo>:pull`,
  puis `GET /v2/<repo>/manifests/<digest amd64>` et somme des `layers[].size` ;
- débit : `curl --max-time 20 -w '%{speed_download}'` sur la plus grosse couche ;
- daemon sain : un `docker pull alpine` passe ;
- lancer un pull long en arrière-plan **sans timeout**, sortie redirigée vers un fichier.

## Test local : résultat et piège réseau du devcontainer

Avec `PUID=1027 PGID=1027 docker compose up -d --no-deps pap` (`--no-deps` parce que le
port 27018 était pris par le Mongo local de l'utilisateur) : `pap` passe `healthy`,
`/data/{audios,cache,logs,processed}` sont créés en `1027:1027`, le processus
`lmelp-pap arbitrer --sans-navigateur` tourne en uid 1027, et `GET /health` renvoie
`{"status": "ok"}` depuis un conteneur voisin de `lmelp-network`.

Depuis le devcontainer en revanche, `curl localhost:8090` donne *Connection reset by
peer*. Cause : le devcontainer tourne en `--network=host`
(`.devcontainer/devcontainer.json:8`), donc le dockerd du devcontainer partage la table
de routage du laptop. Le `lmelp-network` présent (`16065251b942`, `172.18.0.0/16`)
existait avant le test, très probablement depuis une session antérieure ; un bridge du
Docker du laptop (`br-203e2f5ea028`, éteint) occupait entre-temps la même plage, et
`ip route get 172.18.0.2` partait vers lui : docker-proxy coupait la connexion.

Contre-épreuve (sur remarque de l'utilisateur, qui n'avait jamais vu le problème en
docker-in-docker dans back-office-lmelp) : après `docker compose down`, le réseau recréé
reçoit `172.22.0.0/16`, plage libre (Docker évite les routes existantes à la création),
et `curl localhost:8090/health` renvoie 200. Le conflit n'arrive donc qu'avec un réseau
ancien dont la plage a été reprise par l'autre Docker ; ce n'est pas un piège général.
L'origine exacte du réseau ancien n'a pas pu être vérifiée (supprimé par le `down`).

Diagnostic : `ip route get <IP du conteneur>` doit sortir sur le bridge du réseau compose
(`br-<id du réseau>`) ; sinon, recréer le réseau (`docker compose down` puis `up`).

Autre écart vu au même test : `mongo` `unhealthy`, car le `.env` local de l'utilisateur
donne des chemins absolus du laptop (`/home/guillaume/git/docker-lmelp/…`) absents du
devcontainer ; Docker les a créés vides en root et `mongod` n'a pas pu ouvrir son log.
Ces dossiers ont été supprimés ensuite. Attention : le comptage préalable
`find … -type f | wc -l` lancé en `vscode` affichait 0 faute de droits, alors que 16
fichiers (tous issus du test) y étaient : compter avec les mêmes droits que la suppression.

Après le test, `data/pap/` (chowné en 1027 par l'entrypoint) a été remis en 1000:1000 et
vidé via un conteneur alpine, pour ne pas laisser au dépôt des fichiers non modifiables
par `vscode`.

## Suivi

- Issue `castorfou/lmelp-mobile` à ouvrir pour la page Écosystème (service ajouté).
- Mise à jour de la stack NAS après le merge sur `main` (« Update the stack », vérifier
  `Created` de `lmelp-pap`).

## Port NAS : 8085 au lieu de 8090

Premier « Update the stack » sur le NAS : `listen tcp4 0.0.0.0:8090: bind: address
already in use`. Le port 8090 du NAS était déjà pris (service non identifié, pas d'accès
SSH au NAS). Décision de l'utilisateur : publier `pap` sur **8085** côté NAS
(`PAP_PORT=8085` dans `.env.nas.example`, destination du reverse proxy DSM à 8085) ;
l'appli écoute toujours sur 8090 dans le conteneur et le défaut local reste 8090. Le test
`TestPapNasDocumentation::test_step8_reverse_proxy_entry_for_pap` lit désormais le port
dans `.env.nas.example` au lieu de le figer. Sans SSH, vérifier un port libre via la
colonne **Published Ports** de la liste **Containers** de Portainer (ne voit pas les
paquets DSM hors Docker).
