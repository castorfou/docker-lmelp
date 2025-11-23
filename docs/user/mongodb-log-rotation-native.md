# Rotation des logs MongoDB - Installation native (Ubuntu)

Ce guide explique comment configurer la rotation automatique des logs MongoDB sur une installation **native** (non-Docker) sur Ubuntu.

!!! note "Prérequis"
    MongoDB doit être déjà installé et fonctionnel sur votre système Ubuntu.

## Vue d'ensemble

La rotation des logs empêche le fichier `mongod.log` de consommer trop d'espace disque. Cette configuration utilise :

- **Fréquence** : **Quotidienne** (1 fois par jour minimum)
- **Anacron** : Adapté aux portables qui peuvent être éteints la nuit
- **Compression** : Logs archivés compressés avec gzip
- **Rétention** : 30 jours par défaut (configurable)

!!! info "Fréquence d'exécution"
    La rotation s'exécute **1 fois par jour**, 5 minutes après le démarrage de la machine si elle n'a pas été exécutée dans les dernières 24h. Parfait pour les portables qui ne sont pas allumés 24h/24 !

Bien sur cela est configurable:

- pour changer la frequence de declenchement : modifier `/etc/anacrontab`
- pour la compression des logs : modifier `/etc/cron.daily/mongodb-logrotate`
- pour la duree de retention : modifier `/etc/cron.daily/mongodb-logrotate`

## Installation

### 1. Installer anacron et gzip

```bash
sudo apt-get update
sudo apt-get install -y anacron gzip
```

### 2. Configurer MongoDB pour la rotation

Éditer le fichier de configuration MongoDB (généralement `/etc/mongod.conf`) :

```bash
sudo nano /etc/mongod.conf
```

Modifier la section `systemLog` pour ajouter `logRotate: reopen` :

```yaml
systemLog:
  destination: file
  path: /var/log/mongodb/mongod.log
  logAppend: true
  logRotate: reopen  # Active la rotation externe
```

Redémarrer MongoDB pour appliquer la configuration :

```bash
sudo systemctl restart mongod
```

### 3. Copier le script de rotation

Créer le répertoire pour les scripts si nécessaire :

```bash
sudo mkdir -p /usr/local/bin
```

Copier le script de rotation depuis ce repository :

```bash
sudo cp scripts/rotate_mongodb_logs.sh /usr/local/bin/
sudo chmod +x /usr/local/bin/rotate_mongodb_logs.sh
```

### 4. Configurer anacron

Créer un job anacron quotidien :

```bash
sudo nano /etc/cron.daily/mongodb-logrotate
```

Contenu du fichier :

```bash
#!/bin/bash
/usr/local/bin/rotate_mongodb_logs.sh --compress --keep-days 30 >> /var/log/mongodb/logrotate.log 2>&1
```

Rendre le fichier exécutable :

```bash
sudo chmod +x /etc/cron.daily/mongodb-logrotate
```

### 5. Créer le fichier de log de rotation

Créer le fichier `logrotate.log` avec les permissions appropriées pour que cron puisse y écrire :

```bash
sudo touch /var/log/mongodb/logrotate.log
sudo chmod 666 /var/log/mongodb/logrotate.log
```

**Pourquoi** : Le script cron s'exécute en tant que `root` et doit pouvoir écrire dans ce fichier pour tracer les rotations automatiques.

## Vérification

### Vérifier qu'anacron est actif

```bash
systemctl status anacron
```

Si anacron n'est pas actif, le démarrer :

```bash
sudo systemctl enable anacron
sudo systemctl start anacron
```

### ⚠️ Important pour les portables : Désactiver la condition AC Power

Par défaut sur Ubuntu, anacron ne s'exécute **que lorsque le portable est branché sur secteur** (`ConditionACPower=true`). Pour que la rotation fonctionne même sur batterie :

```bash
# Créer un override du service anacron
sudo systemctl edit anacron.service
```

Ajouter ces lignes dans l'éditeur qui s'ouvre :

