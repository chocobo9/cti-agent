from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class DomainStringFeatures:
    domain_length: int
    domain_entropy: float
    tld: str


def _shannon_entropy(s: str) -> float:
    if not s:
        return 0.0
    length = len(s)
    freq: dict[str, int] = {}
    for ch in s:
        freq[ch] = freq.get(ch, 0) + 1
    return -sum((count / length) * math.log2(count / length) for count in freq.values())


def _extract_tld(domain: str) -> str:
    parts = domain.rstrip(".").rsplit(".", maxsplit=1)
    return parts[-1] if parts else ""


def compute_domain_string_features(domain: str) -> DomainStringFeatures:
    clean = domain.rstrip(".").lower()
    return DomainStringFeatures(
        domain_length=len(clean),
        domain_entropy=round(_shannon_entropy(clean), 4),
        tld=_extract_tld(clean),
    )
