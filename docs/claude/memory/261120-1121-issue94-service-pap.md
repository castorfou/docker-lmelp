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
(`.devcontainer/devcontainer.json:8`), donc le dockerd du devcontainer partage l'espace
réseau du laptop. Il a attribué `172.18.0.0/16` à `lmelp-network`, sous-réseau déjà pris
par un bridge (éteint) du Docker du laptop : `ip route get 172.18.0.2` part vers ce
bridge et docker-proxy coupe la connexion. Un conteneur sur le bridge par défaut
(172.17) se joint normalement. Rien de propre à `pap` ni au NAS.

Diagnostic : `ip route get <IP du conteneur>` doit sortir sur le bridge du réseau compose
(`br-<id du réseau>`) ; sinon, conflit de sous-réseau avec le Docker de l'hôte.

Après le test, `data/pap/` (chowné en 1027 par l'entrypoint) a été remis en 1000:1000 et
vidé via un conteneur alpine, pour ne pas laisser au dépôt des fichiers non modifiables
par `vscode`.

## Suivi

- Issue `castorfou/lmelp-mobile` à ouvrir pour la page Écosystème (service ajouté).
- Mise à jour de la stack NAS après le merge sur `main` (« Update the stack », vérifier
  `Created` de `lmelp-pap`).
