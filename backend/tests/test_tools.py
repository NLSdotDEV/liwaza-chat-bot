"""Tests ciblés sur la couche à risque : le parsing des réponses de l'API
World Bank (app/worldbank_client.py). Cf. README.md pour ce qui n'est
délibérément pas testé et pourquoi (frontend, boucle LLM — non déterministe,
coûteuse à tester, faible retour sur investissement à ce périmètre).
"""

from __future__ import annotations

import httpx
import pytest

from app.worldbank_client import WorldBankError, _get, split_name_and_unit


def _client(handler):
    # base_url requis : le code appelle _get() avec des chemins relatifs
    # ("/country/..."), et httpx a besoin d'une base pour les résoudre même
    # avec un transport mocké (sinon urllib échoue sur l'URL relative en
    # tentant d'extraire les cookies de la réponse).
    return httpx.AsyncClient(base_url="https://api.worldbank.org/v2", transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_erreur_metier_sur_http_200():
    """L'API renvoie 200 avec un objet d'erreur : à détecter explicitement."""

    def handler(request):
        return httpx.Response(200, json={"message": [{"id": "120", "value": "Invalid value"}]})

    async with _client(handler) as c:
        with pytest.raises(WorldBankError, match="Invalid value"):
            await _get(c, "/country/XX/indicator/NOPE")


@pytest.mark.asyncio
async def test_rows_null_retourne_liste_vide():
    """Requête valide sans données (data=null) : ne doit pas lever."""

    def handler(request):
        return httpx.Response(200, json=[{"total": 0}, None])

    async with _client(handler) as c:
        assert await _get(c, "/country/CIV/indicator/X") == []


def test_extraction_unite_depuis_le_nom():
    """L'API laisse `unit` vide sur la plupart des indicateurs ; l'unité,
    quand elle existe, est entre parenthèses en fin de nom."""
    assert split_name_and_unit("GDP (current US$)") == ("GDP", "current US$")
    assert split_name_and_unit("Population, total") == ("Population, total", None)


@pytest.mark.asyncio
async def test_fetch_latest_rejoue_la_forme_reelle_observee_par_curl():
    """Rejoue la forme exacte constatée par curl le 2026-08-05 (indicateur
    valide, valeur trouvée), sans appel réseau."""
    from app import cache
    from app.worldbank_client import fetch_latest

    cache.clear()

    sample_response = [
        {"page": 1, "pages": 1, "per_page": 50, "total": 1},
        [
            {
                "indicator": {"id": "NY.GDP.MKTP.CD", "value": "GDP (current US$)"},
                "country": {"id": "CI", "value": "Cote d'Ivoire"},
                "countryiso3code": "CIV",
                "date": "2025",
                "value": 99773555666.1988,
                "unit": "",
            }
        ],
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["mrv"] == "1"
        return httpx.Response(200, json=sample_response)

    async with _client(handler) as c:
        result = await fetch_latest(c, "NY.GDP.MKTP.CD", ["CIV"])

    assert result["values"][0]["value"] == pytest.approx(99773555666.1988)
    assert result["unit"] == "current US$"
    assert result["indicator_name"] == "GDP"
