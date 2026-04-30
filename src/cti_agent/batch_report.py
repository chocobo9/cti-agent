"""Batch pipeline summary report.

After a batch run completes, BatchReport aggregates:
- Domain-level counts: fully successful / partially successful / completely failed
- Per-source success rates (crt.sh, JARM, favicon, pDNS, RDAP, GeoIP)
- Neo4j ingestion results (success/failure counts)
- Total wall-clock duration

Usage:
    report = BatchReport.from_results(enrichments, ingest_report, duration)
    report.print_summary()   # logs a human-readable table
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from cti_agent.enrichment.models import DomainEnrichment
from cti_agent.ingestion.report import IngestReport

logger = logging.getLogger(__name__)

SOURCE_KEYS = ["ct_logs", "jarm", "favicon", "passive_dns", "rdap", "geoip"]
SOURCE_LABELS = {
    "ct_logs": "crt.sh",
    "jarm": "JARM",
    "favicon": "Favicon",
    "passive_dns": "pDNS",
    "rdap": "RDAP",
    "geoip": "GeoIP",
}


@dataclass
class BatchReport:
    total_domains: int = 0
    fully_successful: int = 0
    partially_successful: int = 0
    completely_failed: int = 0
    source_success_rates: dict[str, float] = field(default_factory=dict)
    ingestion_report: IngestReport = field(default_factory=IngestReport)
    duration_seconds: float = 0.0

    @classmethod
    def from_results(
        cls,
        enrichments: list[DomainEnrichment],
        ingest_report: IngestReport,
        duration_seconds: float,
    ) -> BatchReport:
        total = len(enrichments)
        source_success = {k: 0 for k in SOURCE_KEYS}
        fully_ok = 0
        partial = 0
        failed = 0

        for e in enrichments:
            error_count = len(e.errors)
            if error_count == 0:
                fully_ok += 1
            elif error_count >= len(SOURCE_KEYS):
                failed += 1
            else:
                partial += 1
            for key in SOURCE_KEYS:
                if key not in e.errors:
                    source_success[key] += 1

        rates = {
            k: (source_success[k] / total if total > 0 else 0.0)
            for k in SOURCE_KEYS
        }

        return cls(
            total_domains=total,
            fully_successful=fully_ok,
            partially_successful=partial,
            completely_failed=failed,
            source_success_rates=rates,
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
            "Source success rates:",
        ]
        for key in SOURCE_KEYS:
            label = SOURCE_LABELS.get(key, key)
            rate = self.source_success_rates.get(key, 0.0)
            lines.append(f"  {label:<12s} {rate:6.1%}")
        lines.extend([
            "",
            f"Neo4j ingested:         {self.ingestion_report.success}",
            f"Neo4j failures:         {len(self.ingestion_report.failures)}",
            f"Duration:               {self.duration_seconds:.1f}s",
            "=" * 60,
        ])
        for line in lines:
            logger.info(line)
