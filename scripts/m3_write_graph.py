"""M3.5-M3.7 — Write cluster assignments and incidents to Neo4j.

Runs combined DB+HDB clustering on the precomputed distance matrix,
generates incidents from pulse_id groupings, and writes Cluster nodes,
Incident nodes, IN_CLUSTER edges, and PART_OF edges to Neo4j.

Usage:
    cd /mnt/d/proj/agent/cti-agent
    source agent-venv/bin/activate
    python -m scripts.m3_write_graph
    python -m scripts.m3_write_graph --dry-run
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

import numpy as np

from cti_agent.clustering.clusterer import (
    evaluate_clustering,
    load_ground_truth,
    run_combined,
)
from cti_agent.clustering.matrix import load_distance_matrix, load_enrichments
from cti_agent.graph.client import Neo4jClient
from cti_agent.graph.config import get_settings
from cti_agent.graph.repository import GraphRepository
from cti_agent.models import load_domains_from_file

logging.basicConfig(format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%Y-%m-%d %H:%M:%S", level=logging.INFO)
logger = logging.getLogger(__name__)


def _parse_date(s: str | None) -> date:
    if not s:
        return date(2020, 1, 1)
    try:
        return date.fromisoformat(s[:10])
    except (ValueError, TypeError):
        return date(2020, 1, 1)


def main() -> int:
    parser = argparse.ArgumentParser(description="Write cluster + incident graph to Neo4j")
    parser.add_argument("--dataset", type=Path, default=Path("data/dataset/attribution_dataset_v2.jsonl"))
    parser.add_argument("--matrix-dir", type=Path, default=Path("data/clustering/distance_matrix"))
    parser.add_argument("--enrichment-dir", type=Path, default=Path("data/enrichment"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/clustering/graph_output"))
    parser.add_argument("--dry-run", action="store_true", help="Generate JSON only, skip Neo4j writes")
    parser.add_argument("--dbscan-eps", type=float, default=0.215)
    parser.add_argument("--dbscan-min-samples", type=int, default=2)
    parser.add_argument("--hdbscan-min-cluster-size", type=int, default=3)
    parser.add_argument("--hdbscan-min-samples", type=int, default=2)
    parser.add_argument("--dbscan-quality-threshold", type=float, default=0.40)
    parser.add_argument("--hdbscan-quality-threshold", type=float, default=0.20)
    args = parser.parse_args()

    # --- Load inputs ---
    dm = load_distance_matrix(args.matrix_dir)
    matrix = dm.matrix
    domain_labels = dm.domain_labels
    logger.info("Matrix: %dx%d (%d domains)", matrix.shape[0], matrix.shape[1], len(domain_labels))

    enrichments, _ = load_enrichments(args.enrichment_dir, min_features=2, domain_whitelist=set(domain_labels))
    assert [e.domain for e in enrichments] == domain_labels, "Enrichment ordering mismatch with domain_labels"
    logger.info("Enrichments: %d (aligned with matrix)", len(enrichments))

    dataset_entries = load_domains_from_file(args.dataset)
    dataset_map = {inp.domain: inp for inp in dataset_entries}
    logger.info("Dataset: %d entries", len(dataset_entries))

    gt = load_ground_truth(args.dataset, domain_filter=set(domain_labels))

    # --- M3.5: Run combined clustering ---
    logger.info("")
    logger.info("=== M3.5: Combined Clustering ===")
    result = run_combined(
        matrix,
        dbscan_params={"eps": args.dbscan_eps, "min_samples": args.dbscan_min_samples},
        hdbscan_params={"min_cluster_size": args.hdbscan_min_cluster_size, "min_samples": args.hdbscan_min_samples},
        domain_labels=domain_labels,
        enrichments=enrichments,
        dbscan_quality_threshold=args.dbscan_quality_threshold,
        hdbscan_quality_threshold=args.hdbscan_quality_threshold,
    )
    ev = evaluate_clustering(result, matrix, gt)
    logger.info("Clusters: %d, Noise: %d (%.1f%%), Purity: %s, ARI: %s",
                ev.n_clusters, ev.n_noise, ev.noise_ratio * 100,
                f"{ev.cluster_purity:.4f}" if ev.cluster_purity is not None else "N/A",
                f"{ev.ari_overall:.4f}" if ev.ari_overall is not None else "N/A")
    logger.info("Cluster sizes: %s", ev.cluster_sizes)

    cluster_info: dict[int, dict] = {}
    for cid in set(result.labels):
        if cid == -1:
            continue
        mask = result.labels == cid
        domains_in = [domain_labels[i] for i in range(len(domain_labels)) if mask[i]]
        cluster_info[cid] = {
            "cluster_id": int(cid),
            "size": len(domains_in),
            "algorithm": "combined",
            "quality_score": None,
            "domains": domains_in,
        }

    domain_cluster_map = {domain_labels[i]: int(result.labels[i]) for i in range(len(domain_labels))}

    # --- M3.6: Incident generation ---
    logger.info("")
    logger.info("=== M3.6: Incident Generation ===")

    pulse_groups: dict[str, list[str]] = defaultdict(list)
    for inp in dataset_entries:
        if inp.pulse_id:
            pulse_groups[inp.pulse_id].append(inp.domain)
        elif inp.family:
            pulse_groups[f"threatfox|{inp.family}"].append(inp.domain)
        else:
            pulse_groups["unknown"].append(inp.domain)

    incidents: list[dict] = []
    for incident_id, domains in sorted(pulse_groups.items()):
        cluster_tags = sorted(set(
            domain_cluster_map.get(d, -1) for d in domains
        ) - {-1})

        domain_dates = []
        for d in domains:
            inp = dataset_map.get(d)
            if inp:
                fs = getattr(inp, "first_seen", None)
                if fs:
                    domain_dates.append(_parse_date(fs))

        inc_date = min(domain_dates) if domain_dates else date(2020, 1, 1)

        incidents.append({
            "incident_id": incident_id,
            "date": inc_date.isoformat(),
            "cluster_tag_set": cluster_tags,
            "domain_count": len(domains),
            "domains": domains,
        })

    logger.info("Incidents: %d (OTX pulses: %d, ThreatFox: %d)",
                len(incidents),
                sum(1 for i in incidents if not i["incident_id"].startswith("threatfox")),
                sum(1 for i in incidents if i["incident_id"].startswith("threatfox")))
    logger.info("Incidents with cluster tags: %d / %d",
                sum(1 for i in incidents if i["cluster_tag_set"]), len(incidents))

    # --- Save JSON outputs ---
    args.output_dir.mkdir(parents=True, exist_ok=True)

    assignments = [{"domain": d, "cluster_id": domain_cluster_map.get(d, -1)} for d in domain_labels]
    (args.output_dir / "cluster_assignments.json").write_text(
        json.dumps(assignments, indent=2), encoding="utf-8")

    (args.output_dir / "incidents.json").write_text(
        json.dumps(incidents, indent=2, default=str), encoding="utf-8")

    (args.output_dir / "cluster_metadata.json").write_text(
        json.dumps(list(cluster_info.values()), indent=2), encoding="utf-8")

    logger.info("JSON saved to %s", args.output_dir)

    if args.dry_run:
        logger.info("DRY RUN — skipping Neo4j writes")
        return 0

    # --- M3.5 + M3.7: Neo4j writes ---
    logger.info("")
    logger.info("=== Neo4j Writes ===")
    settings = get_settings()
    with Neo4jClient(settings) as client:
        repo = GraphRepository(client)

        domain_count_rows = client.execute_read("MATCH (d:Domain) RETURN count(d) AS cnt")
        neo4j_domains = domain_count_rows[0]["cnt"] if domain_count_rows else 0
        logger.info("Neo4j has %d Domain nodes", neo4j_domains)
        if neo4j_domains < 500:
            logger.warning("Expected 700+ Domain nodes. Run reingest_from_json.py first if needed.")

        for cid, info in cluster_info.items():
            repo.merge_cluster(
                cluster_id=info["cluster_id"],
                size=info["size"],
                algorithm=info["algorithm"],
                quality_score=info["quality_score"],
            )
        logger.info("Wrote %d Cluster nodes", len(cluster_info))

        in_cluster_count = 0
        for cid, info in cluster_info.items():
            for domain in info["domains"]:
                repo.merge_in_cluster(domain=domain, cluster_id=info["cluster_id"])
                in_cluster_count += 1
        logger.info("Wrote %d IN_CLUSTER edges", in_cluster_count)

        for inc in incidents:
            repo.merge_incident(
                incident_id=inc["incident_id"],
                date=date.fromisoformat(inc["date"]),
                cluster_tag_set=inc["cluster_tag_set"],
                domain_count=inc["domain_count"],
            )
        logger.info("Wrote %d Incident nodes", len(incidents))

        part_of_count = 0
        for inc in incidents:
            for domain in inc["domains"]:
                repo.merge_part_of(domain=domain, incident_id=inc["incident_id"])
                part_of_count += 1
        logger.info("Wrote %d PART_OF edges", part_of_count)

    logger.info("")
    logger.info("=== Summary ===")
    logger.info("Clusters: %d nodes, %d IN_CLUSTER edges", len(cluster_info), in_cluster_count)
    logger.info("Incidents: %d nodes, %d PART_OF edges", len(incidents), part_of_count)
    return 0


if __name__ == "__main__":
    sys.exit(main())
