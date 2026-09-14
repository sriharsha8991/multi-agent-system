"""Out-of-band artifact store.

Graph state must stay small and JSON-serializable: LangGraph checkpoints it, and the
dev server / Studio serializes it over HTTP — a pandas DataFrame does not survive that
round trip (it comes back as ``None``).

So payloads live here, keyed by artifact id, and **only the digest** goes into graph
state. That is a stronger form of the data-separation rule: the payload can never be
checkpointed, never crosses the wire, and never reaches a prompt. Tools hand ids to each
other; whoever needs the real data asks this store for it.

Process-local by design (the agents run in one process). A distributed deployment would
swap this for Redis/disk behind the same ``put``/``get`` interface.
"""
from __future__ import annotations

import itertools
import threading

from .artifacts import Artifact

_lock = threading.Lock()
_items: dict[str, Artifact] = {}
_counter = itertools.count(1)


def put(artifact: Artifact, prefix: str = "a") -> str:
    """Store a payload and return its artifact id."""
    with _lock:
        art_id = f"{prefix}{next(_counter)}"
        _items[art_id] = artifact
    return art_id


def get(art_id: str) -> Artifact | None:
    return _items.get(art_id)


def ids() -> list[str]:
    return list(_items)


def of_kind(kind: type) -> list[tuple[str, Artifact]]:
    """All (id, artifact) pairs of a given artifact class — e.g. FigureArtifact."""
    return [(k, v) for k, v in _items.items() if isinstance(v, kind)]


def clear() -> None:
    with _lock:
        _items.clear()
