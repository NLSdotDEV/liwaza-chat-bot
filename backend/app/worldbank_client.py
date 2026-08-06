"""Client HTTP vers api.worldbank.org/v2.

Vérifications empiriques (curl, 2026-08-05, cf. docs/SPEC_MCP_COTE_IVOIRE.md §5.1) :
- répond en HTTP 200 sans clé API
- accepte plusieurs codes pays séparés par ';' en un seul appel
- accepte mrv=1 pour la dernière valeur connue (saute les années à null côté serveur)
- renvoie {"message": [...]} (liste d'un seul dict) au lieu du tableau [metadata, data]
  attendu quand un code pays ou indicateur est invalide
- per_page=30000 fonctionne en une page ; total réel = 29544 indicateurs
"""

from __future__ import annotations

import re
from typing import Any

import httpx

from app.cache import cached

BASE_URL = "https://api.worldbank.org/v2"
DEFAULT_COUNTRY = "CIV"
DEFAULT_INDICATOR_PER_PAGE = 30000
CATALOG_TTL_SECONDS = 24 * 60 * 60


class WorldBankError(Exception):
    """Levée quand l'API Banque mondiale renvoie sa forme d'erreur {"message": [...]}."""

    def __init__(self, key: str, value: str):
        self.key = key
        self.value = value
        super().__init__(f"World Bank API error ({key}): {value}")


def build_client() -> httpx.AsyncClient:
    # connect=20s : ce backend a été testé derrière un réseau à latence de
    # connexion élevée et variable (~15s sur une première connexion HTTPS
    # dans certains environnements) ; un timeout court y produit des faux
    # échecs. En hébergement standard, ce budget n'est simplement pas utilisé.
    timeout = httpx.Timeout(connect=20.0, read=20.0, write=10.0, pool=5.0)
    return httpx.AsyncClient(base_url=BASE_URL, timeout=timeout)


def _parse(payload: Any) -> list[dict[str, Any]]:
    """Valide la forme [metadata, data] de l'API World Bank et retourne `data`.

    Lève WorldBankError si le payload est la forme d'erreur observée par
    curl : une liste d'un seul élément {"message": [{"key":..., "value":...}]}.
    """
    if isinstance(payload, list) and len(payload) == 1 and isinstance(payload[0], dict) and "message" in payload[0]:
        first_message = payload[0]["message"][0] if payload[0]["message"] else {}
        raise WorldBankError(
            key=first_message.get("key", "unknown"),
            value=first_message.get("value", "no detail"),
        )
    if not (isinstance(payload, list) and len(payload) == 2):
        raise WorldBankError(key="unexpected_shape", value=str(payload)[:200])
    _, data = payload
    return data or []


