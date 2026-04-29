from __future__ import annotations

from datetime import date
from typing import Iterator, TypeVar

T = TypeVar("T")


def chunked(iterable: list[T], size: int) -> Iterator[list[T]]:
    if size <= 0:
        raise ValueError(f"Chunk size must be positive, got {size}")
    for i in range(0, len(iterable), size):
        yield iterable[i: i + size]


def compute_reg_length(creation_date: date | None, expiration_date: date | None) -> int | None:
    if creation_date is None or expiration_date is None:
        return None
    return (expiration_date - creation_date).days


def compute_cert_key(fingerprint: str | None, serial_number: str | None, issuer: str) -> str:
    if fingerprint is not None:
        return fingerprint
    if serial_number is not None:
        return f"{serial_number}:{issuer}"
    raise ValueError("Cannot compute certificate key: no fingerprint and no serial_number")


def detect_ip_version(address: str) -> int:
    return 6 if ":" in address else 4
