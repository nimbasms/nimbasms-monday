# Nimba SMS pour monday.com

App monday permettant d'envoyer des SMS via l'API Nimba SMS, manuellement depuis
une vue de board ou automatiquement via un bloc d'automatisation.

Construite pour : **app publique marketplace**, **infrastructure monday workflows**,
**hebergement monday code**.

---

## Ce qui a change par rapport a la version precedente

| Point | Avant | Maintenant |
|---|---|---|
| Payload d'automatisation | lecture de `payload.phone_number` | lecture de `payload.inputFields`, avec repli sur `inboundFieldValues` |
| Authentification serveur | HMAC maison sur un en-tete `monday-signature` inexistant | verification du JWT `Authorization` (signature, `exp`, `aud`) |
| Identifiants Nimba | stockes dans les settings de l'app, exposes au navigateur | secure storage monday code, un jeu par compte, jamais renvoyes au client |
| Types GraphQL | `Int!` / `[Int]` | `ID!` / `[ID!]` (obligatoire depuis l'API 2023-10) |
| CORS | absent, la vue ne pouvait joindre le backend | origines `*.monday.com` / `*.monday.app` autorisees |
| Liste des expediteurs | endpoint maison appele par le navigateur | Remote Options URL cote serveur + endpoint vue |
| Erreurs d'action | 500 silencieux, rejoue 30 min par monday | severity codes, echec permanent vs temporaire |
| Rapports de livraison | echo du payload recu | statut persiste, puis reporte sur l'element via OAuth |
| Desinstallation | aucune purge | webhook de cycle de vie, effacement des donnees du compte |
| En-tetes de securite | absents | HSTS, nosniff, referrer-policy |
| Tests | aucun | 27 tests |

---

## Architecture

```
.mondaycoderc          runtime Python 3.12 pour monday code
app/
  config.py            variables d'environnement (pydantic-settings)
  security.py          verification des deux types de JWT monday
  storage.py           secure storage monday code (+ repli memoire en dev)
  phone.py             normalisation des numeros (formats guineens inclus)
  errors.py            severity codes renvoyes a monday
  services/
    nimba.py           client async de l'API Nimba SMS
    monday_api.py      client GraphQL monday (ID!, shortLivedToken)
  routers/
    workflows.py       bloc d'action + remote options
    credentials.py     connexion du compte Nimba (admin)
    send.py            envoi manuel depuis la vue
    messages.py        DLR Nimba + consultation d'un envoi
    health.py
frontend/
  index.html app.js    vue de board : composer et envoyer
  settings.html        vue Admin : saisie des identifiants Nimba
  sms.js               compteur de segments GSM-7 / UCS-2
  api.js               client HTTP portant le sessionToken
  config.js            URL du backend, a renseigner au deploiement
tests/
```

### Deux jetons, deux usages

- **JWT d'integration** (en-tete `Authorization`, signe avec le *Signing Secret*) :
  requetes serveur-a-serveur de monday vers le bloc d'action et les remote
  options. Il contient un `shortLivedToken` utilise pour ecrire sur le board.
- **sessionToken** (`monday.get("sessionToken")`, signe avec le *Client Secret*) :
  requetes du navigateur vers le backend depuis les vues.

`security.py` accepte les deux secrets pour le sessionToken. La documentation
monday indique le Client Secret, mais plusieurs apps rapportent une signature
avec le Signing Secret selon le type de vue. **A confirmer sur votre app** et a
restreindre a un seul secret une fois verifie.

---

## Deploiement

Rien de tout ceci ne peut etre fait sans vos identifiants monday : ces etapes
sont a executer par vous.

### 1. Preparer l'app dans le Developer Center

Creez l'app, puis ajoutez ces features :

| Feature | Type | URL a renseigner |
|---|---|---|
| Vue de board | Board View | CDN monday code (client-side) |
| Vue d'administration | Account Settings View | meme CDN, `settings.html` |
| Bloc d'action | Integration / workflows | `https://<backend>/monday/action/send-sms` |

Champs du bloc d'action (onglet *Fields*) :

| Cle | Type | Role |
|---|---|---|
| `messageText` | text | corps du SMS |
| `recipient` | text | numero, ou mapping depuis une colonne |
| `phoneColumnId` | column id | repli si `recipient` est vide |
| `senderName` | remote options | URL : `https://<backend>/monday/field-options/senders` |
| `statusColumnId` | column id | facultatif |
| `statusLabel` | text | facultatif |
| `logToUpdates` | boolean | facultatif |

Scopes OAuth minimaux : `boards:read`, `boards:write`, `updates:write`.

### 2. Deployer le backend

```bash
npm i -g @mondaycom/apps-cli
mapps init                      # colle ton token monday
mapps code:push -a <APP_ID>     # compte ~20 min au premier deploiement
```

Puis les secrets (jamais commites) :

```bash
mapps code:secret -i <APP_ID> -m set -k MONDAY_SIGNING_SECRET -v "<signing secret>"
mapps code:secret -i <APP_ID> -m set -k MONDAY_CLIENT_SECRET  -v "<client secret>"
mapps code:env    -i <APP_ID> -m set -k APP_PUBLIC_URL        -v "https://<url de deploiement>"
mapps code:env    -i <APP_ID> -m set -k NIMBA_BASE_URL        -v "https://api.nimbasms.com"
mapps code:push -a <APP_ID>     # les variables ne prennent effet qu'apres redeploiement
```

En runtime Python, une variable d'environnement n'est chargee qu'au demarrage :
tout changement impose un redeploiement.

### 3. Deployer le frontend

Renseignez d'abord l'URL du backend dans `frontend/config.js`, puis :

```bash
mapps code:push --client-side -d frontend -a <APP_ID>
```

### 4. Verifier

```bash
curl https://<backend>/health          # {"status":"ok"}
mapps code:logs -i <APP_VERSION_ID>
```

### Lancer en local

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env                   # DEV_MODE=true
.venv/bin/uvicorn app.main:app --reload --port 8080
.venv/bin/python -m pytest tests -q
```

`DEV_MODE=true` bascule le stockage en memoire : le secure storage monday code
n'existe que dans le conteneur deploye.

---

## Limites connues

1. **Retour de statut sur le board.** Implemente. `/nimba/dlr` classe le
   statut puis ecrit « Livre » / « Echec » / « En cours » sur l'element, a
   condition que le compte ait autorise l'app en OAuth et que le bloc ait
   renseigne `dlrColumnId`. Sans autorisation OAuth, le statut reste consultable
   via `/api/messages/{id}` mais n'est pas reporte sur le board.
2. **Flux OAuth 2.1.** L'implementation suit le flux historique. monday publie
   un guide de migration vers OAuth 2.1 — a verifier avant soumission.
3. **Severity codes.** Les valeurs de `app/errors.py` doivent etre confrontees a
   la grille officielle avant soumission.
5. **Payload Nimba.** Les chemins et le format d'envoi (`to`, `message`,
   `sender_name`) sont repris de la version precedente du depot. A confirmer
   contre la documentation Nimba en vigueur, notamment le nom du champ de
   callback pour les DLR.
6. **Envoi manuel limite a 500 destinataires** par requete. Au-dela il faut
   passer par la file de monday code (`QueueApi`) pour ne pas depasser le
   timeout d'une minute.

## Avant soumission au marketplace

### Bloquant

- [ ] **Relire et s'approprier le code.** monday refuse les apps « construites
      principalement avec du no-code ou du code genere par IA ». Ce depot a ete
      ecrit avec un assistant : la revue attend un auteur capable de defendre
      chaque choix d'architecture.
- [ ] **Arbitrer le stockage des identifiants Nimba.** L'app les collecte via
      une vue d'administration. monday recommande la *Credentials field* pour
      les workflows, et sa politique securite indique que l'app « ne doit pas
      collecter d'identifiants utilisateur ». Point a confirmer avec l'equipe de
      revue avant de figer l'architecture.
- [ ] **Verifier la non-redondance.** monday n'approuve plus les integrations
      dont l'objet principal duplique une integration existante. Nimba SMS est
      un fournisseur distinct, mais l'argumentaire doit etre explicite.

### Technique

- [ ] Secret du sessionToken confirme, code reduit a ce seul secret
- [ ] Grille des severity codes confrontee a la documentation
- [ ] Format d'envoi Nimba et champ de callback DLR confirmes
- [ ] Scopes OAuth reduits au strict necessaire
- [ ] Scan de securite : `mapps code:report`, plus le scan Burp de la revue
- [ ] Test sur board reel : recette activee, desactivee, app desinstallee

### Legal et listing

- [ ] Politique de confidentialite publiee en HTTPS (obligatoire)
- [ ] Conditions d'utilisation
- [ ] Canal de support actif, SLA du Marketplace Listing Agreement accepte
- [ ] Page de listing : nom, description courte et longue, captures
- [ ] App publiee via l'onglet *Share* pour obtenir le lien `auth.monday.com`
      exige par le formulaire de soumission

La revue se deroule sur un board monday partage : monday cree le board et t'y
invite apres soumission.
