"""M3.4.1 Infrastructure Overlap Diagnosis

Analyzes whether same-actor/same-family domains share detectable
infrastructure patterns (IP overlap, ASN, TLS issuer, registrar).
Diagnoses root cause of poor clustering: enrichment gaps, temporal
sampling, or genuine lack of shared infrastructure.

Usage:
    cd /mnt/d/proj/agent/cti-agent
    source agent-venv/bin/activate
    python -m scripts.m3_infrastructure_diagnosis
"""

from __future__ import annotations

import ipaddress
import json
import logging
import sys
from collections import Counter, defaultdict
from pathlib import Path

logging.basicConfig(format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%Y-%m-%d %H:%M:%S", level=logging.INFO)
logger = logging.getLogger(__name__)

ENRICHMENT_DIR = Path("data/enrichment")
DATASET_PATH = Path("data/dataset/attribution_dataset_v2.jsonl")
OUTPUT_DIR = Path("data/clustering/diagnostics")


def _valid_ip(value: str) -> bool:
    try:
        addr = ipaddress.ip_address(value)
        return not addr.is_unspecified
    except ValueError:
        return False


def _extract_ips(enrichment: dict) -> set[str]:
    ips = set()
    for r in enrichment.get("passive_dns", []):
        if _valid_ip(r.get("ip", "")):
            ips.add(r["ip"])
    for ip in enrichment.get("current_ips", []):
        if _valid_ip(ip):
            ips.add(ip)
    return ips


def _extract_asns(enrichment: dict) -> set[int]:
    return {g["asn_number"] for g in enrichment.get("geoip", []) if g.get("asn_number") is not None}


def _extract_issuers(enrichment: dict) -> set[str]:
    return {c["issuer"] for c in enrichment.get("certificates", []) if c.get("issuer")}


def _assign_quartile(first_seen: str | None, quartile_boundaries: list[str]) -> str:
    if not first_seen:
        return "unknown"
    for i, boundary in enumerate(quartile_boundaries):
        if first_seen <= boundary:
            return f"Q{i+1}"
    return f"Q{len(quartile_boundaries)+1}"


def diagnose_group(
    group_name: str,
    domains_meta: list[dict],
    enrichments: dict[str, dict],
) -> dict:
    domains = [m["domain"] for m in domains_meta if m["domain"] in enrichments]
    n = len(domains)
    if n < 2:
        return {"group": group_name, "domain_count": n, "diagnosis": "insufficient_domains"}

    first_seens = []
    for m in domains_meta:
        fs = m.get("first_seen")
        if fs:
            first_seens.append(fs)
    first_seens.sort()

    quartile_boundaries = []
    if len(first_seens) >= 4:
        step = len(first_seens) // 4
        quartile_boundaries = [first_seens[step], first_seens[2*step], first_seens[3*step]]

    domain_quartiles = {}
    for m in domains_meta:
        if m["domain"] in enrichments:
            domain_quartiles[m["domain"]] = _assign_quartile(m.get("first_seen"), quartile_boundaries)

    domain_ips = {d: _extract_ips(enrichments[d]) for d in domains}
    domain_asns = {d: _extract_asns(enrichments[d]) for d in domains}
    domain_issuers = {d: _extract_issuers(enrichments[d]) for d in domains}
    domain_registrars = {d: enrichments[d].get("registrar") for d in domains}

    ip_sharing_pairs = 0
    ip_sharing_same_q = 0
    ip_sharing_cross_q = 0
    total_pairs = 0
    same_q_pairs = 0
    cross_q_pairs = 0

    for i in range(n):
        for j in range(i+1, n):
            d_i, d_j = domains[i], domains[j]
            total_pairs += 1
            shared = domain_ips[d_i] & domain_ips[d_j]
            same_q = domain_quartiles.get(d_i) == domain_quartiles.get(d_j) and domain_quartiles.get(d_i) != "unknown"

            if same_q:
                same_q_pairs += 1
            else:
                cross_q_pairs += 1

            if shared:
                ip_sharing_pairs += 1
                if same_q:
                    ip_sharing_same_q += 1
                else:
                    ip_sharing_cross_q += 1

    all_asns = Counter()
    for d in domains:
        for asn in domain_asns[d]:
            all_asns[asn] += 1
    unique_asns = len(all_asns)
    dominant_asn = all_asns.most_common(1)[0] if all_asns else (None, 0)
    domains_with_asn = sum(1 for d in domains if domain_asns[d])

    all_issuers = Counter()
    for d in domains:
        for iss in domain_issuers[d]:
            all_issuers[iss] += 1
    domains_with_cert = sum(1 for d in domains if domain_issuers[d])
    dominant_issuer = all_issuers.most_common(1)[0] if all_issuers else (None, 0)

    registrar_counter = Counter(v for v in domain_registrars.values() if v)
    domains_with_registrar = sum(1 for v in domain_registrars.values() if v)
    dominant_registrar = registrar_counter.most_common(1)[0] if registrar_counter else (None, 0)

    signals = 0
    if ip_sharing_pairs > 0:
        signals += 1
    if dominant_asn[1] >= n * 0.5 and domains_with_asn >= n * 0.5:
        signals += 1
    if dominant_issuer[1] >= domains_with_cert * 0.5 and domains_with_cert >= 3:
        signals += 1
    if dominant_registrar[1] >= domains_with_registrar * 0.5 and domains_with_registrar >= 3:
        signals += 1

    if signals >= 3:
        verdict = "strong"
    elif signals >= 1:
        verdict = "weak"
    else:
        verdict = "none"

    return {
        "group": group_name,
        "domain_count": n,
        "verdict": verdict,
        "signal_count": signals,
        "time_distribution": dict(Counter(domain_quartiles.values())),
        "ip_overlap": {
            "sharing_pairs": ip_sharing_pairs,
            "total_pairs": total_pairs,
            "rate": round(ip_sharing_pairs / total_pairs, 4) if total_pairs > 0 else 0,
            "same_quartile_rate": round(ip_sharing_same_q / same_q_pairs, 4) if same_q_pairs > 0 else 0,
            "cross_quartile_rate": round(ip_sharing_cross_q / cross_q_pairs, 4) if cross_q_pairs > 0 else 0,
        },
        "asn": {
            "coverage": f"{domains_with_asn}/{n}",
            "unique_asns": unique_asns,
            "dominant": {"asn": dominant_asn[0], "count": dominant_asn[1]} if dominant_asn[0] else None,
        },
        "tls": {
            "coverage": f"{domains_with_cert}/{n}",
            "unique_issuers": len(all_issuers),
            "dominant": {"issuer": dominant_issuer[0], "count": dominant_issuer[1]} if dominant_issuer[0] else None,
        },
        "registrar": {
            "coverage": f"{domains_with_registrar}/{n}",
            "unique_registrars": len(registrar_counter),
            "dominant": {"registrar": dominant_registrar[0], "count": dominant_registrar[1]} if dominant_registrar[0] else None,
        },
    }


def write_report(results: dict, output_path: Path) -> None:
    lines = ["# M3.4.1 Infrastructure Overlap Diagnosis Report", ""]

    for section_name, section_key in [("Actor Group", "actor"), ("Family Group", "family"), ("Shared Infra Group", "shared")]:
        items = results.get(section_key, [])
        if not items:
            continue
        lines.append(f"## {section_name}")
        lines.append("")

        for r in items:
            name = r["group"]
            v = r["verdict"]
            lines.append(f"### {name} ({r['domain_count']} domains) — Signal: **{v}** ({r['signal_count']}/4)")
            lines.append(f"- Time: {r['time_distribution']}")
            ip = r["ip_overlap"]
            lines.append(f"- IP overlap: {ip['sharing_pairs']}/{ip['total_pairs']} pairs ({ip['rate']*100:.1f}%), same-Q={ip['same_quartile_rate']*100:.1f}% cross-Q={ip['cross_quartile_rate']*100:.1f}%")
            lines.append(f"- ASN: coverage={r['asn']['coverage']}, unique={r['asn']['unique_asns']}, dominant={r['asn']['dominant']}")
            lines.append(f"- TLS: coverage={r['tls']['coverage']}, unique={r['tls']['unique_issuers']}, dominant={r['tls']['dominant']}")
            lines.append(f"- Registrar: coverage={r['registrar']['coverage']}, unique={r['registrar']['unique_registrars']}, dominant={r['registrar']['dominant']}")
            lines.append("")

    lines.append("## Summary")
    lines.append("")
    actor_results = results.get("actor", [])
    if actor_results:
        strong = sum(1 for r in actor_results if r["verdict"] == "strong")
        weak = sum(1 for r in actor_results if r["verdict"] == "weak")
        none_ = sum(1 for r in actor_results if r["verdict"] == "none")
        ip_any = sum(1 for r in actor_results if r["ip_overlap"]["sharing_pairs"] > 0)
        asn_dom = sum(1 for r in actor_results if r["asn"]["dominant"] and r["asn"]["dominant"]["count"] >= r["domain_count"] * 0.5)
        lines.append(f"**Actor group** ({len(actor_results)} actors):")
        lines.append(f"- Signal strength: {strong} strong, {weak} weak, {none_} none")
        lines.append(f"- IP overlap present: {ip_any}/{len(actor_results)}")
        lines.append(f"- Dominant ASN (>50%): {asn_dom}/{len(actor_results)}")

        same_q_rates = [r["ip_overlap"]["same_quartile_rate"] for r in actor_results]
        cross_q_rates = [r["ip_overlap"]["cross_quartile_rate"] for r in actor_results]
        avg_same = sum(same_q_rates) / len(same_q_rates) if same_q_rates else 0
        avg_cross = sum(cross_q_rates) / len(cross_q_rates) if cross_q_rates else 0
        lines.append(f"- Avg same-quartile IP overlap: {avg_same*100:.2f}%")
        lines.append(f"- Avg cross-quartile IP overlap: {avg_cross*100:.2f}%")
        lines.append("")

    family_results = results.get("family", [])
    if family_results:
        strong = sum(1 for r in family_results if r["verdict"] == "strong")
        weak = sum(1 for r in family_results if r["verdict"] == "weak")
        none_ = sum(1 for r in family_results if r["verdict"] == "none")
        ip_any = sum(1 for r in family_results if r["ip_overlap"]["sharing_pairs"] > 0)
        lines.append(f"**Family group** ({len(family_results)} families):")
        lines.append(f"- Signal strength: {strong} strong, {weak} weak, {none_} none")
        lines.append(f"- IP overlap present: {ip_any}/{len(family_results)}")
        lines.append("")

    shared_results = results.get("shared", [])
    if shared_results:
        strong = sum(1 for r in shared_results if r["verdict"] == "strong")
        weak = sum(1 for r in shared_results if r["verdict"] == "weak")
        ip_any = sum(1 for r in shared_results if r["ip_overlap"]["sharing_pairs"] > 0)
        lines.append(f"**Shared infra group** ({len(shared_results)} sub-groups):")
        lines.append(f"- Signal strength: {strong} strong, {weak} weak")
        lines.append(f"- IP overlap present: {ip_any}/{len(shared_results)}")
        lines.append("")

    lines.append("## Conclusion")
    lines.append("")
    lines.append("_To be filled after reviewing the data above._")

    output_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    dataset = [json.loads(line) for line in DATASET_PATH.read_text(encoding="utf-8").strip().split("\n")]
    logger.info("Loaded %d dataset entries", len(dataset))

    enrichments: dict[str, dict] = {}
    for path in sorted(ENRICHMENT_DIR.glob("*.json")):
        try:
            enrichments[path.stem] = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    logger.info("Loaded %d enrichment files", len(enrichments))

    by_group: dict[str, list[dict]] = defaultdict(list)
    for entry in dataset:
        by_group[entry.get("group", "unknown")].append(entry)

    results: dict[str, list[dict]] = {}

    actor_entries = by_group.get("actor_attribution", [])
    by_actor: dict[str, list[dict]] = defaultdict(list)
    for e in actor_entries:
        by_actor[e.get("actor", "unknown")].append(e)
    logger.info("Actor group: %d actors", len(by_actor))
    results["actor"] = []
    for actor, entries in sorted(by_actor.items()):
        r = diagnose_group(actor, entries, enrichments)
        results["actor"].append(r)
        logger.info("  %s: verdict=%s, IP overlap=%d/%d", actor, r["verdict"],
                     r["ip_overlap"]["sharing_pairs"], r["ip_overlap"]["total_pairs"])

    family_entries = by_group.get("family_attribution", [])
    by_family: dict[str, list[dict]] = defaultdict(list)
    for e in family_entries:
        by_family[e.get("family", "unknown")].append(e)
    logger.info("Family group: %d families", len(by_family))
    results["family"] = []
    for family, entries in sorted(by_family.items()):
        r = diagnose_group(family, entries, enrichments)
        results["family"].append(r)
        logger.info("  %s: verdict=%s, IP overlap=%d/%d", family, r["verdict"],
                     r["ip_overlap"]["sharing_pairs"], r["ip_overlap"]["total_pairs"])

    # Dataset JSONL uses group key "shared_infra" (see m2_dataset_builder.py); not the boolean field name.
    shared_entries = by_group.get("shared_infra", [])
    by_shared: dict[str, list[dict]] = defaultdict(list)
    for e in shared_entries:
        by_shared[e.get("family", "shared")].append(e)
    logger.info("Shared infra group: %d sub-groups", len(by_shared))
    results["shared"] = []
    for name, entries in sorted(by_shared.items()):
        r = diagnose_group(f"shared:{name}", entries, enrichments)
        results["shared"].append(r)
        logger.info("  %s: verdict=%s, IP overlap=%d/%d", name, r["verdict"],
                     r["ip_overlap"]["sharing_pairs"], r["ip_overlap"]["total_pairs"])

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "infrastructure_overlap_data.json").write_text(
        json.dumps(results, indent=2, default=str), encoding="utf-8",
    )
    write_report(results, OUTPUT_DIR / "infrastructure_overlap_report.md")
    logger.info("Report: %s", OUTPUT_DIR / "infrastructure_overlap_report.md")
    logger.info("Data: %s", OUTPUT_DIR / "infrastructure_overlap_data.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
