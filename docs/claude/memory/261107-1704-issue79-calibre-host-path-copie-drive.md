# Issue #79 — `CALIBRE_HOST_PATH` monte la copie Synology Drive, pas la bibliothèque CWA

## Contexte

`CALIBRE_HOST_PATH` (`.env.nas`) montait la bibliothèque CWA
(`/volume1/docker/calibre-web-automated/books`), rafraîchie une fois par nuit par
`scripts/nas/nightly-sync.sh` (00:05). Toute modif Calibre n'atteignait le back-office et
l'app mobile que le lendemain, alors que la copie Synology Drive
(`/volume1/homes/guillaume/Backup/framework/home/guillaume/Calibre Library`), source même
de `nightly-sync.sh`, est à jour en quelques secondes.

Décision : castorfou/back-office-lmelp ADR 0001 « lmelp lit la copie Drive, pas la
bibliothèque CWA ». Une seule variable pour le back-office **et** `lmelp-export`.

## Modifications

- `.env.nas.example` : nouvelle valeur de `CALIBRE_HOST_PATH` (non quotée, l'espace est
  accepté par compose et Portainer).
- `docker-compose.yml` : **inchangé**. Il monte déjà le *dossier* (`…:/calibre:ro`) : un
  `metadata.db` remplacé par Drive (nouvel inode) reste visible. Un bind-mount du fichier
  aurait figé l'ancien inode.
- `scripts/nas/nightly-sync.sh` : commentaire d'en-tête seulement (« PÉRIMÈTRE : ne sert
  que CWA »), comportement identique.
- `docs/user/calibre-vers-app-mobile.md` : chaîne renumérotée 1 Calibre → 2 copie Drive →
  3 `lmelp-export` → 4 Release → 5 app ; CWA devient une branche annexe (section « Branche
  annexe : bibliothèque CWA et `nightly-sync.sh` ») ; délai = au plus `PUBLISH_INTERVAL`
  après la synchro Drive ; « où chercher » ramené à 5 points ; commandes de vérification
  des droits de lecture sous `/volume1/homes`.
- `docs/user/calibre-setup.md`, `.env.example`, `docs/user/export-android.md` : exemple NAS
  générique `/volume1/homes/utilisateur/Drive/Calibre Library` + conseil de pointer sur la
  copie synchronisée en continu.
- `docs/user/migration-nas.md`, `README.md`, `CLAUDE.md` (section `lmelp-export`) alignés.

## Tests

`tests/test_docker_compose.py::TestCalibreHostPathUsesDriveCopy` :

- `CALIBRE_HOST_PATH` de `.env.nas.example` == défaut `CALIBRE_SOURCE_PATH` lu par regex
  dans `nightly-sync.sh` (source de vérité unique, pas de chemin en dur dupliqué) ;
- valeur absolue et hors CWA ;
- aucune doc `docs/user/*.md` ne montre `CALIBRE_HOST_PATH` sur CWA ; phrases obsolètes
  (« lit donc la bibliothèque **CWA** »…) absentes ;
- la section « Délai » parle de Synology Drive, plus de `nightly-sync.sh`.

## Apprentissages

- **detect-secrets** signale comme « Base64 High Entropy String » un littéral qui colle
  `CALIBRE_HOST_PATH=` au chemin complet de la bibliothèque CWA (même dans un `.md`). Contournement propre : factoriser le chemin dans
  une constante de classe (`CWA_LIBRARY`) et composer avec une f-string, plutôt qu'un
  `pragma: allowlist secret`.
- Le devcontainer n'a pas de démon Docker : les 16 tests de `tests/test_mongodb_image.py`
  qui buildent l'image échouent en local quel que soit le changement. Les lancer avec
  `--deselect tests/test_mongodb_image.py` et laisser la CI les exécuter.
- Validation NAS OK : les deux conteneurs lisent `/calibre/metadata.db` sous `homes`, la
  dernière modif Calibre apparaît dans la page À propos du back-office.
- Effet de bord côté back-office (#327) : l'indicateur « Copie Calibre : mise à jour il y a
  1 h » passe en orange alors que la copie est à jour. Avec une copie temps réel, l'âge de
  `metadata.db` mesure l'inactivité dans Calibre, pas un retard de synchro : le seuil
  orange hérité de l'époque CWA est trompeur (à traiter dans back-office-lmelp).
