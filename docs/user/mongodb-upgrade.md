# Version de MongoDB et montée de version majeure

L'image `ghcr.io/castorfou/lmelp-mongo` embarque une série précise de MongoDB, fixée dans
`mongodb.Dockerfile` (`FROM mongo:8.2`). Les correctifs de la série 8.2 arrivent à chaque
reconstruction de l'image ; un changement de version est une opération manuelle, décrite
sur cette page.

!!! warning "Pourquoi 8.2 et pas `mongo:8`"
    `mongod` 8.0.21 et suivantes, 8.3 et 9.0 refusent de démarrer quand `uname -r` indique
    un noyau Linux de 6.19 à 7.0.13 :

    ```
    MongoDB cannot start: Linux kernel versions 6.19 and newer has a known incompatibility
    with this version of MongoDB.
    ```

    Tous les noyaux Ubuntu 7.0 sont concernés : leur version s'affiche `7.0.0-NN`, même
    quand ils contiennent le correctif du noyau. C'est le cas des runners GitHub Actions et
    des postes Ubuntu récents. La série 8.2 n'a pas ce contrôle et démarre sur ces noyaux.
    Le noyau des NAS Synology est plus ancien et n'est pas concerné.

    Le retour sur `mongo:8` (8.3 et suivantes) attend la correction de
    [SERVER-136848](https://jira.mongodb.org/browse/SERVER-136848).
    `tests/test_mongodb_image.py::TestMongoBaseImagePinned` refuse une série soumise à ce
    contrôle.

## Binaire et FCV : deux versions à connaître

Une instance MongoDB porte deux numéros de version :

| Version | Ce qu'elle désigne | Comment elle change |
|---|---|---|
| **Binaire** | La version de `mongod` installée dans l'image | Avec l'image du conteneur |
| **FCV** (`featureCompatibilityVersion`) | Le format des données sur disque | Uniquement par une commande explicite |

La FCV ne suit jamais le binaire toute seule : après une mise à jour de l'image, les
données restent au format précédent tant que la commande `setFeatureCompatibilityVersion`
n'a pas été lancée.

### Relever les deux versions

```bash
docker exec lmelp-mongo mongosh --quiet --eval 'printjson({
  binaire: db.version(),
  fcv: db.adminCommand({getParameter: 1, featureCompatibilityVersion: 1}).featureCompatibilityVersion.version
})'
```

Résultat attendu, par exemple :

```
{ binaire: '8.3.1', fcv: '8.2' }
```

!!! note "Une seule valeur par `--eval`"
    `mongosh --eval` n'affiche que le résultat de la dernière expression. Deux commandes
    séparées par un `;` ne renvoient que la seconde, d'où le regroupement dans un seul objet.

## Règles d'une montée de version

1. **Une majeure à la fois.** `mongod` n'ouvre que des données dont la FCV appartient à
   la majeure précédente. MongoDB 9.0 démarre sur des données en FCV 8.0 ou 8.3, pas en 8.2.
2. **Sauvegarder avant.** Une fois la FCV relevée, le binaire précédent ne peut plus ouvrir
   les données : le retour arrière passe par la restauration d'un backup.
3. **Relever la FCV explicitement**, avec `confirm: true`, après avoir vérifié que la
   nouvelle version tourne correctement.
4. **Ne jamais utiliser un tag flottant** (`mongo:latest`) pour une image de base de
   données : il change de majeure sans prévenir, lors d'une reconstruction quelconque.

## Procédure : de 8.x à 9.0

### 1. Sauvegarder

```bash
docker exec -e FORCE_BACKUP=1 lmelp-mongo /scripts/backup_mongodb.sh
ls -lh data/backups/
```

Voir [Gestion des backups](backup-restore.md) pour la restauration.

### 2. Passer le binaire en 8.3

Dans `mongodb.Dockerfile`, remplacer `FROM mongo:8.2` par `FROM mongo:8.3`, publier
l'image (voir l'étape 4) et vérifier que le binaire est en 8.3. Cette étape suppose que
[SERVER-136848](https://jira.mongodb.org/browse/SERVER-136848) est corrigé : sinon, la CI
échoue sur les runners GitHub.

### 3. Amener la FCV en 8.3

Le binaire doit être en 8.3 (vérifier avec la commande ci-dessus), puis :

```bash
docker exec lmelp-mongo mongosh --quiet --eval \
  'db.adminCommand({setFeatureCompatibilityVersion: "8.3", confirm: true})'
```

Relever à nouveau les deux versions : la FCV doit valoir `8.3`.

### 4. Passer l'image en 9.0

Dans `mongodb.Dockerfile`, remplacer `FROM mongo:8.3` par `FROM mongo:9`, puis publier la
modification sur `main`. Le workflow GitHub Actions reconstruit et publie
`ghcr.io/castorfou/lmelp-mongo:latest`, que Watchtower déploie ensuite. Sans Watchtower :

```bash
docker compose pull mongo
docker compose up -d mongo
```

Vérifier que le conteneur est `healthy` et que le binaire est en 9.0 :

```bash
docker ps --filter name=lmelp-mongo
```

### 5. Amener la FCV en 9.0

Après quelques jours de fonctionnement normal :

```bash
docker exec lmelp-mongo mongosh --quiet --eval \
  'db.adminCommand({setFeatureCompatibilityVersion: "9.0", confirm: true})'
```

## Dépannage

### Le conteneur s'arrête au démarrage : « Linux kernel versions 6.19 and newer »

Le binaire de l'image appartient à une série soumise au contrôle du noyau (8.0.21 et
suivantes, 8.3, 9.0), et la machine tourne sur un noyau de 6.19 à 7.0.13. Vérifier la
ligne `FROM` de `mongodb.Dockerfile` (attendu : `mongo:8.2`) et le noyau de la machine
(`uname -r`). Voir l'encadré en haut de cette page.

### Le conteneur redémarre en boucle avec le code de sortie 62

```bash
docker logs lmelp-mongo 2>&1 | grep -i "featureCompatibilityVersion"
```

Un message de ce type indique que le binaire est trop récent (ou trop ancien) pour la FCV
des données :

```
UPGRADE PROBLEM: Found an invalid featureCompatibilityVersion document ...
Shutting down attr={"exitCode":62}
```

Les données ne sont pas endommagées. Pour revenir à un état fonctionnel :

1. Redémarrer avec une image dont le binaire accepte la FCV en place (la majeure
   précédente).
2. Relever la FCV comme décrit plus haut.
3. Reprendre la montée de version, une majeure à la fois.

### Poste local avec `docker-compose.mongo7.yml`

Le fichier `docker-compose.mongo7.yml` remplace l'image par `mongo:7.0` pour les postes
dont le noyau Linux (6.19 à 7.0.13) empêche MongoDB 8.x de démarrer. Il exige un répertoire
de données en FCV 7.0 : une copie du volume d'une instance 8.x ne s'y ouvre pas. Pour
reprendre ces données, partir d'un répertoire `MONGO_DATA_PATH` vide et
[restaurer un backup](backup-restore.md#restauration-depuis-un-backup). MongoDB ne
garantit pas la restauration d'un dump vers une version plus ancienne : vérifier les
données après l'opération.

```bash
docker compose -f docker-compose.yml -f docker-compose.mongo7.yml up -d
```
