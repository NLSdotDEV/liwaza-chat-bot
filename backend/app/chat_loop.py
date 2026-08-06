"""Boucle d'orchestration : LLM + tool use via un client MCP HTTP.

La boucle se connecte à /mcp/ **comme un client MCP**, pas par import direct
des fonctions Python. C'est ce qui rend la couche MCP réellement traversée et
vérifiable (CONTEXT.md §3.2 : le frontend ne contourne pas la couche MCP —
le principe s'applique symétriquement à /chat).

Adaptations au SDK réellement installé (mcp==2.0.0), différent du nom de
fonction et de l'arité attendus par un exemple générique :
- `streamablehttp_client` n'existe pas ; la fonction s'appelle
  `streamable_http_client` et retourne un couple (read, write), pas un
  triplet.
- Les champs des objets retournés par le SDK sont en snake_case
  (`tool.input_schema`, `result.structured_content`, `outcome.is_error`), pas
  en camelCase.
- `/mcp` (sans slash final) renvoie 405 une fois le frontend statique monté
  sur "/" (cf. app/main.py) — l'URL canonique utilisée ici a le slash final.
- Le SDK Groq (API compatible OpenAI) a un `connect timeout` par défaut de 5s
  (`groq._constants.DEFAULT_TIMEOUT`), trop court pour la latence de première
  connexion HTTPS observée dans certains environnements (~15s, même symptôme
  que celui documenté dans worldbank_client.py). Sans l'augmenter, le tout
  premier appel LLM échoue systématiquement avec un timeout de connexion —
  pas un problème de clé ou de l'API Groq.
- Format de tool use compatible OpenAI (pas le format Anthropic) : les tool
  calls arrivent dans `message.tool_calls` (liste), chaque appel a un
  `function.arguments` en JSON *string* à parser ; les résultats repartent en
  messages séparés `{"role": "tool", "tool_call_id": ..., "content": ...}`,
  pas en blocs `tool_result` imbriqués dans un message `user`.
"""

from __future__ import annotations

import json
import os
from typing import Any

import groq
import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

MODEL = os.environ["GROQ_MODEL"]  # identifiant vérifié sur console.groq.com/docs/models avant usage
# Le port par défaut suit $PORT (pas 8000 en dur) : sur un PaaS comme Render,
# $PORT est assigné dynamiquement, et c'est sur ce port que main.py écoute
# réellement — un défaut figé à 8000 casserait l'auto-appel MCP en prod.
MCP_URL = os.environ.get("MCP_URL", f"http://127.0.0.1:{os.environ.get('PORT', 8000)}/mcp/")
MAX_TURNS = 6

SYSTEM_PROMPT = """Tu es un assistant de données publiques sur la Côte d'Ivoire.

Tu réponds en français ou en anglais, selon la langue de l'utilisateur.

Règles :
- Ne jamais inventer un code d'indicateur : passer par search_indicators.
- Toujours citer l'année de la donnée et l'unité.
- Si les données manquent, le dire ; ne pas estimer.
- Rester concis : un chiffre, son année, une phrase de contexte.
"""

_llm = groq.AsyncGroq(timeout=httpx.Timeout(connect=20.0, read=120.0, write=30.0, pool=5.0))


def _to_groq_tools(mcp_tools) -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description or "",
                "parameters": t.input_schema,
            },
        }
        for t in mcp_tools
    ]


async def run_chat(messages: list[dict[str, Any]]) -> dict[str, Any]:
    """Exécute la boucle jusqu'à la réponse finale.

    `messages` est au format compatible OpenAI (déjà résolu par l'appelant à
    partir de l'historique + du nouveau message utilisateur), sans le message
    système — celui-ci est injecté ici à chaque appel plutôt que stocké dans
    l'historique, pour éviter de le dupliquer à chaque tour. Retourne
    {"reply", "trace", "history"} — `history` (les messages mis à jour, au
    format JSON pur) doit revenir au tour suivant ; `trace` est la liste des
    outils appelés, affichée dans l'UI comme preuve d'exécution réelle.
    """
    trace: list[dict[str, Any]] = []

    async with streamable_http_client(MCP_URL) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = _to_groq_tools((await session.list_tools()).tools)

            for _ in range(MAX_TURNS):
                response = await _llm.chat.completions.create(
                    model=MODEL,
                    max_tokens=1500,
                    messages=[{"role": "system", "content": SYSTEM_PROMPT}, *messages],
                    tools=tools,
                )

                choice = response.choices[0]
                # `exclude_none` : la réponse porte des champs propres à Groq
                # (reasoning, executed_tools, annotations...) absents du
                # schéma d'entrée ChatCompletionMessageParam ; les laisser à
                # None évite de les réinjecter dans l'historique renvoyé au
                # tour suivant.
                messages.append(choice.message.model_dump(mode="json", exclude_none=True))

                if choice.finish_reason != "tool_calls":
                    return {"reply": choice.message.content or "", "trace": trace, "history": messages}

                for tool_call in choice.message.tool_calls:
                    tool_input = json.loads(tool_call.function.arguments)
                    outcome = await session.call_tool(tool_call.function.name, tool_input)
                    payload = str(outcome.structured_content) if outcome.structured_content is not None else "".join(
                        c.text for c in outcome.content if hasattr(c, "text")
                    )
                    trace.append({"tool": tool_call.function.name, "input": tool_input, "is_error": outcome.is_error})
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": payload,
                        }
                    )

    return {
        "reply": "Limite de tours atteinte sans réponse finale.",
        "trace": trace,
        "history": messages,
    }
