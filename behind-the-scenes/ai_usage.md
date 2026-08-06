# Divulgation de l'usage de l'IA

> Obligatoire (CONTEXT.md §4). Écrit pour être exact plutôt que flatteur —
> l'énoncé pénalise l'inexactitude plus que l'usage de l'IA lui-même, et
> l'usage efficace de l'IA est explicitement le comportement attendu, pas
> toléré.

---

## 1. Outil utilisé

**Claude Code**, avec le modèle **Claude Sonnet 5**, en session interactive
de bout en bout : scaffolding, implémentation backend et frontend, débogage,
tests, Docker, CI, et rédaction de cette documentation elle-même.

## 2. Répartition assisté / manuel

La quasi-totalité du code et de la documentation de ce dépôt a été produite
à travers cette session Claude Code, sur instruction directe du candidat à
chaque étape. Ce n'est pas un projet où l'IA a rempli les détails d'un
squelette écrit à la main — c'est une conversation dirigée, tour par tour,
où le candidat a :

- fixé les contraintes dures (`CONTEXT.md`) et le plan d'exécution détaillé
  (`BUILD.md`) — **ces deux documents ont été fournis déjà rédigés dans la
  conversation** ; leur propre processus de rédaction en amont (assisté par
  IA ou non) n'est pas visible depuis cette session et doit être complété par
  le candidat lui-même s'il a eu lieu ailleurs ;
- tranché les décisions qui n'appartiennent qu'à lui (budget temps 5-7h,
  cible de déploiement Render, "on va faire le build.md d'abord, après je
  génère la clé Claude") ;
- validé ou redirigé chaque étape en la lisant, pas en l'acceptant en bloc.

L'IA a produit : le code (Python, React, Dockerfile, CI), les tests, les
diagrammes, et le texte des quatre documents (`README.md`,
`docs/architecture.md`, `docs/ai_strategy.md`, ce fichier). Le candidat a
produit : le cadrage stratégique (`CONTEXT.md`, `BUILD.md`), les décisions de
budget et de séquencement, et la validation à chaque étape.

## 3. Journal des interactions principales

Résumé fidèle de l'enchaînement réel des échanges de cette session (pas une
reconstruction a posteriori) :

1. **Cadrage initial** — demande d'un plan détaillé et schématisé pour un
   projet "tableau de bord Côte d'Ivoire" en 5 outils MCP sur l'API Banque
   mondiale → production de `docs/SPEC_MCP_COTE_IVOIRE.md`.
2. **Fourniture de `CONTEXT.md`** — document de contexte de l'assessment
   Liwaza (barème, contraintes dures, historique de décision sur le choix de
   source de données) → intégration dans la spec, avec vérifications
   empiriques par `curl` de chaque hypothèse marquée "non vérifiée"
   (connectivité de l'API, appel multi-pays, forme des erreurs, limites de
   pagination, codes d'agrégats régionaux).
3. **"Commence"** — construction du backend (`worldbank_client.py`,
   `cache.py`, `mcp_server.py`, `chat_loop.py`, `main.py`), tests unitaires,
   Dockerfile, avec vérification à chaque fichier via exécution réelle
   (serveur lancé, appels HTTP réels, client MCP officiel), pas seulement
   lecture de code.
4. **"Code le front directement dans ce projet"** — scaffold Vite/React,
   UI de chat minimale, intégration Docker multi-stage, avec découverte et
   correction de deux bugs réels en testant l'intégration (sérialisation de
   l'historique de conversation, redirection `/mcp` cassée par le montage du
   frontend statique).
5. **Fourniture de `BUILD.md`** — plan d'implémentation détaillé avec code
   de référence pour chaque fichier → réécriture complète en conciliant ce
   code avec le SDK `mcp` réellement installé (des noms de fonctions et
   d'attributs diffèrent de ce qu'anticipait le document), plus correction de
   plusieurs bugs supplémentaires trouvés en testant (ordre de
   `load_dotenv()`, type de retour désactivant la sortie structurée MCP,
   perte de l'historique de conversation côté frontend, image Docker Alpine
   incompatible avec le bundler Vite 8).
6. **"On va faire le build.md d'abord... après je génère la clé Claude"** —
   étape courante : documentation (ce fichier et les trois autres), en
   différant tout ce qui exige une clé Anthropic active.

## 4. Vérifié empiriquement vs accepté sur confiance

Discipline appliquée tout au long de la session (héritée de CONTEXT.md §6) :
ne jamais présenter une supposition comme un fait avant test.

**Vérifié par exécution réelle** : connectivité et forme des réponses de
`api.worldbank.org` (curl direct) ; les 5 outils MCP via un vrai client MCP
en HTTP (pas des mocks) ; le rate limiting (429 constaté à la 16ᵉ requête) ;
le build et l'exécution du conteneur Docker combiné ; le flux `docker-compose`
à deux services avec le proxy réseau inter-conteneurs ; l'identifiant du
modèle `claude-sonnet-5` (recherché sur `docs.claude.com`, pas déduit).

**Non vérifié, signalé comme tel** : le round-trip complet de la boucle de
chat avec un vrai appel LLM (tool-use effectif sur plusieurs tours) — aucune
clé Anthropic disponible pendant la construction. Le rendu visuel de l'UI
dans un vrai navigateur — aucun outil de capture d'écran disponible dans cet
environnement. Le choix du modèle Sonnet 5 lui-même repose sur un
raisonnement a priori (`docs/ai_strategy.md` §5), pas sur une mesure de
qualité comparée à Haiku sur ce jeu d'outils précis.

## 5. Limite de cette divulgation

Cette page couvre la session Claude Code visible depuis cet environnement.
Elle ne peut pas attester de ce qui s'est passé avant — en particulier la
rédaction de `CONTEXT.md` et `BUILD.md`, fournis déjà écrits. Si ces
documents ont eux-mêmes été produits avec une assistance IA, c'est au
candidat de le déclarer : cette page ne peut décrire que ce qu'elle a vu.
