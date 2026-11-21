# Issue #97 — Service `pap` : `MONGO_URI` et `MONGO_DB`

Contexte : depuis castorfou/lmelp-pap#67 (maturité des enregistrements), l'appli pap range
son travail dans les collections `pap_*` de la base `masque_et_la_plume` (ADR 0004 de
lmelp-pap). Elle lit `MONGO_URI` et `MONGO_DB`. Sans `MONGO_URI`, elle démarre mais sans
maturité, et `POST /api/verifications` répond 503 `MONGO_URI absent` (constaté sur le NAS).

## Modifications

- `docker-compose.yml`, service `pap` : `MONGO_URI=mongodb://mongo:27017` (même hôte que
  `LMELP_MONGO_URI` de `lmelp-export`) et `MONGO_DB=${MONGO_DATABASE:-masque_et_la_plume}`
  (même base que `MONGODB_URL` du backend). Commentaire « Mongo pas encore utilisé »
  retiré, `depends_on: mongo` conservé. Rien à ajouter dans `.env*` : valeurs fixées par
  le compose.
- `docs/user/configuration.md`, section « Variables de l'appli pap » : tableau des deux
  variables, collections `pap_*`, effet de leur absence, redéploiement nécessaire
  (Watchtower ne relit pas le compose).
- `docs/user/migration-nas.md`, étape 9 : case « maturité active »
  (`curl http://<IP du NAS>:8085/api/donnees` → `maturite_active`, bouton « Vérifier les
  URL des intégraux »).
- Tests : `tests/test_docker_compose.py::TestPapService`
  (`test_pap_receives_mongo_uri_of_stack_mongo`, `test_pap_mongo_db_is_backend_database`,
  `test_pap_compose_block_no_longer_says_mongo_unused`,
  `test_configuration_doc_documents_pap_mongo_variables`) et
  `::TestPapNasDocumentation::test_step9_checks_pap_maturity_is_active`.

## Vérification locale (devcontainer)

- Avec l'image à jour : `"maturite_active": true` et `POST /api/verifications` → 200.
  Contrôle sans `MONGO_URI` (`docker run` nu) : 503, `maturite_active` absent.
- L'image `lmelp-pap:latest` en cache datait d'avant lmelp-pap#67 : `/api/donnees` ne
  renvoyait pas la clé malgré les variables présentes. Faire un `docker compose pull pap`
  avant de conclure.
- Pour tester sans gêner le laptop (Mongo local sur 27018, chemins absolus du `.env`) :
  projet séparé `docker compose -p t97` avec `MONGO_PORT`, `PAP_PORT` et chemins de
  volumes surchargés dans l'environnement. Un dossier de logs Mongo neuf, créé par
  l'utilisateur du devcontainer, doit appartenir à `999` sinon `mongod` boucle sur
  `Failed to open /var/log/mongodb/mongod.log` (et pap échoue alors en résolution DNS de
  `mongo`, conteneur absent du réseau pendant les redémarrages).

## Écosystème

pap lit et écrit désormais Mongo : nouveau flux à reporter sur la page Écosystème de
lmelp-mobile (issue dédiée citant la PR).
