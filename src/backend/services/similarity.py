"""Explainable local near-text similarity for workspace materials."""
import re
from typing import Any

from storage import items as item_repository
from storage.workspace import get_active_connection


ALGORITHM = "token-jaccard-v1"


def _tokens(text: str) -> set[str]:
    lowered = text.lower()
    words = set(re.findall(r"[a-z0-9][a-z0-9_.+-]{1,}", lowered))
    for sequence in re.findall(r"[\u3400-\u9fff]+", lowered):
        words.update(sequence[index:index + 2] for index in range(len(sequence) - 1))
    return words


def find_similar_items(
    item_id: int, *, threshold: float = 0.2, limit: int = 10
) -> list[dict[str, Any]] | None:
    conn = get_active_connection()
    try:
        source = item_repository.get_item(conn, item_id)
        if not source:
            return None
        source_tokens = _tokens(f"{source['title']}\n{source['content_text']}")
        matches = []
        for candidate in item_repository.list_all_except(conn, item_id):
            candidate_tokens = _tokens(f"{candidate['title']}\n{candidate['content_text']}")
            union = source_tokens | candidate_tokens
            score = len(source_tokens & candidate_tokens) / len(union) if union else 0.0
            if score >= threshold:
                shared = sorted(source_tokens & candidate_tokens)[:12]
                matches.append({"item": candidate, "score": round(score, 4), "evidence": {
                    "algorithm": ALGORITHM, "shared_tokens": shared,
                }})
        matches.sort(key=lambda value: (-value["score"], value["item"]["id"]))
        matches = matches[:limit]
        item_repository.replace_similarity_relations(conn, item_id, matches)
        return matches
    finally:
        conn.close()
