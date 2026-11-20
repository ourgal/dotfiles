"""Resolve a user query to a single AniList media entry."""

from __future__ import annotations

from typing import Any

from .media import normalize, titles_of
from .seanime import SeanimeError


class Ambiguous(RuntimeError):
    pass


def resolve_media(client: Any, query: str, pick_index: int | None) -> dict[str, Any]:
    results = client.search_anime(query, per_page=10)
    results = [m for m in results if (m.get("format") or "") != "MUSIC" and not m.get("isAdult")]
    if not results:
        raise SeanimeError(f"AniList has no result for {query!r}")

    if pick_index is not None:
        if not 1 <= pick_index <= len(results):
            raise SeanimeError(f"--pick must be between 1 and {len(results)}")
        return results[pick_index - 1]

    wanted = normalize(query)
    scored: list[tuple[int, float, dict[str, Any]]] = []
    for media in results:
        best = 0
        qwords = wanted.split()
        for title in titles_of(media):
            candidate = normalize(title)
            if not candidate:
                continue
            cwords = candidate.split()
            if candidate == wanted:
                best = max(best, 100)
            elif cwords[: len(qwords)] == qwords or qwords[: len(cwords)] == cwords:
                # word-boundary prefix only: "yani" must not match "YaniSuu"
                ratio = min(len(cwords), len(qwords)) / max(len(cwords), len(qwords))
                best = max(best, 80 + int(10 * ratio))
            else:
                # Loose word overlap is only trusted for longer queries;
                # a one-word query would match unrelated titles ("yani").
                if len(qwords) >= 3:
                    overlap = len(set(qwords) & set(cwords)) / len(qwords)
                    if overlap >= 0.6:
                        best = max(best, int(60 * overlap))
        scored.append((best, float(media.get("meanScore") or 0), media))

    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    top_score, _, top = scored[0]
    if top_score < 60:
        listing = "\n".join(
            f"  {i + 1}. {m['title'].get('romaji')} (id {m['id']}, {m.get('format')}, {m.get('episodes') or '?'} eps)"
            for i, (_s, _ms, m) in enumerate(scored)
        )
        raise Ambiguous(f"no confident match for {query!r}; use --pick N:\n{listing}")
    if len(scored) > 1 and scored[1][0] == top_score:
        listing = "\n".join(
            f"  {i + 1}. {m['title'].get('romaji')} (id {m['id']}, {m.get('format')}, {m.get('episodes') or '?'} eps)"
            for i, (_s, _ms, m) in enumerate(scored)
        )
        raise Ambiguous(f"several equally good matches for {query!r}; use --pick N:\n{listing}")
    return top
