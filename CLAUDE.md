# Project: docker-lmelp

## Description
proposer une archi complete docker mongo, lmelp, back-office-lmelp avec gestion des sauvegardes auto et restore db. Sous forme de docker compose et installable en stackainer sur NAS ou sur PC perso

## La Stack Technique
- **Langage**: Python 3.11
- **Gestionnaire de dépendances**: uv & pyproject.toml
- **Environnement de développement**: VS Code Dev Container
- **Qualité de Code**: pre-commit hooks avec ruff
- **Tests**: pytest
- **Documentation**: MkDocs & mkdocs-material
- **Node.js**: Installé et configuré (version LTS)

## Structure du Projet

```
.
├── .claude/                # Configuration Claude Code
│   └── commands/          # Commandes slash personnalisées
├── .devcontainer/          # Configuration du dev container
├── .github/workflows/      # CI/CD GitHub Actions
├── data/
│   ├── raw/               # Données brutes (non versionnées)
│   └── processed/         # Données traitées
├── docs/                   # Documentation MkDocs
│   ├── index.md           # Page d'accueil de la documentation
│   ├── user/              # Documentation utilisateur
│   ├── dev/               # Documentation développeur
│   └── claude/
│       └── memory/        # Mémoire projet (décisions, apprentissages)
├── notebooks/             # Notebooks Jupyter pour l'exploration
├── src/                   # Code source Python
├── tests/                 # Tests unitaires et d'intégration
├── .gitignore
├── .pre-commit-config.yaml
├── CLAUDE.md              # Ce fichier - Documentation pour Claude Code
└── pyproject.toml         # Configuration du projet et dépendances
```

## Environnement de Développement

### Prérequis
- VS Code avec l'extension Dev Containers
- Docker (version moderne avec Docker Compose V2 intégré)

**Note importante** : Ce projet utilise Docker Compose V2 qui est intégré à Docker. Utiliser `docker compose` (avec espace) et non `docker-compose` (avec tiret).

### Déploiement Portainer

Ce projet est conçu pour être déployé facilement via Portainer (interface graphique Docker).

**⚠️ IMPORTANT - Chemins de volumes dans Portainer** :

Portainer et Docker Compose "pur" résolvent les chemins relatifs différemment :
- **Docker Compose en CLI** : résout `./data/logs` depuis le répertoire où se trouve le `docker-compose.yml`
- **Portainer** : résout `./data/logs` depuis son propre répertoire de travail (`/data/compose/X/`)

**Règle absolue** : Dans Portainer, **toujours utiliser des chemins absolus** pour les variables de volumes dans le fichier `.env`.

```bash
# ❌ MAUVAIS dans Portainer (chemins relatifs)
MONGO_LOG_PATH=./data/mongodb-logs

# ✅ BON dans Portainer (chemins absolus)
MONGO_LOG_PATH=/home/user/docker-lmelp/data/mongodb-logs
MONGO_LOG_PATH=/volume1/docker/lmelp/data/mongodb-logs  # NAS Synology
```

Cette différence de comportement a été identifiée lors du diagnostic d'un problème où MongoDB ne pouvait pas écrire ses logs. Portainer transformait le chemin relatif `./data/mongodb-logs` en `/data/compose/4/data/mongodb-logs` au lieu du chemin attendu.

### Ne jamais imbriquer les volumes de deux services qui se chownent chacun

