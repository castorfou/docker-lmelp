# Issue #61 — Watchdog `chmod 600` pour la clé privée PGX exposée en 755

## Contexte

DSM File Station affichait la clé privée `pgx_lmelp_ed25519` (`/docker/lmelp/pgx-keys/`)
avec le privilège `rwxr-xr-x` (755) — une clé privée SSH ne devrait jamais être lisible
par le groupe/others. L'utilisateur a signalé ceci comme une issue de sécurité.

## Diagnostic mené (via échange avec l'utilisateur, pas d'accès direct au NAS)

Étape 1 — vérifier dans le code source réel avant de supposer un bug applicatif : lecture
de `nbs/pgx.py::ensure_pgx_ssh_key` (repo `castorfou/lmelp`, récupéré via `gh api`) :
```python
subprocess.run(["ssh-keygen", "-t", "ed25519", "-f", key_path, "-N", "", "-C", "lmelp-pgx"], ...)
```
`ssh-keygen` fixe explicitement `0600` à la création, **indépendamment de l'umask** (un
umask ne peut que retirer des bits, jamais en ajouter — ne peut donc jamais expliquer un
passage de 600 à 755). L'unique `chown -R $PUID:$PGID ... /app/keys` de l'entrypoint lmelp
(`docker/build/entrypoint.sh`) ne touche que le propriétaire, pas les bits de droits.
Conclusion : **rien dans le code lmelp n'explique le 755** — hypothèse initiale posée :
artefact d'affichage DSM (ACL Btrfs/Windows ACL synchronisée différemment des bits POSIX
réels), à confirmer avant d'agir (méthodologie "comprendre avant de contourner",
[[251123-1622-consolidation-mongodb-anacron]] et les issues #47/#48/#51 déjà catalogées
dans `CLAUDE.md`).

Étape 2 — diagnostic demandé et obtenu de l'utilisateur : `docker exec lmelp-frontoffice
stat /app/keys/pgx_lmelp_ed25519` **depuis le conteneur lui-même** montre `Access:
(0755/-rwxr-xr-x)` — donc pas un artefact d'affichage DSM, un vrai 755 vu par le process
Linux. Détail déterminant : `Modify: 10:14:07` mais `Change: 12:42:22` (~2h30 d'écart).
Seuls `chown`/`chmod`/`rename` mettent à jour `ctime` sans toucher `mtime` — la preuve
qu'un mécanisme **externe au conteneur** a modifié les métadonnées du fichier après sa
création, sans réécrire son contenu. Hypothèse retenue (non vérifiable à 100% sans accès
direct à la config DSM) : synchronisation ACL Synology sur le dossier partagé NAS
réappliquant périodiquement ses propres droits sur les fichiers qu'il contient.

## Décision (validée avec l'utilisateur)

Puisque la cause exacte est externe à `docker-lmelp` **et** à `lmelp` (aucun code dans ces
deux repos ne l'explique, et `docker-lmelp` n'a pas accès à la config DSM), application du
pattern déjà validé dans ce repo pour une classe de problème identique — "un mécanisme
externe réapplique périodiquement de mauvais droits/ownership sur un fichier persistant"
— le **watchdog auto-réparateur**, déjà en place pour MongoDB (`CHOWN_WATCHDOG_INTERVAL`,
issue #51, voir [[260819-0745-issue51-mongo-log-path-overlap]]).

Différence clé avec le cas MongoDB : `docker-lmelp` build sa propre image MongoDB
(`mongodb.Dockerfile`), donc le watchdog original est intégré à son entrypoint. Pour
lmelp, `docker-lmelp` ne fait que `pull` l'image `ghcr.io/castorfou/lmelp:latest` (buildée
depuis le repo `lmelp`) — impossible d'y injecter un correctif sans remplacer entièrement
son entrypoint (fragile, casserait à chaque mise à jour d'image). Solution retenue : un
**service sidecar** dans `docker-compose.yml`, sans build custom (image `alpine:latest`),
qui monte le même volume `PGX_KEYS_PATH` et boucle la correction.

## Modifications apportées (branche `61-security-risque-liée-aux-droits-sur-la-clé-de-connexion`)

- `docker-compose.yml` : nouveau service `pgx-keys-watchdog` — `image: alpine:latest`,
  `container_name: lmelp-pgx-keys-watchdog`, monte
  `${PGX_KEYS_PATH:-./data/pgx-keys}:/keys`, boucle `chmod 600
  /keys/pgx_lmelp_ed25519` + `chmod 644 /keys/pgx_lmelp_ed25519.pub` toutes les
  `${PGX_KEYS_WATCHDOG_INTERVAL:-300}` secondes (défaut identique à
  `CHOWN_WATCHDOG_INTERVAL` de MongoDB pour la cohérence). Tourne en root (pas de
  PUID/PGID nécessaire — chmod sur un fichier appartenant à un autre UID fonctionne en
  root). `2>/dev/null` rend les `chmod` silencieux tant que la clé n'existe pas encore
  (avant la première génération par lmelp).
- `tests/test_docker_compose.py` : nouvelle classe `TestPgxKeysWatchdogConfiguration` (4
  tests TDD, RED confirmé avant l'implémentation puis GREEN) : service existe, monte le
  volume `PGX_KEYS_PATH`, commande contient `chmod 600` sur le bon fichier, restart
  policy `unless-stopped`.
- `.env.example`, `.env.nas.example` : `PGX_KEYS_WATCHDOG_INTERVAL` documenté en
  commentaire (optionnel, défaut suffisant dans la quasi-totalité des cas).
- `docs/user/configuration.md`, `README.md` (tableau des services + structure) :
  documentation du nouveau service.
- `CLAUDE.md` : nouvelle entrée généralisant le pattern "sidecar watchdog quand on ne
  contrôle pas l'image qui écrit dans un volume persistant" — distincte de l'entrée
  MongoDB (watchdog intégré à une image qu'on build soi-même).

## Vérification effectuée sans Docker (daemon indisponible dans ce devcontainer)

Logique `chmod` testée directement via `sh -c` sur une vraie paire de clés générée par
`ssh-keygen` puis forcée à 755 : confirmé que `chmod 600`/`chmod 644` restaurent bien les
droits attendus. `docker compose config --quiet` valide la syntaxe complète du nouveau
service et la résolution de `${PGX_KEYS_WATCHDOG_INTERVAL:-300}`.
