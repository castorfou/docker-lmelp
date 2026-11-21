# Issue #99 : le service pap monte le dossier audios du back-office

## Contexte

lmelp-pap#81 (« Mettre un enregistrement qualifié à disposition de lmelp », décision
lmelp-pap#61) : pap copie un enregistrement **valide** de `/data/audios/<année>/<nom>`
vers le dossier audio du back-office, via un `.part` renommé, sans jamais écraser, puis
écrit une fiche dans `pap_remises`. Contrat de l'image (lmelp-pap PR #99, branche `mvp0`) :
`PAP_AUDIOS_LMELP=/audios-lmelp` par défaut, dossier créé dans l'image, entrypoint qui ne
chowne que `/data`.

## Modifications (branche `99-service-pap-monter-le-dossier-audios-du-back-office`)

- `docker-compose.yml`, service `pap` : volume `${AUDIO_PATH:-./data/audios}:/audios-lmelp`
  (même source que `backend` sur `/app/audios`) et `PAP_AUDIOS_LMELP=/audios-lmelp`
  explicite.
- `docs/user/configuration.md`, section « Variables de l'appli pap » : le montage, la
  copie `<année>/<nom>`, la propriété du dossier (back-office), `PUID`/`PGID` communs.
- `tests/test_docker_compose.py::TestPapService` : les deux volumes de pap, même source
  que le backend, variable d'environnement, `PAP_PATH_HOTE` et `AUDIO_PATH` non imbriqués
  (défauts du compose et deux `.env*.example`), doc.

## Points saillants

- Règle de l'issue #51 appliquée : pap chowne `/data` récursivement, donc `PAP_PATH_HOTE`
  et `AUDIO_PATH` doivent rester frères. Le dossier partagé n'est chowné par personne côté
  pap ; il suffit que backend et pap tournent sous les mêmes `PUID`/`PGID`.
- Aucune nouvelle variable `.env` : `AUDIO_PATH` existait déjà.
- Le montage n'a d'effet qu'avec une image pap issue de lmelp-pap PR #99 ; avant, il est
  inoffensif.
- Vérification sur le NAS après merge : redéployer, contrôler `Created`, puis
  `docker exec -u appuser lmelp-pap sh -c 'ls /audios-lmelp && touch /audios-lmelp/.t && rm /audios-lmelp/.t'`.
