# Issue #74 — Épingler la version de MongoDB (`mongo:latest` → 9.0 casse le démarrage)

## Contexte

`mongodb.Dockerfile` partait de `FROM mongo:latest`. Depuis le 1er octobre 2026,
`mongo:latest` pointe sur **MongoDB 9.0**. Les données du NAS sont en
`featureCompatibilityVersion` (FCV) **8.2**, or mongod 9.0 n'ouvre que des données en
FCV 8.0 ou 8.3 ([doc d'upgrade 9.0](https://www.mongodb.com/docs/manual/release-notes/9.0-upgrade/)).

Au prochain build de l'image (tout push sur `main` touchant les chemins surveillés par
`.github/workflows/build-mongo-image.yml`, ou un `workflow_dispatch`), `lmelp-mongo:latest`
serait passée en 9.0, Watchtower l'aurait déployée et `mongod` serait sorti en code 62
(`UPGRADE PROBLEM: Found an invalid featureCompatibilityVersion document`), en boucle.

Incident réellement subi sur un autre conteneur `mongo:latest` du même NAS. Ici le
correctif est **préventif** : l'image publiée le 27/09 n'avait pas encore été reconstruite.

## Root cause

Un tag flottant sur une image de **base de données**. Pour un service sans état, `latest`
se contente d'apporter une version plus récente. Pour une base, le format des données sur
disque lie le binaire à une plage de versions : MongoDB impose de monter **une majeure à
la fois** et de relever la FCV explicitement entre deux. Le tag flottant fait le saut à
notre place, sans prévenir, au moment d'un build déclenché pour une tout autre raison.

## Vérifications faites avant de choisir le tag

Docker Hub, le 01/10/2026 (API `hub.docker.com/v2/repositories/library/mongo/tags/<tag>`,
utilisable sans daemon Docker) :

| Tag | Digest amd64 | Dernière mise à jour |
|---|---|---|
| `latest`, `9`, `9.0` | `9fb436085129` | 01/10/2026 |
| `8`, `8.3` | `949d53a1e0f0` | 16/09/2026 |
| `8.2` | `41afd6e1183f` | 23/07/2026 |

Sur le NAS : `{ featureCompatibilityVersion: { version: '8.2' }, ok: 1 }`.

## Décision : `FROM mongo:8`, pas `mongo:8.2`

- `mongo:8` = 8.3 aujourd'hui, et un binaire 8.3 ouvre des données en FCV 8.2.
- `mongo:8.2` n'est plus mis à jour depuis juillet : on perdrait les correctifs.
- `mongo:8` ne peut pas glisser vers 9.x et reçoit les patchs 8.x à chaque rebuild.
- 8.3 est le point de passage obligé vers 9.0.

## Modifications

- `mongodb.Dockerfile:9-14` : `FROM mongo:8`, avec un commentaire qui explique l'épinglage.
- `docker-compose.mongo7.yml` : commentaire d'en-tête complété. Cet override local
  (`mongo:7.0`, nécessaire car MongoDB 8.x ne démarre pas sur noyau 6.19–7.0.13,
  SERVER-121912) exige un répertoire de données en FCV 7.0. Une copie du volume du NAS
  ne s'y ouvre pas : il faut restaurer un dump avec `mongorestore`.
- `tests/test_mongodb_image.py` :
  - helper `_mongo_base_image_tag()` et regex `PINNED_MONGO_TAG` (`^\d+(\.\d+){0,2}$`) ;
  - `TestMongoBaseImagePinned::test_dockerfile_base_image_is_pinned_to_a_major_version`
    (le test RED : `got 'latest'`) ;
  - `TestMongoBaseImagePinned::test_compose_files_do_not_use_floating_official_mongo_tag`
    (parcourt `docker-compose*.yml`) ;
  - `TestMongoDBImageContent::test_mongod_version_matches_pinned_base_image` (compare
    `mongod --version` au tag du `FROM`, sur l'image construite).
- Documentation : nouvelle page `docs/user/mongodb-upgrade.md` (procédure de montée de
  version majeure), `docs/dev/mongodb-custom-image.md`, `docs/user/backup-restore.md`,
  `docs/user/installation.md`, `README.md`, et une section piège dans `CLAUDE.md`.

## Apprentissages

### `db.version(); db.adminCommand(...)` n'affiche que la dernière expression

La commande de vérification de l'issue (`mongosh --quiet --eval 'db.version();
db.adminCommand({getParameter:1, featureCompatibilityVersion:1})'`) n'a renvoyé que la
FCV : `mongosh --eval` n'imprime que le résultat de la **dernière** expression. Pour avoir
les deux, tout mettre dans un seul objet :

```
mongosh --quiet --eval 'printjson({binaire: db.version(), fcv: db.adminCommand({getParameter:1, featureCompatibilityVersion:1}).featureCompatibilityVersion.version})'
```

### La version du binaire et la FCV sont deux choses distinctes

La FCV ne monte jamais toute seule. L'image du 27/09 a été construite alors que
`mongo:latest` pointait déjà sur 8.3 (depuis le 16/09) : le binaire en place est donc
probablement 8.3 avec une FCV restée en 8.2. Un diagnostic de version doit toujours
relever les deux.

### Le dev container n'a pas de daemon Docker

`docker build` et `docker run` échouent dans le dev container. Les tests de
`TestMongoDBImageContent` et `test_image_can_be_built` ne tournent donc qu'en CI
(`ci.yml` tourne sur toutes les branches à chaque push). Conséquences pour le workflow TDD :

- écrire le test RED sous forme **statique** (lecture du Dockerfile) pour pouvoir le voir
  échouer puis passer en local ;
- pousser tôt les commits `test:` et `fix:` pour faire valider les tests conteneur par la
  CI avant de demander le test global à l'utilisateur ;
- en local, lancer la suite avec
  `--deselect tests/test_mongodb_image.py::TestMongoDBImageContent --deselect tests/test_mongodb_image.py::TestMongoDBImageBuild::test_image_can_be_built`.

Sur le poste de l'utilisateur (noyau 7.0.0-34), une image 8.x se construit mais `mongod`
n'y démarre pas (SERVER-121912) : seul `mongod --version` y est vérifiable.

### Règle retenue

Ne jamais baser une image de base de données sur un tag flottant. Épingler la majeure, et
traiter chaque montée de version comme une opération manuelle : sauvegarde, une majeure à
la fois, `setFeatureCompatibilityVersion` avec `confirm: true` entre deux.

## Suite possible (hors périmètre de l'issue)

Passage en 9.0, documenté dans `docs/user/mongodb-upgrade.md` :

1. Binaire 8.3 en place, puis `db.adminCommand({setFeatureCompatibilityVersion: "8.3", confirm: true})`.
2. `FROM mongo:9`, rebuild et redéploiement, puis
   `db.adminCommand({setFeatureCompatibilityVersion: "9.0", confirm: true})`.
