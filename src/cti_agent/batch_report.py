"""Batch pipeline summary report.

After a batch run completes, BatchReport aggregates:
- Domain-level counts: fully successful / partially successful / completely failed
- Per-source stats: has_data / no_data / errored / skipped
- Neo4j ingestion results (success/failure counts)
- Total wall-clock duration

Usage:
    report = BatchReport.from_results(enrichments, ingest_report, duration, sources)
    report.print_summary()   # logs a human-readable table
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable

from cti_agent.enrichment.config import ALL_SOURCES, SOURCE_ERROR_KEYS, SOURCE_LABELS
from cti_agent.enrichment.models import DomainEnrichment
from cti_agent.ingestion.report import IngestReport

logger = logging.getLogger(__name__)

_HAS_DATA_CHECKS: dict[str, Callable[[DomainEnrichment], bool]] = {
    "crtsh": lambda e: bool(e.certificates),
    "jarm": lambda e: e.jarm_hash is not None,
    "favicon": lambda e: e.favicon_hash is not None,
    "pdns": lambda e: bool(e.passive_dns),
    "rdap": lambda e: e.creation_date is not None or e.registrar is not None,
    "geoip": lambda e: any(g.asn_number is not None or g.country is not None for g in e.geoip),
}


@dataclass
class SourceStats:
    has_data: int = 0
    no_data: int = 0
    errored: int = 0
    skipped: bool = False


@dataclass
class BatchReport:
    total_domains: int = 0
    fully_successful: int = 0
    partially_successful: int = 0
    completely_failed: int = 0
    source_stats: dict[str, SourceStats] = field(default_factory=dict)
    ingestion_report: IngestReport = field(default_factory=IngestReport)
    duration_seconds: float = 0.0

    @classmethod
    def from_results(
        cls,
        enrichments: list[DomainEnrichment],
        ingest_report: IngestReport,
        duration_seconds: float,
        sources: frozenset[str] | None = None,
    ) -> BatchReport:
        enabled = sources if sources is not None else ALL_SOURCES
        total = len(enrichments)
        fully_ok = 0
        partial = 0
        failed = 0

        stats: dict[str, SourceStats] = {}
        for src in ALL_SOURCES:
            stats[src] = SourceStats(skipped=src not in enabled)

        for e in enrichments:
            error_count = len(e.errors)
            if error_count == 0:
                fully_ok += 1
            elif error_count >= len(enabled):
                failed += 1
            else:
                partial += 1

            for src in ALL_SOURCES:
                s = stats[src]
                if s.skipped:
                    continue
                error_key = SOURCE_ERROR_KEYS[src]
                if error_key in e.errors:
                    s.errored += 1
                elif _HAS_DATA_CHECKS[src](e):
                    s.has_data += 1
                else:
                    s.no_data += 1

        return cls(
            total_domains=total,
            fully_successful=fully_ok,
            partially_successful=partial,
            completely_failed=failed,
            source_stats=stats,
            ingestion_report=ingest_report,
            duration_seconds=duration_seconds,
        )

    def print_summary(self) -> None:
        lines = [
            "",
            "=" * 60,
            "BATCH PIPELINE SUMMARY",
            "=" * 60,
            f"Total domains:          {self.total_domains}",
            f"Fully successful:       {self.fully_successful}",
            f"Partially successful:   {self.partially_successful}",
            f"Completely failed:      {self.completely_failed}",
            "",
            "Source results (data / empty / errors):",
        ]
        for src in sorted(ALL_SOURCES):
            label = SOURCE_LABELS.get(src, src)
            s = self.source_stats.get(src)
            if s is None or s.skipped:
                lines.append(f"  {label:<12s}  skipped")
            else:
                lines.append(
                    f"  {label:<12s}  {s.has_data:>4} data  {s.no_data:>4} empty  {s.errored:>4} err"
                )
        lines.extend([
            "",
            f"Neo4j ingested:         {self.ingestion_report.success}",
            f"Neo4j failures:         {len(self.ingestion_report.failures)}",
            f"Duration:               {self.duration_seconds:.1f}s",
            "=" * 60,
        ])
        for line in lines:
            logger.info(line)
