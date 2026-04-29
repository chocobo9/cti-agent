from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class IngestReport:
    success: int = 0
    failures: list[tuple[str, str]] = field(default_factory=list)
    skipped: int = 0
    duration_seconds: float = 0.0
    # Per-domain partial enrichment errors propagated from Session B (non-blocking).
    partial_errors: list[tuple[str, dict[str, str]]] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.success + len(self.failures) + self.skipped

    @property
    def failure_rate(self) -> float:
        return len(self.failures) / self.total if self.total > 0 else 0.0

    def merge(self, other: "IngestReport") -> "IngestReport":
        return IngestReport(
            success=self.success + other.success,
            failures=[*self.failures, *other.failures],
            skipped=self.skipped + other.skipped,
            duration_seconds=self.duration_seconds + other.duration_seconds,
            partial_errors=[*self.partial_errors, *other.partial_errors],
        )
