"""Cache in-process (dict + TTL). Suffisant pour un seul réplica.

Limite assumée (cf. docs/SPEC_MCP_COTE_IVOIRE.md §9) : incohérent dès qu'il y a
plusieurs instances du backend, faute de mémoire partagée. Passage à Redis
nécessaire au premier besoin de scaling horizontal.
"""

import time
from collections.abc import Awaitable, Callable, Hashable
from typing import Any

DEFAULT_TTL_SECONDS = 24 * 60 * 60

_store: dict[Hashable, tuple[float, Any]] = {}


async def cached(key: Hashable, fetch: Callable[[], Awaitable[Any]], ttl: float = DEFAULT_TTL_SECONDS) -> Any:
    now = time.monotonic()
    hit = _store.get(key)
    if hit is not None and now - hit[0] < ttl:
        return hit[1]
    value = await fetch()
    _store[key] = (now, value)
    return value


def clear() -> None:
    _store.clear()
