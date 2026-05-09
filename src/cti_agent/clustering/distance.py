"""Pairwise distance functions for the 7 clustering features.

Each function returns a normalized distance in [0, 1] where
0 = identical and 1 = maximally different. Missing/null inputs
return a configurable default (typically 1.0).

Features by dimension:
  Identity   — domain_string, registration_time, tls_certificate
  Config     — jarm, favicon
  Behavior   — passive_dns, asn_geo
"""

from __future__ import annotations

import ipaddress
from datetime import date
from typing import Sequence

from rapidfuzz.distance import Hamming, Levenshtein

from cti_agent.enrichment.models import CertificateInfo, GeoIPInfo, PassiveDNSRecord

FEATURE_NAMES = (
    "domain_string",
    "registration_time",
    "tls_certificate",
    "jarm",
    "favicon",
    "passive_dns",
    "asn_geo",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_sld(domain: str) -> str:
    """Strip TLD to get the second-level domain portion, lowercased."""
    d = domain.lower().rstrip(".")
    parts = d.rsplit(".", maxsplit=1)
    return parts[0] if len(parts) > 1 else d


def _jaccard_distance(set_a: set, set_b: set) -> float:
    """1 - |A & B| / |A | B|.  Returns 1.0 when both sets are empty."""
    if not set_a and not set_b:
        return 1.0
    union = set_a | set_b
    if not union:
        return 1.0
    return 1.0 - len(set_a & set_b) / len(union)


def _extract_valid_ips(records: Sequence[PassiveDNSRecord]) -> set[str]:
    """Filter passive DNS records to only valid, routable IP addresses."""
    ips: set[str] = set()
    for record in records:
        try:
            addr = ipaddress.ip_address(record.ip)
        except ValueError:
            continue
        if not addr.is_unspecified:
            ips.add(record.ip)
    return ips


# ---------------------------------------------------------------------------
# Feature 1: Domain String Distance (Identity)
# ---------------------------------------------------------------------------

def domain_string_distance(domain_a: str, domain_b: str) -> float:
    """Levenshtein distance on the SLD portion, normalized by max length."""
    sld_a = _extract_sld(domain_a)
    sld_b = _extract_sld(domain_b)
    if not sld_a and not sld_b:
        return 0.0
    if not sld_a or not sld_b:
        return 1.0
    max_len = max(len(sld_a), len(sld_b))
    return Levenshtein.distance(sld_a, sld_b) / max_len


# ---------------------------------------------------------------------------
# Feature 2: Registration Time Distance (Identity)
# ---------------------------------------------------------------------------

def registration_time_distance(
    date_a: date | None,
    date_b: date | None,
    max_days: float = 365.0,
    missing_default: float = 1.0,
) -> float:
    """Absolute day difference normalized by *max_days*, capped at 1.0."""
    if date_a is None or date_b is None:
        return missing_default
    day_diff = abs((date_a - date_b).days)
    return min(day_diff / max_days, 1.0)


# ---------------------------------------------------------------------------
# Feature 3: TLS Certificate Distance (Identity)
# ---------------------------------------------------------------------------

def tls_certificate_distance(
    certs_a: Sequence[CertificateInfo],
    certs_b: Sequence[CertificateInfo],
    issuer_weight: float = 0.4,
    san_weight: float = 0.6,
    missing_default: float = 1.0,
) -> float:
    """Best-match composite distance across all cert pairs.

    For each (cert_i, cert_j) pair, computes a weighted combination of
    issuer exact-match distance and SAN-list Jaccard distance.  Returns
    the minimum across all pairs.
    """
    if not certs_a or not certs_b:
        return missing_default
    best = 1.0
    for ca in certs_a:
        for cb in certs_b:
            if ca.fingerprint is not None and cb.fingerprint is not None and ca.fingerprint == cb.fingerprint:
                best = 0.0
                break
            issuer_dist = 0.0 if ca.issuer == cb.issuer else 1.0
            san_dist = _jaccard_distance(set(ca.san_list), set(cb.san_list))
            pair_dist = issuer_weight * issuer_dist + san_weight * san_dist
            if pair_dist < best:
                best = pair_dist
        if best == 0.0:
            break
    return best


# ---------------------------------------------------------------------------
# Feature 4: JARM Distance (Configuration)
# ---------------------------------------------------------------------------

_JARM_LEN = 62
_JARM_ZEROS = "0" * _JARM_LEN


def jarm_distance(
    jarm_a: str | None,
    jarm_b: str | None,
    cipher_weight: float = 0.5,
    ext_weight: float = 0.5,
    missing_default: float = 1.0,
) -> float:
    """Composite: Hamming on first 30 chars + Levenshtein on last 32 chars."""
    if jarm_a is None or jarm_b is None:
        return missing_default
    if jarm_a == _JARM_ZEROS:
        jarm_a = None
    if jarm_b == _JARM_ZEROS:
        jarm_b = None
    if jarm_a is None or jarm_b is None:
        return missing_default
    if len(jarm_a) != _JARM_LEN or len(jarm_b) != _JARM_LEN:
        return missing_default

    cipher_a, ext_a = jarm_a[:30], jarm_a[30:]
    cipher_b, ext_b = jarm_b[:30], jarm_b[30:]
    cipher_dist = Hamming.distance(cipher_a, cipher_b) / 30
    ext_dist = Levenshtein.distance(ext_a, ext_b) / 32
    return cipher_weight * cipher_dist + ext_weight * ext_dist


# ---------------------------------------------------------------------------
# Feature 5: Favicon Distance (Configuration)
# ---------------------------------------------------------------------------

def favicon_distance(
    hash_a: int | None,
    hash_b: int | None,
    missing_default: float = 1.0,
) -> float:
    """Binary exact match: 0 if equal, 1 if different."""
    if hash_a is None or hash_b is None:
        return missing_default
    return 0.0 if hash_a == hash_b else 1.0


# ---------------------------------------------------------------------------
# Feature 6: Passive DNS Distance (Behavior)
# ---------------------------------------------------------------------------

def passive_dns_distance(
    pdns_a: Sequence[PassiveDNSRecord],
    types_a: Sequence[str],
    pdns_b: Sequence[PassiveDNSRecord],
    types_b: Sequence[str],
    ip_weight: float = 1.0,
    type_weight: float = 0.0,
    missing_default: float = 1.0,
) -> float:
    """IP-set Jaccard distance with optional DNS-record-type component.

    Filters passive DNS records to valid IPs before comparison.
    Uses adaptive weighting when one component has no data.
    """
    ips_a = _extract_valid_ips(pdns_a)
    ips_b = _extract_valid_ips(pdns_b)
    set_types_a = set(types_a)
    set_types_b = set(types_b)

    has_ips = bool(ips_a) or bool(ips_b)
    has_types = bool(set_types_a) or bool(set_types_b)

    if not has_ips and not has_types:
        return missing_default

    if has_ips and has_types:
        ip_dist = _jaccard_distance(ips_a, ips_b)
        type_dist = _jaccard_distance(set_types_a, set_types_b)
        return ip_weight * ip_dist + type_weight * type_dist

    if has_ips:
        return _jaccard_distance(ips_a, ips_b)

    return _jaccard_distance(set_types_a, set_types_b)


# ---------------------------------------------------------------------------
# Feature 7: ASN + GeoIP Distance (Behavior)
# ---------------------------------------------------------------------------

def asn_geo_distance(
    geo_a: Sequence[GeoIPInfo],
    geo_b: Sequence[GeoIPInfo],
    asn_weight: float = 0.6,
    country_weight: float = 0.4,
    missing_default: float = 1.0,
) -> float:
    """Composite: ASN-number-set Jaccard (0.6) + country-set Jaccard (0.4).

    Uses adaptive weighting when one component has no data.
    """
    asns_a = {g.asn_number for g in geo_a if g.asn_number is not None}
    asns_b = {g.asn_number for g in geo_b if g.asn_number is not None}
    countries_a = {g.country for g in geo_a if g.country is not None}
    countries_b = {g.country for g in geo_b if g.country is not None}

    has_asns = bool(asns_a) or bool(asns_b)
    has_countries = bool(countries_a) or bool(countries_b)

    if not has_asns and not has_countries:
        return missing_default

    if has_asns and has_countries:
        asn_dist = _jaccard_distance(asns_a, asns_b)
        country_dist = _jaccard_distance(countries_a, countries_b)
        return asn_weight * asn_dist + country_weight * country_dist

    if has_asns:
        return _jaccard_distance(asns_a, asns_b)

    return _jaccard_distance(countries_a, countries_b)
