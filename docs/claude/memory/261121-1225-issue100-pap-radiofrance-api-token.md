# Issue #100 : clé de l'API Radio France pour le service pap

## Contexte

L'appli pap (castorfou/lmelp-pap) lit l'API Radio France (GraphQL, en-tête `X-Token`)
avec la variable `RADIOFRANCE_API_TOKEN` :

- lmelp-pap#100 : pendant l'écoute, présentateur, critiques et invités de la diffusion ;
- lmelp-pap#81 : description d'un enregistrement mis à disposition de lmelp.

Sans clé, pap fonctionne sans ces données. Les CGU interdisent de conserver les réponses :
pap ne les écrit nulle part.

## Modifications (aucun commit encore au moment de l'écriture, branche
`100-service-pap-passer-la-clé-de-lapi-radio-france-radiofrance_api_token`)

- `docker-compose.yml`, service `pap`, `environment` :
  `RADIOFRANCE_API_TOKEN=${RADIOFRANCE_API_TOKEN:-}` (vide par défaut), avec commentaire.
- `.env.example` et `.env.nas.example`, section « Appli pap » : `RADIOFRANCE_API_TOKEN=`
  vide, commentaire (compte https://developers.radiofrance.fr/, 1 000 requêtes/jour,
  secret jamais commité).
- `docs/user/configuration.md`, section « Variables de l'appli pap » : rôle de la clé,
  comportement sans clé, CGU.
- `tests/test_docker_compose.py::TestPapService` : variable passée à pap et à pap seul,
  exemples `.env*` qui la déclarent **vide** (garde-fou contre une clé commitée), doc.

## Points saillants

- Pas de changement de flux au sens de la règle « Écosystème lmelp » de `CLAUDE.md`
  (service, fréquence, volume, label Watchtower inchangés) : pas d'issue lmelp-mobile.
- Une variable d'environnement n'est pas appliquée par Watchtower : sur le NAS, renseigner
  la clé dans `.env` / variables Portainer puis redéployer (`docker compose up -d pap` ou
  « Update the stack »), et vérifier la date `Created` de `lmelp-pap` et
  `docker exec lmelp-pap printenv RADIOFRANCE_API_TOKEN`.
- Test du critère d'acceptation (panneau d'écoute) prévu sur le NAS après merge.
