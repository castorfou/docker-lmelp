# Issue #83 — dockerd du devcontainer sur noyau hôte 7.0 : docker-in-docker:4 via le template

## Symptôme

Dans le devcontainer, `dockerd` ne démarrait pas sur un hôte Ubuntu en noyau
`7.0.0-43-generic`, et les tests d'image mongo (`tests/test_mongodb_image.py`) échouaient
avec *Cannot connect to the Docker daemon*. `/tmp/dockerd.log` :

```
iptables v1.8.9 (legacy): can't initialize iptables table `nat': Table does not exist
```

Ce noyau ne fournit plus le module `ip_tables` (table `nat` legacy) : seul nftables
fonctionne.

## Cause racine

La cause est plus profonde que l'hypothèse de l'issue, qui proposait de régénérer le lock.
**Le tag `ghcr.io/devcontainers/features/docker-in-docker:2` est figé pour toujours à
2.17.0**, la dernière 2.x. Les correctifs amont paraissent dans les majeures suivantes :

| Tag | Version | Choix d'iptables |
|-----|---------|------------------|
| `:2` | 2.17.0 | au **build** de l'image (legacy si `iptables-legacy -L` répond à ce moment-là) |
| `:3` | 3.1.0 | option `iptablesSwitchAtRuntime`, **fausse** par défaut ; containerd lancé explicitement (erofs désactivé) |
| `:4` | 4.1.3 | `iptablesSwitchAtRuntime` **vraie** par défaut : `docker-init.sh` choisit legacy seulement si `ip_tables` est chargé, nft sinon (4.1.3 : marche aussi avec un entrypoint non-root) |

Régénérer `devcontainer-lock.json` en `:2` ne change rien : il faut **changer de majeure**.

Pour lire la version derrière un tag de feature :
`docker manifest inspect ghcr.io/devcontainers/features/docker-in-docker:N`, annotation
`dev.containers.metadata`. Pour retrouver le commit d'une version :
`gh api "repos/devcontainers/features/commits?path=src/docker-in-docker"`.

Autre trouvaille : avec `docker_in_docker=y`, le template montait
`/var/run/docker.sock` sur `/var/run/docker-host.sock` pour un « proxy socat ». Or
docker-in-docker ne lit jamais ce socket (le proxy socat appartient à
**docker-outside-of-docker**). Ce montage ne servait à rien et donnait un accès root au
Docker de l'hôte.

## Démarche : corriger le template d'abord

À la demande de l'utilisateur, l'ordre a été inversé par rapport à un correctif local :

1. Issue [castorfou/PyFoundry#117](https://github.com/castorfou/PyFoundry/issues/117),
   traitée dans une session PyFoundry et fusionnée sur `main` (commit `eb77808`, PR #118) :
   `:4` avec `"moby": false`, montage `docker-host.sock` retiré, doc et écho
   `postCreateCommand.sh` corrigés.
2. Ici, des tests RED d'abord (`tests/test_devcontainer.py`), puis
   `uvx cruft update --variables-to-update '{"docker_in_docker": "y"}'` depuis `main` de
   PyFoundry, sans release. Le cruft update valide la modif du template.

Un seul conflit, dans `.devcontainer/devcontainer.json` : l'ajout fait à la main
(`docker-in-docker:2: {}`, ours) contre l'entrée du template (`:4`, theirs). Résolu au
profit du template. Le lock a été régénéré par
`npx -y @devcontainers/cli@0.80.1 upgrade --workspace-folder .`, qui écrit le fichier
sans saut de ligne final, ajouté ensuite à la main. Seule docker-in-docker a changé
(2.17.0 → 4.1.3).

## Fichiers modifiés

- `tests/test_devcontainer.py` (nouveau) : un petit lecteur JSONC sans dépendance, qui
  retire les commentaires `//` et `/* */` hors chaînes. Le fichier contient des URL
  `https://` et un commentaire en fin de ligne. Les tests exigent :
  - `docker_in_docker == "y"` dans `.cruft.json` ;
  - une seule feature docker-in-docker, en majeure ≥ 4 ;
  - `iptablesSwitchAtRuntime` absent ou à `true` ;
  - aucun montage de `/var/run/docker.sock` ;
  - les clés du lock égales à celles des features ;
  - une version du lock ≥ 4.0.0, de même majeure, avec `resolved` cohérent avec
    `integrity`.
- `.cruft.json` : `docker_in_docker` à `"y"`, commit `eb77808`.
- `.devcontainer/devcontainer.json` : `docker-in-docker:4` avec `{"moby": false}`.
- `.devcontainer/devcontainer-lock.json` : 4.1.3,
  `sha256:fae40f3c8be5a7c3b0db344c1d30341bc2c91ba38d1d5b14cd2ad72e6d65d084`.
- `.devcontainer/postCreateCommand.sh` : écho « Docker-in-Docker activé (daemon Docker
  propre au conteneur) », venu du template.

## Validation

Après un « Rebuild Container », sans aucun contournement :
- `docker info` répond (29.9.3) ;
- `update-alternatives --query iptables` affiche `/usr/sbin/iptables-nft` ;
- `containerd --config /etc/containerd/config.toml` et
  `dockerd --containerd /run/containerd/containerd.sock` sont lancés par
  `/usr/local/share/docker-init.sh` ;
- `uv run --active pytest` passe en entier, tests d'image mongo compris.

## Règles retenues

- Une feature devcontainer en `:N` suit la dernière N.x **seulement** : un correctif amont
  publié dans une majeure supérieure n'arrive jamais par le lock. Quand un bug de feature
  persiste, vérifier la version derrière le tag avant de régénérer le lock.
- Une feature fournie par le template s'active par la variable cruft
  (`--variables-to-update`), jamais par un ajout à la main dans `devcontainer.json`.
  Sinon, chaque cruft update conflicte et les correctifs du template n'arrivent pas.
- `cruft diff` après la mise à jour ne montre plus que des écarts propres au projet,
  antérieurs à cette issue : pragma `allowlist secret`, extension
  `ms-azuretools.vscode-containers`, auteur npm.
