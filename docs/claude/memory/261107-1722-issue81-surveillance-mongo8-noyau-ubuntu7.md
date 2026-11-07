# Issue #81 — Surveiller SERVER-136848 : alerte quand `mongo:8` démarre sur noyau Ubuntu 7.0

## Contexte

Depuis la PR #80, `mongodb.Dockerfile` est épinglé sur `FROM mongo:8.2` : `mongod` 8.0.21+,
8.3 et 9.0 lisent `uname -r` et refusent les noyaux 6.19 à 7.0.13. Ubuntu affiche toujours
`7.0.0-NN`, donc tous les noyaux Ubuntu 7.0 sont refusés, dont celui des runners GitHub
`ubuntu-24.04` ([SERVER-136848](https://jira.mongodb.org/browse/SERVER-136848), ouvert).
Objectif : ne plus surveiller le ticket à la main.

## Solution

- `.github/workflows/mongo-kernel-watch.yml` : `schedule` lundi 06:00 UTC + `workflow_dispatch`,
  `runs-on: ubuntu-24.04`, permissions `issues: write` / `contents: read`. Le YAML n'a aucune
  logique : un step `uname -r`, un step qui lance le script avec `GH_TOKEN` et les secrets
  `NTFY_SERVER_URL` / `NTFY_TOPIC` (déjà créés dans le dépôt).
- `scripts/check_mongo_kernel_fix.sh` (`set -uo pipefail`, sans `-e` : chaque erreur est gérée) :
  - `docker run --rm --pull always --entrypoint mongod mongo:8 --version` ;
  - code ≠ 0 + `Linux kernel versions 6.19` → toujours bloqué, exit 0 ;
  - code 0 + `db version v8.3`+ → corrigé ;
  - tout le reste (pull KO, message inconnu, version < 8.3) → affiche la sortie, exit 1
    (run rouge = signal) ;
  - corrigé : `gh label create mongo-kernel-watch --force`, puis dédoublonnage par
    `gh issue list --state all --json title,labels --jq` (titre exact **ou** label), puis
    `gh issue create` (version, noyau, lien du run, checklist de bascule), puis ntfy.
- ntfy : `curl -fsS -X POST "$NTFY_SERVER_URL/$NTFY_TOPIC"` avec `Title`, `Click`,
  `Priority: default`. Secrets absents → `::warning::`, issue quand même ouverte, exit 0.
  Échec curl → exit 1 **après** la création de l'issue.
- Le topic ntfy sert de mot de passe : pas de `set -x` (vérifié par test sur les lignes non
  commentées), sortie de curl jetée (`>/dev/null 2>&1`), message d'erreur sans URL.

## Choix de conception

- Tester l'image plutôt que lire Jira : le ticket peut être fermé avant la publication de
  l'image corrigée.
- Ouvrir une issue, pas une PR : une PR créée avec `GITHUB_TOKEN` ne déclenche pas la CI.
  La bascule reste une PR relue, car un `FROM` modifié sur `main` part en prod via Watchtower.

## Tests

`tests/test_mongo_kernel_watch.py` reprend le pattern de stubs PATH de
`tests/test_nightly_sync.py` (`_stub` qui journalise `"$name $*"` dans `$CALLS_LOG`) avec des
faux `docker`, `gh`, `curl`, `uname`. Couvre : bloqué, échec inconnu, version 8.2, corrigé
(8.3/9.0/10.0), issue existante, secrets absents, échec ntfy, topic jamais affiché, et la
structure du workflow. Piège rencontré : le journal des appels contient l'appel curl après
`gh issue create`, donc la tranche « issue » doit s'arrêter à `curl ` pour vérifier que le
topic n'est pas dans l'issue.

## Validation réelle et piège devcontainer (issue #83)

- `gh workflow run` n'est possible qu'une fois le workflow présent sur `main` : test réel du
  dispatch après merge.
- Le script a été lancé pour de vrai dans le devcontainer (noyau hôte `7.0.0-43-generic`) :
  `mongo:8 refuse toujours ce noyau … rien à faire`, exit 0. Suite complète : 177 tests verts.
- Pour y arriver, `dockerd` ne démarrait pas : la feature `docker-in-docker` (ajoutée à la main,
  lock en 2.17.0) choisit `iptables-legacy` au build de l'image, et le noyau hôte 7.0 n'a plus
  de table `nat` legacy (`/tmp/dockerd.log` : *can't initialize iptables table `nat'*).
  Contournement à chaud, perdu au rebuild :
  `sudo update-alternatives --set iptables /usr/sbin/iptables-nft` (idem `ip6tables`), puis
  `sudo nohup dockerd &`. Correctif durable suivi dans l'issue #83 (PyFoundry, `cruft update`,
  `docker_in_docker: "y"` dans le contexte cruft).
- Les 16 tests de `tests/test_mongodb_image.py` qui échouent en local avec *Cannot connect to
  the Docker daemon* viennent de ce piège, pas du code.
