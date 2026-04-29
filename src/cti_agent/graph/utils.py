from __future__ import annotations

import math
from collections.abc import Iterator, Sequence
from datetime import date
from typing import Any, Final

DECAY_LAMBDA: Final[float] = math.log(2) / 14
DECAY_MAX_AGE_DAYS: Final[int] = 150

SHARED_HOSTING_ASNS: Final[frozenset[int]] = frozenset({
    13335,
    16509,
    15169,
    14061,
    20940,
})


def calculate_decay_score(
    age_days: int | float,
    lambda_: float = DECAY_LAMBDA,
) -> float:
    if age_days < 0:
        return 1.0
    if age_days >= DECAY_MAX_AGE_DAYS:
        return 0.0
    return math.exp(-lambda_ * age_days)


def is_shared_hosting_asn(asn_number: int) -> bool:
    return asn_number in SHARED_HOSTING_ASNS


def calculate_domain_age_days(
    creation_date: date,
    reference_date: date | None = None,
) -> int:
    ref = reference_date or date.today()
    return (ref - creation_date).days


def batch_params(
    items: Sequence[dict[str, Any]],
    batch_size: int = 500,
) -> Iterator[list[dict[str, Any]]]:
    for i in range(0, len(items), batch_size):
        yield list(items[i: i + batch_size])
