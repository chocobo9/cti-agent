"""Run DBSCAN/HDBSCAN clustering on the precomputed distance matrix.

Supports single-run, parameter sweep, and combined ensemble modes.
Uses k-distance analysis to suggest eps range before DBSCAN sweep.

Usage:
    cd /mnt/d/proj/agent/cti-agent
    source agent-venv/bin/activate

    # Full sweep (default): k-distance analysis + sweep both + combined best
    python -m scripts.run_clustering

    # Single algorithm run
    python -m scripts.run_clustering --algorithm dbscan --eps 0.3 --min-samples 3
    python -m scripts.run_clustering --algorithm hdbscan --min-cluster-size 5

    # Sweep only one algorithm
    python -m scripts.run_clustering --sweep --algorithm dbscan
    python -m scripts.run_clustering --sweep --algorithm hdbscan
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import numpy as np

from cti_agent.clustering.clusterer import (
    compute_k_distances,
    evaluate_clustering,
    find_best_params,
    load_ground_truth,
    run_combined,
    run_dbscan,
    run_hdbscan,
    save_cluster_result,
    save_sweep_report,
    suggest_eps_range,
    sweep_dbscan,
    sweep_hdbscan,
)
from cti_agent.clustering.matrix import load_distance_matrix

logging.basicConfig(
    format="%(asctime)s %(levelname)-7s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def _print_evaluation(label: str, ev) -> None:
    logger.info("  %-12s clusters=%-3d noise=%.1f%%  sil=%s  ARI=%s  ARI_actor=%s  ARI_family=%s  purity=%s",
                label, ev.n_clusters, ev.noise_ratio * 100,
                f"{ev.silhouette:.4f}" if ev.silhouette is not None else "N/A",
                f"{ev.ari_overall:.4f}" if ev.ari_overall is not None else "N/A",
                f"{ev.ari_actor_group:.4f}" if ev.ari_actor_group is not None else "N/A",
                f"{ev.ari_family_group:.4f}" if ev.ari_family_group is not None else "N/A",
                f"{ev.cluster_purity:.4f}" if ev.cluster_purity is not None else "N/A")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run clustering on distance matrix")
    parser.add_argument("--matrix-dir", type=Path, default=Path("data/clustering/distance_matrix"))
    parser.add_argument("--dataset-path", type=Path, default=Path("data/dataset/attribution_dataset_v1.jsonl"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/clustering/results"))
    parser.add_argument("--algorithm", type=str, default="both", choices=["dbscan", "hdbscan", "combined", "both"])
    parser.add_argument("--sweep", action="store_true", help="Run parameter sweep")
    parser.add_argument("--eps", type=float, default=None)
    parser.add_argument("--min-samples", type=int, default=3)
    parser.add_argument("--min-cluster-size", type=int, default=5)
    parser.add_argument("--enrichment-dir", type=Path, default=Path("data/enrichment"))
    parser.add_argument("--no-quality-filter", action="store_true", help="Skip structural quality filtering")
    parser.add_argument("--dbscan-quality-threshold", type=float, default=0.40)
    parser.add_argument("--hdbscan-quality-threshold", type=float, default=0.20)
    args = parser.parse_args()

    dm = load_distance_matrix(args.matrix_dir)
    matrix = dm.matrix
    domain_labels = dm.domain_labels
    logger.info("Loaded %dx%d distance matrix (%d domains)", matrix.shape[0], matrix.shape[1], len(domain_labels))

    gt = load_ground_truth(args.dataset_path, domain_filter=set(domain_labels))
    logger.info("Ground truth: %d domains matched", len(gt))

    enrichments = None
    if not args.no_quality_filter:
        from cti_agent.clustering.matrix import load_enrichments
        enrichments_list, _ = load_enrichments(args.enrichment_dir, min_features=2)
        enrichment_map = {e.domain: e for e in enrichments_list}
        enrichments = [enrichment_map[d] for d in domain_labels if d in enrichment_map]
        if len(enrichments) != len(domain_labels):
            logger.warning("Enrichment mismatch: %d enrichments vs %d domains — quality filter disabled",
                           len(enrichments), len(domain_labels))
            enrichments = None
        else:
            logger.info("Enrichments loaded: %d (quality filter enabled, DB=%.2f, HDB=%.2f)",
                        len(enrichments), args.dbscan_quality_threshold, args.hdbscan_quality_threshold)

    if args.algorithm == "both" or args.sweep:
        logger.info("")
        logger.info("=== k-distance analysis ===")
        k_dists = compute_k_distances(matrix, k_values=[2, 3, 5])
        for k, dists in k_dists.items():
            eps_min, eps_elbow, eps_max = suggest_eps_range(dists)
            logger.info("  k=%d: elbow=%.4f, suggested range [%.4f, %.4f]", k, eps_elbow, eps_min, eps_max)
            logger.info("    P10=%.4f  P25=%.4f  P50=%.4f  P75=%.4f  P90=%.4f",
                        dists[int(len(dists)*0.1)], dists[int(len(dists)*0.25)],
                        dists[int(len(dists)*0.5)], dists[int(len(dists)*0.75)],
                        dists[int(len(dists)*0.9)])

        k3_dists = k_dists.get(3, k_dists.get(2, np.array([0.3])))
        eps_min, eps_elbow, eps_max = suggest_eps_range(k3_dists)
        eps_values = sorted(set([
            round(v, 3) for v in np.linspace(eps_min, eps_max, 10)
        ]))
        logger.info("  DBSCAN eps sweep range: %s", [f"{v:.3f}" for v in eps_values])

        logger.info("")
        logger.info("=== DBSCAN sweep ===")
        db_sweep = sweep_dbscan(matrix, domain_labels, gt, eps_values=eps_values,
                                enrichments=enrichments, quality_threshold=args.dbscan_quality_threshold)
        save_sweep_report(db_sweep, args.output_dir, "dbscan")
        best_db = find_best_params(db_sweep, "silhouette")
        if best_db:
            logger.info("Best DBSCAN (pre-filter):")
            _print_evaluation(f"  {best_db.params}", best_db.evaluation)
            if best_db.post_filter_evaluation:
                logger.info("Best DBSCAN (post-filter):")
                _print_evaluation(f"  {best_db.params}", best_db.post_filter_evaluation)

        logger.info("")
        logger.info("=== HDBSCAN sweep ===")
        hdb_sweep = sweep_hdbscan(matrix, domain_labels, gt,
                                  enrichments=enrichments, quality_threshold=args.hdbscan_quality_threshold)
        save_sweep_report(hdb_sweep, args.output_dir, "hdbscan")
        best_hdb = find_best_params(hdb_sweep, "silhouette")
        if best_hdb:
            logger.info("Best HDBSCAN (pre-filter):")
            _print_evaluation(f"  {best_hdb.params}", best_hdb.evaluation)
            if best_hdb.post_filter_evaluation:
                logger.info("Best HDBSCAN (post-filter):")
                _print_evaluation(f"  {best_hdb.params}", best_hdb.post_filter_evaluation)

        if best_db and best_hdb:
            logger.info("")
            logger.info("=== Combined (DBSCAN-first, HDBSCAN fallback, quality-filtered) ===")
            combined = run_combined(
                matrix,
                dbscan_params=best_db.params,
                hdbscan_params=best_hdb.params,
                domain_labels=domain_labels,
                enrichments=enrichments,
                dbscan_quality_threshold=args.dbscan_quality_threshold,
                hdbscan_quality_threshold=args.hdbscan_quality_threshold,
            )
            combined_ev = evaluate_clustering(combined, matrix, gt)
            _print_evaluation("Combined", combined_ev)
            save_cluster_result(combined, combined_ev, args.output_dir / "combined", ground_truth=gt)

    elif args.algorithm == "dbscan":
        eps = args.eps
        if eps is None:
            k_dists = compute_k_distances(matrix, k_values=[3])
            _, eps, _ = suggest_eps_range(k_dists[3])
            logger.info("Auto eps from k=3 elbow: %.4f", eps)
        cr = run_dbscan(matrix, eps=eps, min_samples=args.min_samples, domain_labels=domain_labels)
        ev = evaluate_clustering(cr, matrix, gt)
        _print_evaluation("DBSCAN", ev)
        save_cluster_result(cr, ev, args.output_dir / "dbscan", ground_truth=gt)

    elif args.algorithm == "hdbscan":
        cr = run_hdbscan(matrix, min_cluster_size=args.min_cluster_size, min_samples=args.min_samples, domain_labels=domain_labels)
        ev = evaluate_clustering(cr, matrix, gt)
        _print_evaluation("HDBSCAN", ev)
        save_cluster_result(cr, ev, args.output_dir / "hdbscan", ground_truth=gt)

    elif args.algorithm == "combined":
        eps = args.eps
        if eps is None:
            k_dists = compute_k_distances(matrix, k_values=[3])
            _, eps, _ = suggest_eps_range(k_dists[3])
        cr = run_combined(
            matrix,
            dbscan_params={"eps": eps, "min_samples": args.min_samples},
            hdbscan_params={"min_cluster_size": args.min_cluster_size, "min_samples": args.min_samples},
            domain_labels=domain_labels,
        )
        ev = evaluate_clustering(cr, matrix, gt)
        _print_evaluation("Combined", ev)
        save_cluster_result(cr, ev, args.output_dir / "combined", ground_truth=gt)

    logger.info("")
    logger.info("Output: %s", args.output_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
