# Issue #60 — PGX_HOST doit être une IP directe, pas un nom `.local`

## Contexte

Sur le NAS, la page PGX de lmelp affichait `🔴 Machine joignable —
thinkstationpgx-d7ba.local ne répond pas sur le port 22`, alors que `PGX_HOST` configuré
avec ce même nom mDNS fonctionnait parfaitement depuis le laptop. L'utilisateur avait
vérifié avec `ping` que le nom résolvait correctement depuis le laptop, mais échouait
(résolvait vers une IP publique sans rapport, `82.65.31.119` via
`*.ascot63.synology.me`) quand la commande `ping` était lancée depuis le shell du NAS
lui-même.

## Diagnostic mené (sans accès direct aux machines de l'utilisateur)

Root cause identifiée par lecture de code plutôt que par test direct (je n'ai accès ni au
laptop ni au NAS de l'utilisateur) : le check de connectivité PGX
(`nbs/pgx.py::wait_for_pgx_reachable` dans le repo `castorfou/lmelp`) utilise
`socket.create_connection((host, port), ...)` — résolution DNS standard du système, sans
mDNS/avahi. Cette résolution dépend du serveur DNS hérité par le conteneur Docker via
`/etc/resolv.conf` de sa **machine hôte**, pas d'un mécanisme propre à Docker ou au réseau
bridge du compose file (`lmelp-network`, identique laptop/NAS dans `docker-compose.yml`).
Hypothèse retenue avec l'utilisateur : le routeur LAN du laptop connaît les baux DHCP
locaux et peut résoudre `.local`, alors que le résolveur DNS configuré dans DSM sur le NAS
ne les connaît généralement pas (souvent un résolveur public).

L'utilisateur avait initialement demandé de comprendre ce mécanisme précis pour le
reproduire sur le NAS (ex: forcer le même DNS via un override `dns:` dans
`docker-compose.yml`) — proposition faite dans le plan initial (voir
`/home/vscode/.claude/plans/shimmying-honking-church.md`, historique de session). Après
discussion, l'utilisateur a tranché pour l'option la plus simple et déjà recommandée par
la doc existante : basculer `PGX_HOST` vers l'IP directe (`192.168.50.151`) plutôt que de
reproduire un mécanisme DNS fragile dépendant du routeur.

## Modifications apportées (commit `aa9b38e`)

Aucun changement de `docker-compose.yml` requis : `PGX_HOST` n'a pas de valeur par défaut
dans les templates (`.env.example`/`.env.nas.example` utilisaient déjà `192.168.x.x` en
exemple). Le fix est purement documentaire, pour éviter que d'autres tombent dans le même
piège :

- `docs/user/configuration.md` (section "Variables PGX") : nouvel encadré
  `!!! warning` expliquant explicitement la cause (DNS hérité de la machine hôte, pas un
  mécanisme Docker) et le cas vécu.
- `.env.nas.example` : commentaire renforcé sur `PGX_HOST` avec référence à l'issue #60.
- `docs/user/migration-nas.md` : nouveau bloc `!!! warning` dans l'arborescence NAS
  (Étape 1) documentant ce cas concret.
- `CLAUDE.md` : nouvelle entrée "piège" généralisant la leçon au-delà de PGX — toute
  variable d'environnement pointant vers une machine du réseau local doit utiliser une IP
  directe, jamais un hostname, car la résolution dépend de la machine hôte du conteneur.

## Ajout complémentaire demandé en cours de session

L'utilisateur a signalé, en relisant `docs/user/migration-nas.md`, qu'il manquait une
étape expliquant comment autoriser la clé SSH PGX générée automatiquement
(`pgx_lmelp_ed25519.pub`) sur la machine PGX elle-même (`authorized_keys`). Ajout d'une
nouvelle **Étape 7 — Autoriser la clé SSH PGX** dans `docs/user/migration-nas.md`,
insérée après le test des containers et avant la config du reverse proxy DSM
(renumérotation des étapes suivantes : 7→8 pour le reverse proxy, 8→9 pour la validation
finale, avec ajout d'un item de checklist PGX dans cette dernière). Décrit les deux
méthodes : page **PGX** de l'interface Streamlit (affiche la clé publique et la commande
exacte), ou lecture directe via `docker exec lmelp-frontoffice cat
/app/keys/pgx_lmelp_ed25519.pub`.

## Point méthodologique

Cette issue illustre un cas où le diagnostic root-cause s'est fait entièrement par lecture
de code (`nbs/pgx.py` du repo `lmelp`, récupéré via `gh api`) plutôt que par test en
conditions réelles, faute d'accès aux machines de production de l'utilisateur — l'échange
avec l'utilisateur (via `AskUserQuestion`) a permis de confirmer l'hypothèse et de trancher
sur la portée du correctif (documentaire seul, pas de reproduction du mécanisme DNS du
laptop) avant implémentation. Voir aussi [[260823-1202-issue58-pgx-transcription-config]]
pour le contexte plus large de l'intégration PGX dans `docker-lmelp`.
