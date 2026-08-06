"""FastAPI : monte /mcp/, sert /api/chat, sert le frontend.

`load_dotenv()` doit s'exécuter avant l'import de `chat_loop` : ce module lit
`GROQ_MODEL` au chargement (`os.environ[...]`, sans valeur par défaut,
volontairement — échec rapide si la config manque plutôt qu'un mauvais modèle
silencieux). Un import de chat_loop placé avant load_dotenv() planterait au
démarrage dès que la variable ne vient que du .env.
"""

from __future__ import annotations

import os
import time
from collections import defaultdict, deque
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

import groq  # noqa: E402
from fastapi import FastAPI, HTTPException, Request  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from app.chat_loop import run_chat  # noqa: E402
from app.mcp_server import mcp  # noqa: E402

# /mcp/ (avec le slash final) est le livrable "MCP endpoint URL" (CONTEXT.md
# §3.3 et §4). streamable_http_path="/" fait que le sous-app répond sur sa
# propre racine, montée ensuite sur "/mcp" ci-dessous — le résultat externe
# est exactement /mcp/.
#
# Note vérifiée empiriquement : une fois le frontend statique monté sur "/"
# plus bas, la redirection automatique 307 de /mcp (sans slash) vers /mcp/
# casse (405 côté client). D'où l'usage systématique de l'URL avec slash
# final (ici et dans chat_loop.py / .env.example), plus robuste de toute
# façon face aux proxys de certains PaaS qui gèrent mal les redirections.
mcp_app = mcp.streamable_http_app(streamable_http_path="/")


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with AsyncExitStack() as stack:
        # Le sous-app MCP a son propre lifespan (démarre le
        # StreamableHTTPSessionManager) ; Starlette ne le propage pas
        # automatiquement pour un app monté — sans cet appel explicite,
        # /mcp/ répond mais les sessions ne s'initialisent jamais
        # (constaté en testant sans ce wiring).
        await stack.enter_async_context(mcp_app.router.lifespan_context(mcp_app))
        yield


app = FastAPI(title="CI Dashboard — MCP eGov", lifespan=lifespan)
app.mount("/mcp", mcp_app)

RATE_LIMIT, WINDOW = 15, 3600
_hits: dict[str, deque] = defaultdict(deque)


def _first_leaf(exc: BaseException) -> BaseException:
    """Descend récursivement dans un (Base)ExceptionGroup jusqu'à la première
    exception non-groupe. Le client MCP imbrique ses task groups anyio, donc
    une erreur unique peut arriver enveloppée sur plusieurs niveaux."""
    while isinstance(exc, BaseExceptionGroup):
        exc = exc.exceptions[0]
    return exc


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: list[dict] = Field(default_factory=list, max_length=20)


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/api/chat")
async def chat(req: ChatRequest, request: Request) -> dict:
    # Rate limiting : la clé LLM est personnelle, un déploiement public sans
    # garde-fou peut l'épuiser en quelques minutes (CONTEXT.md §3.4).
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    window = _hits[ip]
    while window and now - window[0] > WINDOW:
        window.popleft()
    if len(window) >= RATE_LIMIT:
        raise HTTPException(429, "Limite de requêtes atteinte. Réessayer plus tard.")
    window.append(now)

    messages = [*req.history, {"role": "user", "content": req.message}]

    # except* (PEP 654) : le client MCP tourne dans des task groups anyio, qui
    # enveloppent toute exception levée à l'intérieur d'un ExceptionGroup —
    # potentiellement imbriqué sur plusieurs niveaux — au moment où elle
    # traverse le `async with` ; un except classique ne la matcherait pas.
    try:
        return await run_chat(messages)
    except* groq.AuthenticationError as eg:
        raise HTTPException(502, "Clé API Groq invalide côté serveur.") from _first_leaf(eg)
    except* groq.APIError as eg:
        exc = _first_leaf(eg)
        raise HTTPException(502, f"Erreur de l'API Groq : {exc.message}") from exc
    except* KeyError as eg:
        exc = _first_leaf(eg)
        raise HTTPException(500, f"Variable d'environnement manquante : {exc}") from exc
    except* Exception as eg:
        exc = _first_leaf(eg)
        raise HTTPException(502, f"Erreur d'orchestration : {exc}") from exc


# Frontend servi en statique — un seul conteneur en production.
_dist = Path(__file__).resolve().parent.parent / "static"
if _dist.exists():
    app.mount("/", StaticFiles(directory=_dist, html=True), name="frontend")