**Piège découvert lors de l'issue #51** : `docker-compose.yml` montait `MONGO_LOG_PATH`
en sous-dossier de `LOG_PATH` (`./data/logs/mongodb` sous `./data/logs`). Or le
conteneur `lmelp` chowne récursivement et inconditionnellement son propre volume
`LOG_PATH` à chaque démarrage (mécanisme PUID/PGID, issue #105) — ce qui écrasait
silencieusement l'ownership `mongodb` que l'entrypoint mongo venait de poser sur ses
propres logs, cassant les jobs anacron (backup/rotation) qui ne pouvaient plus y écrire.

**Règle** : quand deux services montent chacun un volume et que l'un des deux fait un
`chown -R` sur sa racine de montage (migration PUID/PGID, correction de permissions
héritées, etc.), leurs chemins hôte respectifs ne doivent **jamais** être imbriqués
l'un dans l'autre — même en tant que sous-dossier a priori "logique". Vérifier ce
risque à chaque nouveau volume ajouté à `docker-compose.yml`.

### Méthodologie de debugging : Comprendre AVANT de contourner

**Principe fondamental** : Toujours chercher à **comprendre la cause racine** d'un problème avant d'appliquer une solution de contournement.

**Exemple concret** : Lors du diagnostic du problème MongoDB ci-dessus, plusieurs solutions de contournement étaient possibles :
- ❌ Supprimer le volume de logs MongoDB (contournement sans comprendre)
- ❌ Utiliser `chmod 777` partout (contournement qui masque le problème)
- ✅ **Investiguer pourquoi** MongoDB ne peut pas écrire, découvrir la transformation de chemin par Portainer

**Bénéfices de persister pour comprendre** :
1. **Solution durable** : On corrige la cause, pas le symptôme
2. **Connaissance acquise** : On apprend quelque chose de réutilisable (ici : comportement spécifique de Portainer)
3. **Documentation précise** : On peut expliquer le "pourquoi" aux futurs utilisateurs
4. **Éviter les effets de bord** : Les contournements créent souvent d'autres problèmes

**Workflow de debugging recommandé** :
1. **Observer** : Collecter les symptômes et les logs d'erreur
2. **Hypothèse** : Formuler des hypothèses sur la cause
3. **Investiguer** : Tester les hypothèses méthodiquement (inspecter les mounts, vérifier les permissions, etc.)
4. **Comprendre** : Identifier la cause racine (transformation des chemins par Portainer)
5. **Corriger** : Appliquer la solution appropriée (chemins absolus)
6. **Documenter** : Partager l'apprentissage pour éviter que d'autres rencontrent le même problème

> "Ne cherchez pas trop tôt des solutions de contournement. Bien comprendre le problème AVANT de vouloir le contourner."

Cette approche prend parfois plus de temps initialement, mais économise énormément de temps à long terme et améliore la maîtrise du système.

### Un hostname réseau local peut résoudre différemment selon la machine hôte du conteneur

**Piège découvert lors de l'issue #60** : `PGX_HOST=thinkstationpgx-d7ba.local` (nom mDNS
d'une station du réseau local) fonctionnait depuis le conteneur `lmelp` sur un laptop, mais
échouait depuis ce même conteneur déployé sur un NAS Synology (*"Machine joignable —
thinkstationpgx-d7ba.local ne répond pas sur le port 22"*), alors qu'un `ping` du même nom
depuis le laptop répondait normalement.

**Cause** : la résolution d'un hostname dans un conteneur dépend du serveur DNS hérité de
sa **machine hôte** (`/etc/resolv.conf`), pas d'un mécanisme propre à Docker ou au réseau
bridge du compose file (identique sur les deux machines). Un routeur LAN connaît souvent
les baux DHCP locaux et peut résoudre des noms `.local` ; le DNS configuré dans DSM sur un
NAS est fréquemment un résolveur public qui les ignore. Un nom qui fonctionne sur un poste
de développement n'est donc pas garanti ailleurs — y compris sur un autre déploiement de la
même stack.

**Règle** : toute variable d'environnement pointant vers une machine du réseau local
(`PGX_HOST` et équivalents futurs) doit utiliser une **IP directe**, jamais un nom `.local`
ou un nom court, quelle que soit la machine où fonctionne le déploiement de référence.

### Un service watchdog en sidecar peut corriger des permissions sans builder l'image

**Généralisation du pattern watchdog (issue #61)** : la clé privée SSH dédiée à PGX est
générée par lmelp avec les droits corrects (`600`, confirmé dans le code —
`ssh-keygen` les fixe explicitement, indépendamment de l'umask) mais un mécanisme externe
au conteneur — très probablement la synchronisation ACL Btrfs/Windows ACL de Synology sur
le dossier partagé NAS — a été observé la réinitialisant à `755` après coup (confirmé par
un écart entre `mtime` et `ctime` du fichier : quelque chose modifie ses métadonnées sans
réécrire son contenu).

Contrairement au cas MongoDB (`CHOWN_WATCHDOG_INTERVAL`, issue #51) où le watchdog est
intégré à l'entrypoint d'une image **buildée par ce repo** (`mongodb.Dockerfile`),
`docker-lmelp` ne build pas l'image `lmelp` (pull direct depuis `ghcr.io`) — impossible d'y
injecter un correctif sans remplacer entièrement son entrypoint (fragile, casserait à
chaque mise à jour d'image). Solution : un **service sidecar minimaliste** dans
`docker-compose.yml` (image légère sans build, ex. `alpine`), qui monte le même volume et
boucle la correction (`chmod`/`chown`) à intervalle régulier — reproduit le bénéfice du
watchdog sans dépendre du contrôle de l'image applicative.

**Règle** : quand un mécanisme externe (NAS, ACL, autre service) réinitialise
périodiquement des permissions ou un ownership sur un volume persistant, et qu'on ne
contrôle pas l'image qui écrit dans ce volume, un sidecar watchdog dans
`docker-compose.yml` est le correctif à privilégier — plus robuste qu'une correction
manuelle ponctuelle, sans dépendre de la cause exacte côté NAS.

### Watchtower ne réapplique pas les changements de `docker-compose.yml`

**Deuxième piège du même type** (identifié lors du diagnostic de l'issue #45 : cache Babelio qui
reste vide malgré un volume ajouté) : Watchtower ne fait que surveiller les nouvelles images et
recrée le conteneur avec **la configuration Docker déjà en place** (mêmes volumes, mêmes
variables d'environnement) — il ne relit jamais `docker-compose.yml`. Après avoir ajouté un
volume ou une variable d'environnement dans le compose file, un redéploiement explicite de la
stack est nécessaire (Portainer : "Update the stack" ; CLI : `docker compose up -d
--force-recreate`), sans quoi le conteneur continue de tourner avec l'ancienne configuration.

### Installation
1. Ouvrir le projet dans VS Code
2. Accepter la proposition d'ouvrir dans un Dev Container
3. Le container se construit automatiquement avec toutes les dépendances

### Gestion des Dépendances
Les dépendances sont gérées via `uv` et définies dans `pyproject.toml`:

```bash
# Sync des dépendances
uv sync --active --all-extras

# Tests
uv run --active pytest

# Documentation
uv run --active mkdocs build --strict

# Precommit
pre-commit run --all-files
```

## Qualité du Code

### Pre-commit Hooks
Des hooks pre-commit sont configurés pour maintenir la qualité du code:

```bash
# Installer les hooks
pre-commit install

# Lancer manuellement sur tous les fichiers
pre-commit run --all-files
```

### Linting et Formatage
Le projet utilise `ruff` pour le linting et le formatage.

**Configuration**: Toute la configuration de ruff se trouve dans `pyproject.toml` sous les sections `[tool.ruff]` et `[tool.ruff.lint]`.

```bash
# Vérifier le code
ruff check .

# Formater le code
ruff format .

# Voir la configuration actuelle
ruff check --show-settings
```

## Tests

```bash
# Lancer tous les tests
pytest

# Lancer avec coverage
pytest --cov=src --cov-report=html
```

## Documentation

Ce projet utilise **MkDocs** avec le thème Material pour générer une documentation professionnelle.

### Structure de la documentation

La documentation est organisée en deux sections principales :

- **`docs/user/`** : Documentation pour les **utilisateurs** du projet (installation, utilisation, guides)
- **`docs/dev/`** : Documentation pour les **développeurs** qui contribuent (architecture, contribution, API interne)

### Commandes MkDocs

```bash
# Installer les dépendances de documentation
uv sync --extra docs

# Prévisualiser la documentation localement (http://localhost:8000)
uv run mkdocs serve

# Construire la documentation pour la production
uv run mkdocs build --strict
```

### Déploiement automatique

La documentation est automatiquement construite et déployée sur GitHub Pages via la workflow `.github/workflows/docs.yml` :
- Déclenché à chaque push sur `main` modifiant `docs/` ou `mkdocs.yml`
- Disponible à l'URL : https://castorfou.github.io/docker-lmelp

### Bonnes pratiques de rédaction

Lors de la génération de documentation avec l'IA (Claude Code), suivre ces principes :

#### ✅ À faire

**Décrire l'état actuel** du système :
- Expliquer ce que le système **fait maintenant**
- Fournir des spécifications techniques et des exemples d'utilisation
- Documenter les fonctionnalités telles qu'elles existent
- Utiliser le présent de l'indicatif

#### ❌ À éviter

- **Références historiques** : Éviter "L'issue #X a amélioré..." ou "La version 2.0 a introduit..."
- **Récits d'évolution** : Éviter "Nous avons d'abord implémenté X, puis Y..."
- **Marqueurs temporels** : Éviter "Nouvelle fonctionnalité", "Récemment ajouté", "Bientôt disponible"
- **Métriques de tests** : Ne pas inclure le nombre de tests ou le taux de couverture dans la documentation

#### Exemple de bonne documentation

**❌ Mauvais** :
> "Nouvelle dans l'issue #42 : L'authentification JWT est maintenant disponible. C'est une amélioration majeure par rapport à l'ancienne méthode OAuth que nous utilisions avant."

**✅ Bon** :
> "L'authentification utilise des tokens JWT (JSON Web Tokens) signés avec RS256. Les tokens ont une durée de vie de 24h et peuvent être renouvelés via le refresh token."

#### Où placer les références historiques

Les références aux issues GitHub et l'historique ont leur place dans :
- ✅ Les sections dédiées "Historique" ou "Notes de développement" (en fin de document)
- ✅ Les messages de commit et pull requests
- ✅ Les commentaires de code expliquant des décisions techniques
- ✅ Le fichier `docs/claude/memory/` pour la mémoire contextuelle
- ❌ **Jamais** dans la documentation fonctionnelle principale (user/ ou dev/)

### Organisation docs/user/ vs docs/dev/

**`docs/user/`** - Pour ceux qui **utilisent** le projet :
- Installation et configuration
- Guides d'utilisation et tutoriels
- Cas d'usage et exemples pratiques
- FAQ et dépannage
- API publique (endpoints, fonctions exposées)

**`docs/dev/`** - Pour ceux qui **modifient** le projet :
- Architecture et design patterns
- Configuration de l'environnement de développement
- Guide de contribution et standards de code
- API interne et structure du code
- Processus de développement et workflow

## Conventions de Code

### Commits
Suivre la convention Conventional Commits:
- `feat:` Nouvelle fonctionnalité
- `fix:` Correction de bug
- `docs:` Documentation
- `test:` Ajout/modification de tests
- `chore:` Tâches de maintenance
- `refactor:` Refactoring sans changement de fonctionnalité

Exemple: `feat(data): ajouter pipeline de preprocessing`

### Style Python
- Utiliser les type hints autant que possible
- Documenter les fonctions avec des docstrings
- Respecter PEP 8 (appliqué automatiquement par ruff)
- Maximum 88 caractères par ligne

## Commandes Claude Code

Ce projet inclut des commandes slash pré-configurées pour Claude Code :

### `/fix-issue {numéro}`
Workflow TDD complet pour résoudre une issue GitHub :
- Récupère les détails de l'issue
- Crée une branche depuis l'issue
- Implémente en TDD (tests RED puis code)
- Vérifie qualité (tests, lint, typecheck)
- Met à jour la documentation
- Commit, push et crée la PR

### `/stocke-memoire`
Sauvegarde les apprentissages et décisions importantes dans `docs/claude/memory/` avec horodatage.

#### Organisation du dossier docs/claude/memory/

Ce dossier sert à conserver une trace des décisions importantes, apprentissages et contexte du projet :

- **Format des fichiers** : Markdown (`.md`)
- **Nommage** : `YYMMDD-HHMM-sujet.md` (ex: `251121-1430-architecture-api.md`)
- **Contenu suggéré** :
  - Décisions d'architecture et leur justification
  - Solutions à des problèmes complexes
  - Patterns de code spécifiques au projet
  - Leçons apprises pendant le développement
  - Contexte métier important

Cette mémoire aide Claude Code à maintenir la cohérence du projet au fil du temps.

## Workflow de Développement

### Cycle typique de développement avec Claude Code

Le workflow complet est détaillé dans [.claude/commands/fix-issue.md](.claude/commands/fix-issue.md).

**Résumé du cycle** :

1. **Démarrage** : Créer ou prendre une issue GitHub
2. **Branche** : `gh issue develop {numéro}` crée automatiquement une branche
3. **TDD** :
   - Écrire les tests qui échouent (RED)
   - Implémenter le code minimum pour passer les tests (GREEN)
   - Refactorer si nécessaire (REFACTOR)
4. **Qualité** : Vérifier que tests, linting et typecheck passent
5. **Documentation** : Mettre à jour README.md, CLAUDE.md si nécessaire
6. **Commit** : Message suivant Conventional Commits
7. **CI/CD** : Attendre que la CI passe avant de continuer
8. **PR** : Créer la pull request et demander validation

**Commande rapide** : Utilisez `/fix-issue {numéro}` pour automatiser ce workflow complet.

### Développement exploratoire

Pour l'exploration de données ou le prototypage :

1. Travailler dans `notebooks/` pour l'exploration
2. Une fois le code stabilisé, le déplacer dans `src/`
3. Ajouter des tests dans `tests/`
4. Documenter les insights dans `docs/claude/memory/`

## Commandes Shell Utiles

```bash
# Synchroniser les dépendances
uv pip sync

# Lancer les tests
pytest

# Vérifier la qualité du code
ruff check .

# Formater le code
ruff format .

# Lancer pre-commit hooks
pre-commit run --all-files

# Mettre à jour pre-commit hooks
pre-commit autoupdate

# Prévisualiser la documentation
uv run mkdocs serve

# Construire la documentation
uv run mkdocs build --strict
```

## Ressources
- Dépôt GitHub: https://github.com/castorfou/docker-lmelp
- Documentation du projet: https://castorfou.github.io/docker-lmelp
- Documentation Python: https://docs.python.org/3.11/
- Documentation uv: https://github.com/astral-sh/uv
- Documentation ruff: https://docs.astral.sh/ruff/
- Documentation MkDocs: https://www.mkdocs.org/
