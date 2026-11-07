#!/bin/bash
# Surveillance hebdomadaire de SERVER-136848 (issue #81).
#
# mongodb.Dockerfile est épinglé sur mongo:8.2 : mongod 8.0.21+, 8.3 et 9.0 refusent
# de démarrer sur les noyaux Ubuntu 7.0 (uname -r = 7.0.0-NN). Ce script, lancé par
# .github/workflows/mongo-kernel-watch.yml sur un runner ubuntu-24.04, teste si
# mongo:8 démarre. Le jour où c'est le cas, il ouvre une seule fois une issue de
# bascule et envoie une notification ntfy.
#
# Codes de sortie :
#   0  mongo:8 toujours bloqué, ou bascule signalée (ou déjà signalée)
#   1  résultat inattendu (pull impossible, message inconnu…) ou échec de l'envoi ntfy
#
# Variables lues : GH_TOKEN (gh), GITHUB_SERVER_URL / GITHUB_REPOSITORY / GITHUB_RUN_ID
# (lien du run), NTFY_SERVER_URL / NTFY_TOPIC (optionnelles).
#
# Le topic ntfy sert de mot de passe : ne jamais l'afficher (pas de set -x, pas d'echo
# de l'URL, sortie de curl jetée).

set -uo pipefail

LABEL="mongo-kernel-watch"
ISSUE_TITLE="Revenir à mongo:8 : SERVER-136848 corrigé"
NTFY_TITLE="docker-lmelp - mongo:8 démarre sur noyau Ubuntu 7.0"
BLOCKED_MESSAGE="Linux kernel versions 6.19"

kernel="$(uname -r)"
echo "Noyau du runner : ${kernel}"

output="$(docker run --rm --pull always --entrypoint mongod mongo:8 --version 2>&1)"
rc=$?

if [ "$rc" -ne 0 ]; then
    if grep -qF "$BLOCKED_MESSAGE" <<<"$output"; then
        echo "mongo:8 refuse toujours ce noyau (SERVER-136848 non corrigé) : rien à faire."
        exit 0
    fi
    echo "::error::Résultat inattendu de mongo:8 (code ${rc}) :"
    echo "$output"
    exit 1
fi

version="$(grep -oE 'db version v[0-9]+\.[0-9]+\.[0-9]+' <<<"$output" | head -n1)"
version="${version#db version }"
major="$(cut -d. -f1 <<<"${version#v}")"
minor="$(cut -d. -f2 <<<"${version#v}")"
if [ -z "$version" ] || [ "$major" -lt 8 ] || { [ "$major" -eq 8 ] && [ "$minor" -lt 3 ]; }; then
    echo "::error::mongo:8 démarre mais sa version n'est pas 8.3 ou plus (${version:-illisible}) :"
    echo "$output"
    exit 1
fi

echo "mongo:8 démarre sur ce noyau : mongod ${version}."

gh label create "$LABEL" --force --color 0E8A16 \
    --description "Alerte du workflow mongo-kernel-watch (SERVER-136848)" >/dev/null

existing="$(gh issue list --state all --limit 1000 --json title,labels \
    --jq "[.[] | select(.title == \"${ISSUE_TITLE}\" or any(.labels[]; .name == \"${LABEL}\"))] | length")"
if [ "${existing:-0}" -gt 0 ]; then
    echo "L'issue « ${ISSUE_TITLE} » existe déjà : ni nouvelle issue, ni notification."
    exit 0
fi

run_url="${GITHUB_SERVER_URL:-https://github.com}/${GITHUB_REPOSITORY:-}/actions/runs/${GITHUB_RUN_ID:-}"

body="$(cat <<EOF
Le workflow \`mongo-kernel-watch\` a détecté que \`mongo:8\` démarre sur un noyau Ubuntu 7.0 :
[SERVER-136848](https://jira.mongodb.org/browse/SERVER-136848) est corrigé dans l'image publiée.

- Version de \`mongod\` détectée : \`${version}\`
- Noyau du runner : \`${kernel}\`
- Run : ${run_url}

## Bascule (PR relue : un \`FROM\` modifié sur \`main\` part en prod via Watchtower)

- [ ] \`mongodb.Dockerfile\` : \`FROM mongo:8.2\` → \`FROM mongo:8\`. Mettre à jour le commentaire.
- [ ] \`tests/test_mongodb_image.py\` : adapter \`KERNEL_CHECK_FREE_MONGO_SERIES\` et \`test_base_image_starts_on_ubuntu_7_kernels\`. Le test ne doit plus imposer 8.2, mais il doit toujours refuser une série bloquée.
- [ ] Docs : encadré « Pourquoi 8.2 » et procédure de \`docs/user/mongodb-upgrade.md\`, \`docs/dev/mongodb-custom-image.md\`, \`docs/user/backup-restore.md\`.
- [ ] \`CLAUDE.md\` : section « \`mongo:8\` ne démarre pas sur un noyau Ubuntu 7.0 ».
- [ ] Supprimer le workflow \`mongo-kernel-watch.yml\` et son script, qui n'ont plus d'objet.
- [ ] Après le merge et le déploiement Watchtower, relever sur le NAS le binaire (attendu : 8.3.x ou plus) et la FCV (attendue : \`8.2\`, inchangée). Le binaire 8.3 ouvre une FCV 8.2 : c'est la configuration que le NAS avait avant la PR #80.
EOF
)"

issue_url="$(gh issue create --title "$ISSUE_TITLE" --label "$LABEL" --body "$body")" || {
    echo "::error::Impossible d'ouvrir l'issue de bascule."
    exit 1
}
echo "Issue ouverte : ${issue_url}"

if [ -z "${NTFY_SERVER_URL:-}" ] || [ -z "${NTFY_TOPIC:-}" ]; then
    echo "::warning::NTFY_SERVER_URL ou NTFY_TOPIC absent : pas de notification ntfy."
    exit 0
fi

if curl -fsS -X POST \
    -H "Title: ${NTFY_TITLE}" \
    -H "Click: ${issue_url}" \
    -H "Priority: default" \
    -d "mongo:8 démarre sur noyau Ubuntu 7.0 : ${issue_url}" \
    "${NTFY_SERVER_URL%/}/${NTFY_TOPIC}" >/dev/null 2>&1; then
    echo "Notification ntfy envoyée."
else
    echo "::error::Échec de l'envoi de la notification ntfy (code $?)."
    exit 1
fi