```ini
[Unit]
ConditionACPower=
```

Sauvegarder (Ctrl+X, Y, Entrée), puis recharger et redémarrer :

```bash
sudo systemctl daemon-reload
sudo systemctl restart anacron
```

Vérifier que la condition a été supprimée :

```bash
systemctl status anacron
```

Vous ne devriez plus voir de message comme :
```
anacron.service was skipped because of an unmet condition check (ConditionACPower=true)
```

### Tester la rotation manuellement

```bash
sudo /usr/local/bin/rotate_mongodb_logs.sh --compress --keep-days 30
```

### Vérifier les fichiers de logs

```bash
ls -lh /var/log/mongodb/
```

Vous devriez voir :
- `mongod.log` : Fichier actif
- `mongod.log.2025-11-23T...` : Logs rotés (après rotation)
- `mongod.log.2025-11-22T....gz` : Logs compressés

### Consulter les logs de rotation

```bash
cat /var/log/mongodb/logrotate.log
```

## Personnalisation

### Modifier la rétention

Pour garder les logs plus longtemps (ex: 60 jours), éditer `/etc/cron.daily/mongodb-logrotate` :

```bash
sudo nano /etc/cron.daily/mongodb-logrotate
```

Modifier `--keep-days 30` par `--keep-days 60`.

### Désactiver la compression

Retirer l'option `--compress` dans `/etc/cron.daily/mongodb-logrotate` :

```bash
#!/bin/bash
/usr/local/bin/rotate_mongodb_logs.sh --keep-days 30 >> /var/log/mongodb/logrotate.log 2>&1
```

## Dépannage

### La rotation ne s'exécute pas automatiquement

1. **Vérifier qu'anacron est actif** :
```bash
systemctl status anacron
```

2. **Vérifier si la condition AC Power bloque l'exécution** :
```bash
sudo journalctl -u anacron | grep "ConditionACPower"
```

Si vous voyez `was skipped because of an unmet condition check (ConditionACPower=true)`, anacron ne s'exécute que sur secteur. Voir la section [Désactiver la condition AC Power](#important-pour-les-portables-desactiver-la-condition-ac-power) ci-dessus.

3. **Vérifier les logs système** :
```bash
sudo journalctl -u anacron -f
```

4. **Tester manuellement** :
```bash
sudo /usr/local/bin/rotate_mongodb_logs.sh
```

### Erreur de connexion à MongoDB

Si le script ne peut pas se connecter à MongoDB, vérifier :

1. MongoDB est démarré :
```bash
sudo systemctl status mongod
```

2. Les variables d'environnement (si MongoDB n'écoute pas sur localhost:27017) :
```bash
export MONGO_HOST=localhost
export MONGO_PORT=27017
sudo -E /usr/local/bin/rotate_mongodb_logs.sh
```

### Permission denied

Si le script ne peut pas écrire dans `/var/log/mongodb/` :

```bash
sudo chown -R mongodb:mongodb /var/log/mongodb/
sudo chmod 755 /var/log/mongodb/
```

## Différences avec la version Docker

| Aspect | Docker | Installation native |
|--------|--------|---------------------|
| **Anacron** | Embarqué dans l'image | Installé sur le système |
| **Script** | Dans `/scripts/` du conteneur | Dans `/usr/local/bin/` |
| **Configuration** | `/etc/mongod.conf` copié dans l'image | `/etc/mongod.conf` du système |
| **Permissions** | UID 999 (utilisateur mongodb) | Utilisateur mongodb du système |
| **Logs de rotation** | `/var/log/mongodb/logrotate.log` | `/var/log/mongodb/logrotate.log` |

## Pour aller plus loin

- [Rotation des logs MongoDB (Docker)](mongodb-log-rotation.md) : Version Docker
- [Documentation MongoDB sur la rotation](https://www.mongodb.com/docs/manual/tutorial/rotate-log-files/)
- [Documentation anacron](https://linux.die.net/man/8/anacron)
