from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime
from typing import Any, Iterator, Protocol, runtime_checkable


@runtime_checkable
class GraphRepository(Protocol):
    """Interface contract for Neo4j graph operations (Session A placeholder).

    Session A will provide the real implementation. This Protocol defines
    the method signatures this ingestion module depends on.
    """

    def merge_domain(
        self,
        *,
        name: str,
        tld: str,
        length: int,
        entropy: float,
        creation_date: date | None,
        registration_length_days: int | None,
        has_mx: bool,
        has_spf: bool,
        has_dmarc: bool,
        dns_record_types: list[str],
        first_seen: datetime,
        last_seen: datetime,
        decay_score: float,
        source: str | None = None,
        actor: str | None = None,
        family: str | None = None,
        shared_infrastructure: bool = False,
    ) -> None: ...

    def merge_certificate(
        self,
        *,
        fingerprint: str,
        issuer: str,
        not_before: datetime,
        not_after: datetime,
        san_list: list[str],
        san_count: int,
    ) -> None: ...

    def merge_has_certificate(self, *, domain: str, cert_fingerprint: str) -> None: ...

    def merge_jarm(self, *, hash: str) -> None: ...

    def merge_has_jarm(
        self, *, domain: str, jarm_hash: str, scan_date: datetime
    ) -> None: ...

    def merge_favicon(self, *, hash: str) -> None: ...

    def merge_has_favicon(
        self, *, domain: str, favicon_hash: str, scan_date: datetime
    ) -> None: ...

    def merge_ip(self, *, address: str, version: int) -> None: ...

    def merge_resolves_to(
        self,
        *,
        domain: str,
        ip: str,
        first_seen: datetime,
        last_seen: datetime,
    ) -> None: ...

    def update_ip_geo(
        self, *, address: str, country: str | None, city: str | None
    ) -> None: ...

    def merge_asn(
        self, *, number: int, name: str | None, country: str | None
    ) -> None: ...

    def merge_belongs_to(self, *, ip: str, asn_number: int) -> None: ...

    def domain_exists(self, name: str) -> bool: ...

    def get_domain(self, name: str) -> dict[str, Any] | None: ...

    def update_domain_timestamps(
        self, *, name: str, last_seen: datetime, decay_score: float
    ) -> None: ...

    def transaction(self) -> Iterator[GraphRepository]: ...

    # --- Cluster/Incident stubs (not called by this module) ---

    def merge_cluster(
        self,
        *,
        cluster_id: int,
        size: int,
        algorithm: str,
        quality_score: float | None = None,
    ) -> None: ...

    def merge_in_cluster(self, *, domain: str, cluster_id: int) -> None: ...

    def merge_incident(
        self,
        *,
        incident_id: str,
        date: date,
        cluster_tag_set: list[int],
        domain_count: int,
    ) -> None: ...

    def merge_part_of(self, *, domain: str, incident_id: str) -> None: ...
