"""M3.8-M3.13 Campaign Discovery Pipeline.

Builds incident similarity graph, runs Leiden community detection,
computes campaign attributes, maps to actors, writes to Neo4j.

Usage:
    cd /mnt/d/proj/agent/cti-agent
    source agent-venv/bin/activate
    python -m scripts.m3_campaign_discovery --grid-search --dry-run
    python -m scripts.m3_campaign_discovery --theta-min 0.1 --gamma 1.0
    python -m scripts.m3_campaign_discovery --no-time-filter --grid-search
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import asdict
from pathlib import Path

from cti_agent.campaign.actor_mapping import (
    build_ground_truth_map,
    build_shared_infra_set,
    map_campaigns_to_actors,
)
from cti_agent.campaign.attributes import compute_campaigns
from cti_agent.campaign.grid_search import GridSearchConfig, find_best_config, run_grid_search
from cti_agent.campaign.leiden import run_leiden_stable
from cti_agent.campaign.similarity import build_similarity_graph, load_incidents
from cti_agent.campaign.writer import write_campaigns_to_neo4j
from cti_agent.graph.client import Neo4jClient
from cti_agent.graph.config import get_settings
from cti_agent.graph.repository import GraphRepository

logging.basicConfig(format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%Y-%m-%d %H:%M:%S", level=logging.INFO)
logger = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="Campaign discovery pipeline")
    parser.add_argument("--incidents", type=Path, default=Path("data/clustering/graph_output/incidents.json"))
    parser.add_argument("--dataset", type=Path, default=Path("data/dataset/attribution_dataset_v2.jsonl"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/clustering/campaign_output"))
    parser.add_argument("--theta-min", type=float, default=0.1)
    parser.add_argument("--gamma", type=float, default=1.0)
    parser.add_argument("--time-window", type=int, default=90)
    parser.add_argument("--no-time-filter", action="store_true")
    parser.add_argument("--grid-search", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    incidents = load_incidents(args.incidents)
    eligible = [inc for inc in incidents if inc.cluster_tag_set]
    isolated = [inc for inc in incidents if not inc.cluster_tag_set]
    logger.info("Incidents: %d total, %d eligible (non-empty tags), %d isolated", len(incidents), len(eligible), len(isolated))

    incident_domains: dict[str, list[str]] = {}
    raw_incidents = json.loads(args.incidents.read_text(encoding="utf-8"))
    for entry in raw_incidents:
        incident_domains[entry["incident_id"]] = entry.get("domains", [])

    gt_map = build_ground_truth_map(args.dataset, incident_domains)
    shared_infra = build_shared_infra_set(args.dataset)
    logger.info("Ground truth: %d incident labels, %d shared infra domains", len(gt_map), len(shared_infra))

    if args.grid_search:
        logger.info("")
        logger.info("=== Grid Search ===")
        config = GridSearchConfig(
            theta_min_values=[round(0.05 * i, 2) for i in range(1, 11)],
            gamma_values=[round(0.5 + 0.1 * i, 1) for i in range(16)],
            time_window_days=args.time_window,
            no_time_filter=args.no_time_filter,
        )
        grid_results = run_grid_search(incidents, config, ground_truth=gt_map)

        args.output_dir.mkdir(parents=True, exist_ok=True)
        grid_out = [
            {k: v for k, v in asdict(r).items() if k != "membership"}
            for r in grid_results
        ]
        (args.output_dir / "grid_search_results.json").write_text(
            json.dumps(grid_out, indent=2, default=str), encoding="utf-8")
        logger.info("Grid search: %d configs saved to %s", len(grid_results), args.output_dir)

        best = find_best_config(grid_results, metric="ari")
        if best:
            logger.info("Best config: θ=%.2f γ=%.1f → %d communities, ARI=%s, Sil=%s",
                        best.theta_min, best.gamma, best.n_communities,
                        f"{best.ari:.4f}" if best.ari is not None else "N/A",
                        f"{best.silhouette:.4f}" if best.silhouette is not None else "N/A")
            args.theta_min = best.theta_min
            args.gamma = best.gamma

    logger.info("")
    logger.info("=== Building Similarity Graph (θ=%.2f, time=%s) ===", args.theta_min,
                f"{args.time_window}d" if not args.no_time_filter else "disabled")
    graph, eligible_filtered = build_similarity_graph(
        incidents, theta_min=args.theta_min,
        time_window_days=args.time_window, no_time_filter=args.no_time_filter,
    )

    logger.info("")
    logger.info("=== Leiden Community Detection (γ=%.1f) ===", args.gamma)
    leiden = run_leiden_stable(graph, resolution=args.gamma)
    logger.info("Communities: %d, Modularity: %.4f, Sizes: %s", leiden.n_communities, leiden.modularity, leiden.community_sizes)

    logger.info("")
    logger.info("=== Campaign Attributes ===")
    campaigns = compute_campaigns(eligible_filtered, leiden.membership)
    for c in campaigns:
        logger.info("  %s: %d incidents, confidence=%.4f, shared=%s, all=%s",
                     c.campaign_id, c.incident_count, c.confidence_score,
                     sorted(c.shared_clusters), sorted(c.all_clusters))

    logger.info("")
    logger.info("=== Actor Mapping ===")
    attributions = map_campaigns_to_actors(campaigns, gt_map, incident_domains, shared_infra)
    for attr in attributions:
        logger.info("  %s → %s (confidence=%.4f, shared_infra=%s)",
                     attr.campaign_id, attr.primary_actor, attr.confidence, attr.is_shared_infrastructure)

    args.output_dir.mkdir(parents=True, exist_ok=True)

    (args.output_dir / "campaigns.json").write_text(
        json.dumps([{**asdict(c), "shared_clusters": sorted(c.shared_clusters), "all_clusters": sorted(c.all_clusters),
                     "first_seen": c.first_seen.isoformat(), "last_seen": c.last_seen.isoformat()} for c in campaigns],
                   indent=2, default=str), encoding="utf-8")

    (args.output_dir / "actor_attributions.json").write_text(
        json.dumps([asdict(a) for a in attributions], indent=2), encoding="utf-8")

    edges = [{"source": graph.vs[e.source]["incident_id"], "target": graph.vs[e.target]["incident_id"],
              "weight": round(e["weight"], 4)} for e in graph.es]
    (args.output_dir / "similarity_graph.json").write_text(
        json.dumps(edges, indent=2), encoding="utf-8")

    logger.info("JSON saved to %s", args.output_dir)

    if args.dry_run:
        logger.info("DRY RUN — skipping Neo4j writes")
        return 0

    logger.info("")
    logger.info("=== Neo4j Writes ===")
    settings = get_settings()
    with Neo4jClient(settings) as client:
        repo = GraphRepository(client)
        summary = write_campaigns_to_neo4j(repo, campaigns, attributions)
        logger.info("Written: %d campaigns, %d BELONGS_TO, %d actors, %d ATTRIBUTED_TO",
                     summary.campaigns_written, summary.belongs_to_edges,
                     summary.actors_written, summary.attributed_to_edges)

    return 0


if __name__ == "__main__":
    sys.exit(main())
