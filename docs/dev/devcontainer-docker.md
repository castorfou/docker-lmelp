# Docker dans le Dev Container

Les tests de `tests/test_mongodb_image.py` construisent l'image `lmelp-mongo` et lancent des
conteneurs. Le Dev Container embarque donc son propre daemon Docker, fourni par la feature
[`docker-in-docker`](https://github.com/devcontainers/features/tree/main/src/docker-in-docker).

## Configuration

La feature vient du template PyFoundry, activée par la variable cruft `docker_in_docker` :

```json
// .cruft.json
"docker_in_docker": "y"
```

```json
// .devcontainer/devcontainer.json
"ghcr.io/devcontainers/features/docker-in-docker:4": {
    "moby": false
}
```

- **Daemon propre au conteneur** : `dockerd` tourne dans le Dev Container. Les images et
  conteneurs de test n'apparaissent pas dans le Docker de l'hôte. Le socket de l'hôte
  (`/var/run/docker.sock`) n'est pas monté.
- **Démarrage** : `/usr/local/share/docker-init.sh` lance `containerd`, puis
  `dockerd --containerd /run/containerd/containerd.sock`.
- **Choix d'iptables au démarrage** : avant de lancer `dockerd`, `docker-init.sh` choisit
  l'alternative `iptables`. Il prend `iptables-legacy` seulement si le module noyau
  `ip_tables` est chargé, et `iptables-nft` sinon. Le même conteneur fonctionne donc sur un
  hôte ancien comme sur un noyau récent sans `ip_tables` (Ubuntu 7.0).
- **Version figée** : `.devcontainer/devcontainer-lock.json` épingle la version exacte
  (digest) de chaque feature.

## Règles

- **Majeure 4 au minimum.** Un tag de feature `:N` ne suit que la dernière N.x :
  `docker-in-docker:2` reste à 2.17.0, qui choisit iptables au build de l'image. Avec ce
  tag, `dockerd` ne démarre pas sur un noyau sans `ip_tables`, et régénérer le lock n'y
  change rien.
- **Activation par cruft, pas à la main.** La feature s'active avec
  `cruft update --variables-to-update '{"docker_in_docker": "y"}'`. Un ajout à la main dans
  `devcontainer.json` conflicte à chaque mise à jour du template et bloque ses correctifs.
- **Lock à jour.** Après un changement de feature, régénérer le lock et le commiter :

  ```bash
  npx -y @devcontainers/cli@0.80.1 upgrade --workspace-folder .
  ```

`tests/test_devcontainer.py` vérifie ces règles : variable cruft, majeure ≥ 4,
`iptablesSwitchAtRuntime` jamais désactivé, aucun montage du socket de l'hôte, lock
synchronisé avec les features et en version ≥ 4.0.0.

## Vérifier que Docker fonctionne

```bash
docker info --format '{{.ServerVersion}}'           # répond sans intervention
update-alternatives --query iptables | grep Value   # iptables-nft sur un noyau sans ip_tables
uv run --active pytest tests/test_mongodb_image.py
```

## Dépannage

### `can't initialize iptables table 'nat': Table does not exist`

`dockerd` a démarré avec `iptables-legacy` sur un noyau qui n'a pas `ip_tables`.

1. Vérifier la feature et sa version figée :

    ```bash
    grep docker-in-docker .devcontainer/devcontainer.json
    grep -A1 docker-in-docker .devcontainer/devcontainer-lock.json
    ```

2. Si la majeure est inférieure à 4, faire un `cruft update` (voir plus haut), régénérer
   le lock, puis « Dev Containers: Rebuild Container ».

Contournement à chaud, perdu au prochain rebuild :

```bash
sudo update-alternatives --set iptables /usr/sbin/iptables-nft
sudo update-alternatives --set ip6tables /usr/sbin/ip6tables-nft
sudo nohup dockerd > /tmp/dockerd-nft.log 2>&1 &
```

### Lire la version réelle derrière un tag de feature

```bash
docker manifest inspect ghcr.io/devcontainers/features/docker-in-docker:4 \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['annotations']['dev.containers.metadata'][:80])"
```

## Historique

- Issue [#83](https://github.com/castorfou/docker-lmelp/issues/83) : `dockerd` ne démarrait pas
  sur un noyau hôte 7.0 avec `docker-in-docker:2`, ajouté à la main. Le passage à `:4` s'est
  fait dans le template ([PyFoundry#117](https://github.com/castorfou/PyFoundry/issues/117)),
  puis ici par `cruft update`.
