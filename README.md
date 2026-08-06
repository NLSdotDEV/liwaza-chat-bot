# Tableau de bord Côte d'Ivoire — serveur MCP + chat

Assistant conversationnel sur les indicateurs socio-économiques de la Côte
d'Ivoire (Banque mondiale), interrogeable en français ou en anglais. La
logique métier vit entièrement dans un serveur MCP à 5 outils, exposé
publiquement en HTTP ; le frontend et la boucle de chat en sont clients, ils
ne la contournent jamais.

Spécification technique détaillée :
[`docs/SPEC_MCP_COTE_IVOIRE.md`](docs/SPEC_MCP_COTE_IVOIRE.md). Document
d'architecture : [`docs/architecture.md`](docs/architecture.md).

`docs/` contient la documentation produit. `behind-the-scenes/` contient les
coulisses (usage de l'IA, script de présentation) — voir
[`behind-the-scenes/ai_usage.md`](behind-the-scenes/ai_usage.md). Les notes de
cadrage internes de l'assessment (`CONTEXT.md`) ne sont pas versionnées.

---

## Livrables

| Élément | URL |
|---|---|
| Frontend | *à compléter après déploiement Render* |
| API backend | *à compléter* — `<url>/api/health` |
| Endpoint MCP | *à compléter* — `<url>/mcp/` (slash final requis, cf. §Notes) |
| Dépôt GitHub | *à compléter* |

Le déploiement n'a pas encore été effectué : c'est une action externe
(compte Render du candidat) qui n'a pas pu être exécutée depuis cet
environnement. Tout le reste — code, tests, Docker, CI — est construit et
vérifié.

---

## Architecture en un coup d'œil

```
React (client MCP) → /api/chat (orchestration, détient la clé LLM)
                          ↓ client MCP interne (HTTP)
                      /mcp/ (5 outils, Streamable HTTP)
                          ↓
                  api.worldbank.org (REST/JSON, sans clé)
```

Un seul conteneur en production : FastAPI sert le build React en statique et
monte `/mcp/` dans le même processus. Détails, diagrammes et scalabilité
100 → 100 000 utilisateurs : [`docs/architecture.md`](docs/architecture.md).

---

## Installation locale

Prérequis : Python 3.12+, Node 20+, une clé API Groq.

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # puis renseigner GROQ_API_KEY
uvicorn app.main:app --reload
```

- `GET http://localhost:8000/api/health` → `{"status": "ok"}`
- `POST http://localhost:8000/api/chat` avec `{"message": "...", "history": []}`
- `http://localhost:8000/mcp/` : brancher [MCP Inspector](https://github.com/modelcontextprotocol/inspector)
  (`npx @modelcontextprotocol/inspector`) dessus pour lister et exécuter les 5
  outils indépendamment du chat.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Sert sur `http://localhost:5173`, avec un proxy Vite vers `http://127.0.0.1:8000`
pour tout `/api/*` (évite d'avoir à ouvrir CORS sur le backend pour le confort
du dev local — cf. `frontend/vite.config.js`).

---

## Docker

### Image unique (production)

Le `Dockerfile` est multi-stage (build Node du frontend, puis image Python
qui sert le résultat en statique) et vit dans `backend/`, mais **le contexte
de build doit être la racine du repo** — il référence `frontend/` :

```bash
docker build -f backend/Dockerfile -t ci-dashboard .
docker run -p 8000:8000 --env-file backend/.env ci-dashboard
```

### docker-compose (dev, 2 services séparés avec hot-reload)

```bash
docker compose up -d
```

`backend` sur `:8000` (rechargement à chaud sur `backend/app`), `frontend` sur
`:5173` (serveur de dev Vite). Le frontend proxy vers le backend par son nom
de service Docker (`BACKEND_URL=http://backend:8000`), pas `127.0.0.1` — les
deux tournent dans des conteneurs séparés sur le réseau compose.

---

## Variables d'environnement

| Variable | Obligatoire | Défaut | Notes |
|---|---|---|---|
| `GROQ_API_KEY` | oui | — | jamais commitée ; absente → `/api/chat` répond une erreur explicite, ne plante pas silencieusement |
| `GROQ_MODEL` | oui | — | volontairement sans valeur par défaut : l'app refuse de démarrer plutôt que d'utiliser un modèle non choisi explicitement (`openai/gpt-oss-120b` dans `.env.example` — testé plus fiable pour le tool use que `llama-3.3-70b-versatile`, qui produit parfois des tool calls mal formés) |
| `MCP_URL` | non | `http://127.0.0.1:8000/mcp/` | le backend s'appelle lui-même comme client MCP ; slash final obligatoire (cf. Notes) |
| `PORT` | non | `8000` | injecté par la plupart des PaaS (Render, Railway, Fly.io) |

`backend/.env.example` liste ces clés avec des valeurs vides/par défaut à
copier vers `.env` (jamais commité, cf. `.gitignore`).

---

## Tests

```bash
cd backend && pytest -v
```

4 tests, ciblés sur `app/worldbank_client.py` — la couche qui parse une API
externe, donc la plus exposée à un changement de comportement hors de notre
contrôle. Voir la section suivante pour ce qui n'est pas testé et pourquoi.

Job CI équivalent : `.github/workflows/ci.yml` (3 jobs — `backend` : pytest,
`frontend` : build Vite, `docker` : build de l'image complète).

---

## Stratégie de test — ce qui est testé, ce qui ne l'est pas, et pourquoi

**Testé** : le parsing des réponses `api.worldbank.org` (`app/worldbank_client.py`) —
forme `[metadata, data]`, forme d'erreur `{"message": [...]}` renvoyée avec un
HTTP 200 (donc indétectable sans lire le corps), `data: null`, et
l'extraction de l'unité depuis le nom de l'indicateur (`split_name_and_unit`).
C'est la couche qui a le plus de chances de casser silencieusement — une API
externe change son comportement sans prévenir, notre code non.

**Pas testé, délibérément** :
- **Le frontend.** Aucun framework de test composant configuré. Coût
  d'installation et de maintenance (Vitest + Testing Library) disproportionné
  au périmètre d'une UI de 90 lignes ; le risque réel (rendu cassé, appel
  réseau mal formé) est couvert par la vérification manuelle en Docker plutôt
  que par des assertions automatisées.
- **La boucle de tool-use LLM (`app/chat_loop.py`).** Non déterministe par
  nature (le modèle décide quels outils appeler et dans quel ordre), coûteuse
  à tester (chaque run consomme des tokens réels), et faible retour sur
  investissement à ce périmètre : un test qui épingle une sortie de modèle
  précise casse au moindre changement de comportement du modèle, sans avoir
  détecté un vrai bug. Le chemin *mécanique* de cette boucle (connexion MCP,
  sérialisation JSON de l'historique, gestion d'erreur) a en revanche été
  vérifié manuellement de bout en bout avec un vrai client MCP (cf. historique
  de la session de build).
- **Les 5 outils MCP eux-mêmes en tant que tests automatisés.** Vérifiés
  manuellement contre l'API réelle (curl + client MCP officiel) plutôt
  qu'avec des mocks, pour éviter de tester une hypothèse sur l'API plutôt que
  l'API — mais pas intégrés en suite pytest automatisée, faute de temps.
  Trace de ces vérifications manuelles : `docs/SPEC_MCP_COTE_IVOIRE.md` §5.1.

---

## Hypothèses et arbitrages

Résumé — historique complet et raisonnement dans
[`docs/architecture.md`](docs/architecture.md).

- **Source de données : Banque mondiale, pas une administration ivoirienne.**
  Les trois exemples cités par l'énoncé (FNE, DGI, GUCE) sont tous verrouillés
  derrière un enrôlement d'entreprise (NCC réel exigé, vérifié empiriquement
  par un essai d'inscription). data.gouv.ci reste un candidat pour une couche
  complémentaire, non vérifié à ce stade.
- **Cache in-process (dict + TTL), pas Redis.** Suffisant à un réplica.
  Incohérent dès plusieurs instances — limite assumée, pas masquée.
- **`get_latest_value` et `compare_countries` partagent une seule fonction
  côté client** (`fetch_latest`, paramétrée par une liste de 1 ou N codes
  pays) plutôt que du code dupliqué qui aurait dérivé au fil des correctifs.
- **Historique de conversation renvoyé au frontend à chaque tour**, pas géré
  côté serveur (pas de session ni de base de données) : plus simple à
  déployer et scaler (le backend reste sans état), au prix de rejouer
  l'historique complet à chaque appel — acceptable au volume attendu.

---

## Captures d'écran

Non incluses dans ce document : produites en environnement sans navigateur
pilotable pour capturer l'UI réellement rendue. À ajouter après un test manuel
dans un vrai navigateur (prévu avant la vidéo).

---

## Améliorations futures

- Couche data.gouv.ci en complément de la Banque mondiale, si l'accès sans
  clé se confirme.
- Cache Redis partagé dès un déploiement à plusieurs réplicas.
- Suite de tests composants frontend si l'UI grandit au-delà de l'écran de
  chat actuel.
- Bascule vers un modèle plus petit (Haiku) sur les tours de conversation
  simples pour réduire le coût, si le volume augmente — cf.
  `docs/ai_strategy.md`.

---

## Notes techniques

**Pourquoi `/mcp/` avec un slash final, partout** (code, `.env.example`,
cette doc) : une fois le frontend statique monté sur `/` dans `main.py`, la
redirection HTTP automatique de `/mcp` (sans slash) vers `/mcp/` se met à
répondre 405 côté client plutôt que de rediriger — constaté empiriquement,
cause exacte non creusée faute de temps. Utiliser directement l'URL avec
slash final contourne le problème et est de toute façon plus robuste : certains
proxys de PaaS gèrent mal les redirections.

**Divulgation de l'usage de l'IA** : voir
[`behind-the-scenes/ai_usage.md`](behind-the-scenes/ai_usage.md).
