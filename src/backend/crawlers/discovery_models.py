"""Source-neutral normalized records returned by discovery adapters."""
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DiscoveredRecord:
    title: str
    content_text: str
    summary: str
    source_url: str
    source_facts: dict[str, Any]
