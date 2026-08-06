"""Serveur MCP : 5 outils au-dessus de l'API World Bank.

Principe de conception : les outils sont pensés pour un agent, pas comme un
proxy 1-pour-1 de l'API. D'où `search_indicators` (le LLM ne connaît pas les
codes) et l'exposition explicite des trous de données (`same_year`,
`missing_years`, `missing_countries`) plutôt que leur masquage.

Adaptation SDK : le paquet `mcp` installé (2.0.0) n'expose plus
`mcp.server.fastmcp.FastMCP` — la classe équivalente est
`mcp.server.MCPServer`, avec la même API `@mcp.tool()` et
`.streamable_http_app()`. Constaté par inspection du paquet installé (cf.
docs/SPEC_MCP_COTE_IVOIRE.md) : le SDK fait foi sur ce point, pas un exemple
de code écrit avant vérification.
"""

from __future__ import annotations

from typing import Annotated, Any

from mcp.server import MCPServer
from pydantic import Field

from app.worldbank_client import (
    DEFAULT_COUNTRY,
    build_client,
    fetch_indicator_catalog,
    fetch_latest,
    fetch_series,
    fetch_topics,
)

mcp = MCPServer("ci-dashboard")
_client = build_client()


@mcp.tool()
async def search_indicators(
    query: Annotated[
        str,
        Field(
            description="Mot-clé en anglais, ex. 'inflation', 'poverty', 'internet'. "
            "Les libellés du catalogue sont en anglais : traduire avant d'appeler."
        ),
    ],
    limit: Annotated[int, Field(ge=1, le=50)] = 10,
) -> dict[str, Any]:
    """Trouve le code d'un indicateur de la Banque mondiale à partir d'un mot-clé.

    À appeler EN PREMIER quand l'utilisateur mentionne un thème sans donner de
    code (« le PIB », « la pauvreté »). Les autres outils exigent un
    `indicator_id` exact — ne jamais l'inventer.
    """
    catalog = await fetch_indicator_catalog(_client)
    needle = query.lower().strip()
    hits = [item for item in catalog if needle in item["name"].lower() or needle in item["source_note"].lower()]
    hits.sort(key=lambda i: needle not in i["name"].lower())  # nom avant description
    return {"query": query, "total_matches": len(hits), "results": hits[:limit]}


@mcp.tool()
async def get_indicator_series(
    indicator_id: Annotated[str, Field(description="Code exact, ex. 'NY.GDP.MKTP.CD'. Obtenu via search_indicators.")],
    country_code: Annotated[str, Field(description="Code ISO3, ex. CIV, GHA, SEN.")] = DEFAULT_COUNTRY,
    start_year: Annotated[int | None, Field(description="Année de début incluse.")] = None,
    end_year: Annotated[int | None, Field(description="Année de fin incluse.")] = None,
) -> dict[str, Any]:
    """Série temporelle d'un indicateur pour un pays (Côte d'Ivoire par défaut).

    Utiliser pour toute question d'évolution ou de tendance. `missing_years`
    liste les années sans donnée : les mentionner si elles sont nombreuses,
    ne pas présenter une série trouée comme continue.
    """
    return await fetch_series(_client, indicator_id, country_code, start_year, end_year)


@mcp.tool()
async def get_latest_value(
    indicator_id: Annotated[str, Field(description="Code exact de l'indicateur.")],
    country_code: Annotated[str, Field(description="Code ISO3.")] = DEFAULT_COUNTRY,
) -> dict[str, Any]:
    """Dernière valeur disponible d'un indicateur pour un pays.

    Préférer cet outil à `get_indicator_series` quand l'utilisateur demande la
    valeur « actuelle ». Les séries accusent souvent 1 à 2 ans de retard :
    toujours citer l'année renvoyée, jamais l'année en cours.
    """
    return await fetch_latest(_client, indicator_id, [country_code])


@mcp.tool()
async def compare_countries(
    indicator_id: Annotated[str, Field(description="Code exact de l'indicateur.")],
    country_codes: Annotated[
        list[str],
        Field(
            description="2 à 6 codes ISO3. Comparateurs régionaux usuels : GHA, SEN, NGA, "
            "et SSF pour l'agrégat Afrique subsaharienne.",
            min_length=2,
            max_length=6,
        ),
    ],
) -> dict[str, Any]:
    """Compare la dernière valeur d'un indicateur entre plusieurs pays.

    Résultat trié par valeur décroissante. Si `same_year` vaut false, les pays
    n'ont pas leur dernière donnée sur la même année : le signaler à
    l'utilisateur plutôt que de comparer implicitement des années différentes.
    `missing_countries` liste les pays sans donnée.
    """
    return await fetch_latest(_client, indicator_id, country_codes)


@mcp.tool()
async def list_topics() -> dict[str, Any]:
    """Liste les grandes thématiques d'indicateurs (santé, éducation, etc.).

    Utile quand l'utilisateur ne sait pas quoi demander, pour lui proposer des
    pistes plutôt que de deviner.
    """
    return {"topics": await fetch_topics(_client)}
