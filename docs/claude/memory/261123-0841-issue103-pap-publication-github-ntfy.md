# Issue #103 : jeton GitHub et ntfy pour la publication de la liste pap

## Contexte

Le bouton **Publier** de l'appli pap (castorfou/lmelp-pap#70, livré dans lmelp-pap#119)
commite les CSV de la liste dans un clone git `/data/depot` (`PAP_DEPOT_GIT`, fixé dans
l'image), les pousse sur `main` de `castorfou/lmelp-pap` (commit
`chore(data): publication depuis le NAS`), puis notifie le résultat sur ntfy
(titres `pap - …`).

## Modifications (branche `103-service-pap-jeton-github-et-ntfy-pour-la-publication-de-la-liste`)

- `docker-compose.yml`, service `pap`, `environment` :
  - `GH_TOKEN=${PAP_GH_TOKEN:-}` : jeton propre à pap, transmis sous le nom `GH_TOKEN`
    attendu par l'image ;
  - `NTFY_SERVER_URL=${NTFY_SERVER_URL:-}`, `NTFY_TOPIC=${NTFY_TOPIC:-}` : même topic que
    `backend` et `lmelp-export`.
  - Pas de nouveau volume : le clone vit dans `PAP_PATH_HOTE/depot`, déjà monté sur `/data`.
- `.env.example` et `.env.nas.example`, section « Appli pap » : `PAP_GH_TOKEN=` vide.
- `docs/user/configuration.md`, section « Variables de l'appli pap » : création du jeton
  fine-grained, clone `/data/depot`, ntfy, ligne de log `publication : …` au démarrage.
- `docs/user/migration-nas.md`, étape 9 : import unique des arbitrages
  (`lmelp-pap arbitrages importer`, console Portainer en `appuser`) et validation de la
  publication.
- `tests/test_docker_compose.py::TestPapService` : pap reçoit `${PAP_GH_TOKEN}` et jamais
  `${GH_TOKEN}`, `PAP_GH_TOKEN` n'est passé à aucun autre service, ntfy identique à
  `backend`, exemples `.env*` vides, doc.

## Points saillants

- **Deux jetons GitHub, un seul nom dans les conteneurs** : `lmelp-export` et `pap`
  lisent tous deux `GH_TOKEN`, mais avec des portées différentes (`lmelp-mobile` contre
  `lmelp-pap`, contents:write chacun). Le compose les distingue côté hôte
  (`GH_TOKEN` contre `PAP_GH_TOKEN`) : un test interdit de passer `${GH_TOKEN}` à pap.
- **Nouveau flux de l'écosystème** (pap → dépôt GitHub lmelp-pap, pap → ntfy, écriture
  des arbitrages dans `pap_*`) : issue
  [castorfou/lmelp-mobile#191](https://github.com/castorfou/lmelp-mobile/issues/191).
- Le `docker.yml` de lmelp-pap ne se déclenche pas sur `data/` : une publication ne
  reconstruit pas l'image et ne réveille pas Watchtower (pas de boucle push → image →
  redéploiement).
- `.env.nas` (gitignoré) n'est qu'une copie locale : sur le NAS, `PAP_GH_TOKEN` se
  renseigne dans les variables de la stack Portainer, puis « Update the stack » (jamais
  « Save settings » seul), et on contrôle la date `Created` de `lmelp-pap`.
- Test NAS prévu après merge (option A), car la stack Portainer suit `main`.