async def _get(client: httpx.AsyncClient, path: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    response = await client.get(path, params={**(params or {}), "format": "json"})
    response.raise_for_status()
    return _parse(response.json())


_UNIT_IN_PARENS = re.compile(r"^(.*)\(([^()]+)\)\s*$")


def split_name_and_unit(name: str) -> tuple[str, str | None]:
    """Extrait l'unité du nom d'un indicateur.

    Le champ `unit` de l'API World Bank est vide sur la grande majorité des
    indicateurs ; quand une unité existe, elle est conventionnellement entre
    parenthèses en fin de nom (ex. "GDP (current US$)" -> ("GDP", "current
    US$")). Best-effort : un nom sans parenthèses finales n'a pas d'unité
    détectable, ce n'est pas une erreur.
    """
    match = _UNIT_IN_PARENS.match(name.strip())
    if not match:
        return name.strip(), None
    label, unit = match.groups()
    return label.strip().rstrip(","), unit.strip()


async def fetch_indicator_catalog(client: httpx.AsyncClient) -> list[dict[str, Any]]:
    """Catalogue complet des indicateurs (~29 500), caché longtemps : change rarement."""

    async def _fetch() -> list[dict[str, Any]]:
        raw = await _get(client, "/indicator", {"per_page": DEFAULT_INDICATOR_PER_PAGE})
        return [
            {
                "id": item["id"],
                "name": item.get("name") or "",
                "source_note": item.get("sourceNote") or "",
                "topics": [t.get("value") for t in item.get("topics", []) if t.get("value")],
            }
            for item in raw
        ]

    return await cached("indicator_catalog", _fetch, ttl=CATALOG_TTL_SECONDS)


async def fetch_topics(client: httpx.AsyncClient) -> list[dict[str, Any]]:
    async def _fetch() -> list[dict[str, Any]]:
        raw = await _get(client, "/topic")
        return [{"topic_id": t.get("id"), "name": t.get("value"), "source_note": t.get("sourceNote")} for t in raw]

    return await cached("topics", _fetch, ttl=CATALOG_TTL_SECONDS)


async def fetch_series(
    client: httpx.AsyncClient,
    indicator_id: str,
    country_code: str = DEFAULT_COUNTRY,
    start_year: int | None = None,
    end_year: int | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {"per_page": 1000}
    if start_year is not None and end_year is not None:
        params["date"] = f"{start_year}:{end_year}"

    cache_key = ("series", country_code.upper(), indicator_id, start_year, end_year)

    async def _fetch() -> list[dict[str, Any]]:
        return await _get(client, f"/country/{country_code}/indicator/{indicator_id}", params)

    rows = await cached(cache_key, _fetch)

    if not rows:
        return {
            "country_code": country_code,
            "indicator_id": indicator_id,
            "error": "Aucune donnée retournée : vérifier le code pays et le code indicateur.",
        }

    name, unit = split_name_and_unit(rows[0]["indicator"]["value"])
    points = sorted(({"year": int(r["date"]), "value": r["value"]} for r in rows), key=lambda p: p["year"])
    missing_years = [p["year"] for p in points if p["value"] is None]

    return {
        "country_name": rows[0]["country"]["value"],
        "country_code": rows[0]["countryiso3code"],
        "indicator_id": indicator_id,
        "indicator_name": name,
        "unit": unit,
        "series": [p for p in points if p["value"] is not None],
        "missing_years": missing_years,
        "source": "World Bank Open Data API",
    }


async def fetch_latest(client: httpx.AsyncClient, indicator_id: str, country_codes: list[str]) -> dict[str, Any]:
    """Dernière valeur connue d'un indicateur pour un ou plusieurs pays.

    Fonction unique pour `get_latest_value` (1 code pays) et
    `compare_countries` (2 à 6) : les deux besoins sont la même requête
    World Bank (mrv=1, codes joints par ';'), seule la taille de la liste
    diffère. Éviter la duplication plutôt que d'avoir deux fonctions qui
    dérivent l'une de l'autre au fil des correctifs.
    """
    joined = ";".join(c.lower() for c in country_codes)
    cache_key = ("latest", tuple(c.upper() for c in country_codes), indicator_id)

    async def _fetch() -> list[dict[str, Any]]:
        return await _get(client, f"/country/{joined}/indicator/{indicator_id}", {"mrv": 1})

    rows = await cached(cache_key, _fetch)
    values = [r for r in rows if r["value"] is not None]
    missing_countries = sorted(set(c.upper() for c in country_codes) - {r["countryiso3code"] for r in values})

    if not values:
        return {
            "indicator_id": indicator_id,
            "error": "Aucune valeur récente disponible pour ces pays.",
            "missing_countries": missing_countries,
        }

    name, unit = split_name_and_unit(values[0]["indicator"]["value"])
    entries = sorted(
        (
            {
                "country_code": r["countryiso3code"],
                "country_name": r["country"]["value"],
                "year": int(r["date"]),
                "value": r["value"],
            }
            for r in values
        ),
        key=lambda e: e["value"],
        reverse=True,
    )
    for rank, entry in enumerate(entries, start=1):
        entry["rank"] = rank

    years = {e["year"] for e in entries}

    return {
        "indicator_id": indicator_id,
        "indicator_name": name,
        "unit": unit,
        "values": entries,
        "same_year": len(years) <= 1,
        "missing_countries": missing_countries,
    }
