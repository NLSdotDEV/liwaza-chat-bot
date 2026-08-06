# Stratégie IA / LLM — appliquée à ce produit

> Comparaison des modèles Anthropic disponibles, évaluée pour **ce produit
> précis** : une boucle de tool-use courte (jusqu'à 6 tours) sur des données
> publiques, pas un comparatif générique de modèles. Chiffres de tarification
> et identifiants vérifiés sur `docs.claude.com` le 2026-08-05 (pas supposés
> — cf. `CONTEXT.md` §6 sur l'obligation de distinguer vérifié et supposé).

---

## 1. Ce que la charge de travail exige réellement

Chaque tour de conversation :
1. reçoit un message utilisateur + l'historique,
2. décide quels outils MCP appeler (0 à plusieurs, jusqu'à `MAX_TURNS=6`
   allers-retours),
3. lit un résultat structuré (JSON, pas du texte à interpréter en langage
   naturel),
4. produit une réponse courte (quelques phrases, un chiffre, une année).

Ce n'est ni un problème de raisonnement long, ni une tâche créative, ni un
contexte massif à digérer. Le facteur qui domine l'expérience utilisateur
est la **latence perçue** (combien de temps avant la première réponse
visible), pas la profondeur de raisonnement.

---

## 2. Modèles comparés

| | Claude Haiku 4.5 | **Claude Sonnet 5 (retenu)** | Claude Opus 5 | Claude Fable 5 |
|---|---|---|---|---|
| Identifiant API | `claude-haiku-4-5-20251001` | `claude-sonnet-5` | `claude-opus-5` | `claude-fable-5` |
| Prix entrée / sortie (par MTok) | $1 / $5 | $3 / $15 (intro $2 / $10 jusqu'au 31/08/2026) | $5 / $25 | $10 / $50 |
| Latence comparative | la plus rapide | rapide | modérée | plus lente |
| Fenêtre de contexte | 200k tokens | 1M tokens | 1M tokens | 1M tokens |
| Positionnement Anthropic | « le plus rapide, quasi frontière » | « le meilleur compromis vitesse/intelligence » | « codage agentique complexe, entreprise » | « intelligence de nouvelle génération pour agents longs » |

## 3. Grille de décision

| Critère | Poids pour ce produit | Lecture |
|---|---|---|
| **Qualité** | Moyen | La tâche est un choix d'outil + reformulation courte, pas un raisonnement profond. Haiku 4.5 suffirait probablement sur la majorité des tours ; Sonnet 5 offre une marge de fiabilité sur les cas ambigus (ex. distinguer `get_latest_value` de `get_indicator_series` selon la formulation) sans franchir dans la sur-qualification d'Opus/Fable |
| **Coût** | Élevé au volume attendu, faible en absolu | Volume faible (démo/évaluation) : le coût unitaire compte peu dans l'absolu. Mais l'écart Sonnet/Haiku (3× sur l'entrée, 3× sur la sortie) devient significatif si le produit passe en usage réel — d'où le plan de bascule en §4 |
| **Latence** | Élevé | Une boucle de tool-use peut enchaîner plusieurs appels au modèle (jusqu'à 6) avant la réponse finale ; chaque aller-retour ajoute de la latence perçue. Sonnet 5 est documenté « rapide », un cran sous Haiku mais nettement devant Opus/Fable — le bon compromis entre le fait de ne pas être le facteur limitant et une fiabilité de choix d'outil supérieure à Haiku |
| **Confidentialité / RGPD** | Élevé sur le principe, faible en pratique ici | Les données interrogées (indicateurs Banque mondiale) sont publiques par nature — aucune contrainte de confidentialité sur les *données métier*. Reste un point réel : le *texte de la question utilisateur* transite par l'API Anthropic (société américaine). Aucune donnée personnelle n'est censée y figurer dans l'usage prévu (questions sur des indicateurs pays), mais rien n'empêche techniquement un utilisateur d'y saisir une donnée personnelle — non traité spécifiquement dans cette version (pas de filtrage d'entrée), à noter comme limite plutôt qu'à ignorer |
| **Sécurité** | Élevé | Clé API jamais exposée au navigateur (CONTEXT.md §3.4) ; rate limiting sur `/api/chat` pour éviter l'épuisement de la clé. Ce sont des garde-fous d'infrastructure, indépendants du modèle choisi |
| **Auto-hébergement** | Non applicable | Les modèles Claude ne sont pas des poids ouverts : pas d'auto-hébergement possible avec ce fournisseur. Une alternative auto-hébergée (ex. un modèle open-weight sur infrastructure propre) supprimerait la dépendance à un fournisseur externe mais introduirait un coût d'exploitation (GPU, MLOps) sans commune mesure avec le volume de ce produit — non retenu, mais c'est le critère qui justifierait de revisiter ce choix si une contrainte de souveraineté des données apparaissait |

## 4. Décision et plan de bascule

**Retenu : `claude-sonnet-5`**, pour le rapport vitesse/fiabilité sur une
boucle de tool-use courte, avec la tarification introductive ($2/$10 par
MTok jusqu'au 31 août 2026) qui réduit temporairement l'écart de coût avec
Haiku.

**Plan de bascule si le volume augmente** : router les tours de conversation
« simples » (une seule question factuelle, un seul appel d'outil attendu)
vers `claude-haiku-4-5`, et réserver Sonnet 5 aux tours ambigus ou
multi-outils (ex. une comparaison qui enchaîne `search_indicators` puis
`compare_countries`). Ce routage n'est **pas implémenté** dans cette version
— la boucle actuelle utilise un seul modèle fixe pour tous les tours,
configuré par la variable d'environnement `ANTHROPIC_MODEL`, précisément pour
que ce changement futur soit un changement de valeur de variable, pas une
réécriture.

**Non retenus, pourquoi** :
- **Opus 5 / Fable 5** — sur-qualifiés pour une boucle de tool-use courte sur
  des données structurées ; le surcoût (jusqu'à 5× sur Fable) n'achète pas de
  bénéfice mesurable sur cette tâche.
- **Haiku 4.5 par défaut** — envisagé, mais écarté comme choix *par défaut*
  faute d'avoir mesuré empiriquement son taux d'erreur de sélection d'outil
  sur ce jeu de 5 outils avant la deadline. C'est le candidat naturel pour le
  plan de bascule ci-dessus, une fois cette mesure faite.

## 5. Ce qui reste à faire, honnêtement

Aucun test de qualité comparatif (Sonnet vs Haiku sur ce jeu d'outils précis)
n'a été exécuté — ce document est un raisonnement de choix a priori, pas le
résultat d'une évaluation empirique du modèle. À la différence du choix de
source de données (Banque mondiale), vérifié par curl avant d'être retenu, le
choix de modèle n'a pas eu le même niveau de vérification faute de clé API
disponible pendant la construction. À faire dès la clé enregistrée : quelques
dizaines d'échanges réels, en notant les cas où le modèle appelle le mauvais
outil ou invente un code d'indicateur au lieu de passer par
`search_indicators`.
