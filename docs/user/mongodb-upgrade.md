# Version de MongoDB et montée de version majeure

L'image `ghcr.io/castorfou/lmelp-mongo` embarque une majeure précise de MongoDB, fixée
dans `mongodb.Dockerfile` (`FROM mongo:8`). Les correctifs de la majeure 8 arrivent à
chaque reconstruction de l'image ; un changement de majeure est une opération manuelle,
décrite sur cette page.

!!! note "Noyaux Linux 6.19 à 7.0.13"
    Certaines versions de `mongod` (8.0.21 et suivantes, premières 8.3 comme 8.3.13,
    premières 9.0) refusent de démarrer quand `uname -r` indique un noyau Linux de 6.19 à
    7.0.13 :

    ```
    MongoDB cannot start: Linux kernel versions 6.19 and newer has a known incompatibility
    with this version of MongoDB.
    ```

    Tous les noyaux Ubuntu 7.0 sont concernés : leur version s'affiche `7.0.0-NN`. C'est le
    cas des runners GitHub Actions et des postes Ubuntu récents. Les versions corrigées
    ([SERVER-136848](https://jira.mongodb.org/browse/SERVER-136848)) démarrent sur ces
    noyaux, et un tag de série (`mongo:8`, `mongo:8.3`) suit automatiquement le dernier
    correctif.
    `tests/test_mongodb_image.py::TestMongoBaseImagePinned` refuse un `FROM` épinglé sur
    une version de correctif plus ancienne.

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

### 2. Vérifier que le binaire est en 8.3

Avec `FROM mongo:8`, le binaire est en 8.3 ou plus. Le vérifier avec la commande
ci-dessus avant de toucher à la FCV.

### 3. Amener la FCV en 8.3

Le binaire doit être en 8.3 (vérifier avec la commande ci-dessus), puis :

```bash
docker exec lmelp-mongo mongosh --quiet --eval \
  'db.adminCommand({setFeatureCompatibilityVersion: "8.3", confirm: true})'
```

Relever à nouveau les deux versions : la FCV doit valoir `8.3`.

### 4. Passer l'image en 9.0

Dans `mongodb.Dockerfile`, remplacer `FROM mongo:8` par `FROM mongo:9`, puis publier la
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

Le binaire de l'image est une version soumise au contrôle du noyau, et la machine tourne
sur un noyau de 6.19 à 7.0.13. Vérifier la ligne `FROM` de `mongodb.Dockerfile` (attendu :
un tag de série comme `mongo:8`, pas une version de correctif ancienne), reconstruire ou
tirer l'image pour récupérer le dernier correctif, et relever le noyau de la machine
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
dont le noyau Linux (6.19 à 7.0.13) empêche une version de MongoDB 8.x de démarrer.
Il exige un répertoire
de données en FCV 7.0 : une copie du volume d'une instance 8.x ne s'y ouvre pas. Pour
reprendre ces données, partir d'un répertoire `MONGO_DATA_PATH` vide et
[restaurer un backup](backup-restore.md#restauration-depuis-un-backup). MongoDB ne
garantit pas la restauration d'un dump vers une version plus ancienne : vérifier les
données après l'opération.

```bash
docker compose -f docker-compose.yml -f docker-compose.mongo7.yml up -d
```
