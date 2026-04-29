from __future__ import annotations

import time

from cti_agent.graph.repository import GraphRepository
from cti_agent.ingestion.mapper import (
    map_asn_ops,
    map_certificate_ops,
    map_domain_props,
    map_favicon_op,
    map_ip_ops,
    map_jarm_op,
)
from cti_agent.ingestion.models import DomainEnrichment
from cti_agent.ingestion.report import IngestReport
from cti_agent.ingestion.utils import chunked

DEFAULT_BATCH_SIZE = 100


def ingest_domain(enrichment: DomainEnrichment, repo: GraphRepository) -> None:
    props = map_domain_props(enrichment)
    repo.merge_domain(
        name=props.name,
        tld=props.tld,
        length=props.length,
        entropy=props.entropy,
        creation_date=props.creation_date,
        registration_length_days=props.registration_length_days,
        has_mx=props.has_mx,
        has_spf=props.has_spf,
        has_dmarc=props.has_dmarc,
        dns_record_types=props.dns_record_types,
        first_seen=props.first_seen,
        last_seen=props.last_seen,
        decay_score=props.decay_score,
    )
    cert_ops = map_certificate_ops(enrichment)
    for op in cert_ops:
        repo.merge_certificate(
            fingerprint=op.key,
            issuer=op.issuer,
            not_before=op.not_before,
            not_after=op.not_after,
            san_list=op.san_list,
            san_count=op.san_count,
        )
        repo.merge_has_certificate(domain=enrichment.domain, cert_fingerprint=op.key)
        for san_domain in op.san_list:
            if san_domain != enrichment.domain and repo.domain_exists(san_domain):
                repo.merge_has_certificate(domain=san_domain, cert_fingerprint=op.key)
    jarm_op = map_jarm_op(enrichment)
    if jarm_op is not None:
        repo.merge_jarm(hash=jarm_op.hash)
        repo.merge_has_jarm(domain=enrichment.domain, jarm_hash=jarm_op.hash, scan_date=jarm_op.scan_date)
    favicon_op = map_favicon_op(enrichment)
    if favicon_op is not None:
        repo.merge_favicon(hash=favicon_op.hash)
        repo.merge_has_favicon(domain=enrichment.domain, favicon_hash=favicon_op.hash, scan_date=favicon_op.scan_date)
    ip_ops = map_ip_ops(enrichment)
    for op in ip_ops:
        repo.merge_ip(address=op.address, version=op.version)
        repo.merge_resolves_to(domain=enrichment.domain, ip=op.address, first_seen=op.first_seen, last_seen=op.last_seen)
        if op.country is not None or op.city is not None:
            repo.update_ip_geo(address=op.address, country=op.country, city=op.city)
    asn_ops = map_asn_ops(enrichment)
    for op in asn_ops:
        repo.merge_asn(number=op.number, name=op.name, country=op.country)
        for ip_addr in op.ip_addresses:
            repo.merge_belongs_to(ip=ip_addr, asn_number=op.number)


def ingest_batch(enrichments: list[DomainEnrichment], repo: GraphRepository, batch_size: int = DEFAULT_BATCH_SIZE) -> IngestReport:
    report = IngestReport()
    start = time.monotonic()
    for batch in chunked(enrichments, batch_size):
        with repo.transaction() as tx:
            for enrichment in batch:
                try:
                    ingest_domain(enrichment, tx)
                    report.success += 1
                    if enrichment.errors:
                        report.partial_errors.append((enrichment.domain, dict(enrichment.errors)))
                except Exception as exc:
                    report.failures.append((enrichment.domain, str(exc)))
    report.duration_seconds = time.monotonic() - start
    return report


def ingest_domain_incremental(enrichment: DomainEnrichment, repo: GraphRepository) -> None:
    existing = repo.get_domain(enrichment.domain)
    if existing is not None:
        repo.update_domain_timestamps(name=enrichment.domain, last_seen=enrichment.enriched_at, decay_score=1.0)
    ingest_domain(enrichment, repo)
