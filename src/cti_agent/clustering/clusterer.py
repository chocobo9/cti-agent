"""DBSCAN/HDBSCAN clustering on precomputed distance matrices.

Implements three clustering modes:
  1. DBSCAN with metric='precomputed'
  2. HDBSCAN (sklearn built-in) with metric='precomputed'
  3. Combined: DBSCAN-first, HDBSCAN fallback for noise domains (Leite et al.)

Includes k-distance plot analysis for eps selection, parameter sweep,
ground truth evaluation (Silhouette, ARI, cluster purity), and persistence.
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.cluster import DBSCAN, HDBSCAN
from sklearn.metrics import adjusted_rand_score, silhouette_score

from cti_agent.enrichment.models import DomainEnrichment
from cti_agent.models import load_domains_from_file

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GroundTruthLabel:
    actor: str | None
    family: str | None
    group: str
    shared_infrastructure: bool


@dataclass(frozen=True)
class ClusterResult:
    labels: np.ndarray
    algorithm: str
    params: dict[str, Any]
    n_clusters: int
    n_noise: int
    noise_ratio: float
    domain_labels: list[str]


@dataclass(frozen=True)
class ClusterEvaluation:
    silhouette: float | None
    ari_overall: float | None
    ari_actor_group: float | None
    ari_family_group: float | None
    n_clusters: int
    n_noise: int
    noise_ratio: float
    cluster_sizes: list[int]
    cluster_purity: float | None


@dataclass(frozen=True)
class SweepResult:
    algorithm: str
    params: dict[str, Any]
    evaluation: ClusterEvaluation
    post_filter_evaluation: ClusterEvaluation | None = None


# ---------------------------------------------------------------------------
# Ground truth
# ---------------------------------------------------------------------------

def load_ground_truth(
    dataset_path: Path,
    domain_filter: set[str] | None = None,
) -> dict[str, GroundTruthLabel]:
    """Load ground truth labels from the dataset JSONL.

    If *domain_filter* is provided, only domains in the set are included.
    """
    inputs = load_domains_from_file(dataset_path)
    result: dict[str, GroundTruthLabel] = {}
    for inp in inputs:
        if domain_filter is not None and inp.domain not in domain_filter:
            continue
        result[inp.domain] = GroundTruthLabel(
            actor=inp.actor,
            family=inp.family,
            group=inp.group or "unknown",
            shared_infrastructure=inp.shared_infrastructure,
        )
    return result


# ---------------------------------------------------------------------------
# k-distance analysis
# ---------------------------------------------------------------------------

def compute_k_distances(matrix: np.ndarray, k_values: list[int] | None = None) -> dict[int, np.ndarray]:
    """For each k, compute the sorted k-th nearest neighbor distances."""
    if k_values is None:
        k_values = [2, 3, 5]
    n = matrix.shape[0]
    result: dict[int, np.ndarray] = {}
    for k in k_values:
        if k >= n:
            continue
        k_dists = np.sort(matrix, axis=1)[:, k]
        result[k] = np.sort(k_dists)
    return result


def suggest_eps_range(
    k_distances: np.ndarray,
) -> tuple[float, float, float]:
    """Suggest eps range from k-distance curve using gradient analysis.

    Returns (eps_min, eps_elbow, eps_max).
    """
    n = len(k_distances)
    if n < 3:
        return (0.1, 0.3, 0.5)

    gradient = np.gradient(k_distances)
    second_grad = np.gradient(gradient)
    elbow_idx = int(np.argmax(second_grad[:int(n * 0.9)]))

    eps_elbow = float(k_distances[elbow_idx])
    eps_min = max(0.05, eps_elbow * 0.5)
    eps_max = min(1.0, eps_elbow * 2.0)

    return (round(eps_min, 4), round(eps_elbow, 4), round(eps_max, 4))


# ---------------------------------------------------------------------------
# Clustering algorithms
# ---------------------------------------------------------------------------

def run_dbscan(
    matrix: np.ndarray,
    eps: float,
    min_samples: int = 3,
    domain_labels: list[str] | None = None,
) -> ClusterResult:
    model = DBSCAN(eps=eps, min_samples=min_samples, metric="precomputed")
    labels = model.fit_predict(matrix)
    n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
    n_noise = int(np.sum(labels == -1))
    return ClusterResult(
        labels=labels,
        algorithm="dbscan",
        params={"eps": eps, "min_samples": min_samples},
        n_clusters=n_clusters,
        n_noise=n_noise,
        noise_ratio=round(n_noise / len(labels), 4) if len(labels) > 0 else 0.0,
        domain_labels=domain_labels or [],
    )


def run_hdbscan(
    matrix: np.ndarray,
    min_cluster_size: int = 5,
    min_samples: int = 3,
    domain_labels: list[str] | None = None,
) -> ClusterResult:
    model = HDBSCAN(
        min_cluster_size=min_cluster_size,
        min_samples=min_samples,
        metric="precomputed",
        copy=True,
    )
    labels = model.fit_predict(matrix)
    n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
    n_noise = int(np.sum(labels == -1))
    return ClusterResult(
        labels=labels,
        algorithm="hdbscan",
        params={"min_cluster_size": min_cluster_size, "min_samples": min_samples},
        n_clusters=n_clusters,
        n_noise=n_noise,
        noise_ratio=round(n_noise / len(labels), 4) if len(labels) > 0 else 0.0,
        domain_labels=domain_labels or [],
    )


def run_combined(
    matrix: np.ndarray,
    dbscan_params: dict[str, Any],
    hdbscan_params: dict[str, Any],
    domain_labels: list[str] | None = None,
    enrichments: list[DomainEnrichment] | None = None,
    dbscan_quality_threshold: float = 0.40,
    hdbscan_quality_threshold: float = 0.20,
) -> ClusterResult:
    """Combined ensemble per Leite et al.: DBSCAN-first, HDBSCAN fallback.

    When *enrichments* is provided, quality filtering is applied to each
    algorithm's output independently before merging.
    """
    from cti_agent.clustering.quality import filter_clusters_by_structural_quality

    db_result = run_dbscan(matrix, domain_labels=domain_labels, **dbscan_params)
    hdb_result = run_hdbscan(matrix, domain_labels=domain_labels, **hdbscan_params)

    if enrichments is not None:
        db_labels, _ = filter_clusters_by_structural_quality(
            db_result.labels, enrichments, matrix, threshold=dbscan_quality_threshold,
        )
        db_result = ClusterResult(
            labels=db_labels, algorithm=db_result.algorithm, params=db_result.params,
            n_clusters=len(set(db_labels)) - (1 if -1 in db_labels else 0),
            n_noise=int(np.sum(db_labels == -1)),
            noise_ratio=round(int(np.sum(db_labels == -1)) / len(db_labels), 4),
            domain_labels=domain_labels or [],
        )
        hdb_labels, _ = filter_clusters_by_structural_quality(
            hdb_result.labels, enrichments, matrix, threshold=hdbscan_quality_threshold,
        )
        hdb_result = ClusterResult(
            labels=hdb_labels, algorithm=hdb_result.algorithm, params=hdb_result.params,
            n_clusters=len(set(hdb_labels)) - (1 if -1 in hdb_labels else 0),
            n_noise=int(np.sum(hdb_labels == -1)),
            noise_ratio=round(int(np.sum(hdb_labels == -1)) / len(hdb_labels), 4),
            domain_labels=domain_labels or [],
        )

    n = len(db_result.labels)
    combined = np.full(n, -1, dtype=int)

    for i in range(n):
        if db_result.labels[i] != -1:
            combined[i] = db_result.labels[i]
        elif hdb_result.labels[i] != -1:
            combined[i] = hdb_result.labels[i] + db_result.n_clusters + 1

    label_map: dict[int, int] = {}
    next_id = 0
    relabeled = np.full(n, -1, dtype=int)
    for i in range(n):
        if combined[i] == -1:
            continue
        if combined[i] not in label_map:
            label_map[combined[i]] = next_id
            next_id += 1
        relabeled[i] = label_map[combined[i]]

    n_clusters = next_id
    n_noise = int(np.sum(relabeled == -1))
    return ClusterResult(
        labels=relabeled,
        algorithm="combined",
        params={"dbscan": dbscan_params, "hdbscan": hdbscan_params},
        n_clusters=n_clusters,
        n_noise=n_noise,
        noise_ratio=round(n_noise / n, 4) if n > 0 else 0.0,
        domain_labels=domain_labels or [],
    )


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def _build_true_labels(
    domain_labels: list[str],
    ground_truth: dict[str, GroundTruthLabel],
) -> list[str | None]:
    result: list[str | None] = []
    for domain in domain_labels:
        gt = ground_truth.get(domain)
        if gt is None:
            result.append(None)
        elif gt.actor:
            result.append(gt.actor)
        elif gt.family:
            result.append(gt.family)
        else:
            result.append("shared_infra")
    return result


def evaluate_clustering(
    result: ClusterResult,
    matrix: np.ndarray,
    ground_truth: dict[str, GroundTruthLabel] | None = None,
) -> ClusterEvaluation:
    labels = result.labels
    n = len(labels)
    non_noise_mask = labels != -1
    non_noise_count = int(np.sum(non_noise_mask))

    unique_clusters = set(labels[non_noise_mask])
    n_clusters = len(unique_clusters)

    sil = None
    if n_clusters >= 2 and non_noise_count >= 2:
        try:
            sub_matrix = matrix[non_noise_mask][:, non_noise_mask]
            sil = float(silhouette_score(sub_matrix, labels[non_noise_mask], metric="precomputed"))
        except Exception:
            pass

    cluster_sizes = sorted(
        [int(np.sum(labels == c)) for c in unique_clusters],
        reverse=True,
    )

    ari_overall = None
    ari_actor = None
    ari_family = None
    purity = None

    if ground_truth and n_clusters > 0:
        true_labels = _build_true_labels(result.domain_labels, ground_truth)

        valid_mask = np.array([
            non_noise_mask[i] and true_labels[i] is not None
            for i in range(n)
        ])
        if np.sum(valid_mask) >= 2:
            ari_overall = float(adjusted_rand_score(
                [true_labels[i] for i in range(n) if valid_mask[i]],
                labels[valid_mask],
            ))

        _gt_default = GroundTruthLabel(None, None, "", False)
        actor_mask = np.array([
            non_noise_mask[i] and true_labels[i] is not None
            and ground_truth.get(result.domain_labels[i], _gt_default).group == "actor_attribution"
            for i in range(n)
        ])
        if np.sum(actor_mask) >= 2:
            ari_actor = float(adjusted_rand_score(
                [true_labels[i] for i in range(n) if actor_mask[i]],
                labels[actor_mask],
            ))

        family_mask = np.array([
            non_noise_mask[i] and true_labels[i] is not None
            and ground_truth.get(result.domain_labels[i], _gt_default).group == "family_attribution"
            for i in range(n)
        ])
        if np.sum(family_mask) >= 2:
            ari_family = float(adjusted_rand_score(
                [true_labels[i] for i in range(n) if family_mask[i]],
                labels[family_mask],
            ))

        purity_scores: list[tuple[float, int]] = []
        for c in unique_clusters:
            c_mask = labels == c
            c_true = [true_labels[i] for i in range(n) if c_mask[i] and true_labels[i] is not None]
            if c_true:
                most_common_count = Counter(c_true).most_common(1)[0][1]
                purity_scores.append((most_common_count / len(c_true), len(c_true)))
        if purity_scores:
            total_weighted = sum(size for _, size in purity_scores)
            purity = round(
                sum(p * size for p, size in purity_scores) / total_weighted,
                4,
            ) if total_weighted > 0 else None

    return ClusterEvaluation(
        silhouette=round(sil, 4) if sil is not None else None,
        ari_overall=round(ari_overall, 4) if ari_overall is not None else None,
        ari_actor_group=round(ari_actor, 4) if ari_actor is not None else None,
        ari_family_group=round(ari_family, 4) if ari_family is not None else None,
        n_clusters=n_clusters,
        n_noise=int(np.sum(labels == -1)),
        noise_ratio=round(int(np.sum(labels == -1)) / n, 4) if n > 0 else 0.0,
        cluster_sizes=cluster_sizes,
        cluster_purity=purity,
    )


# ---------------------------------------------------------------------------
# Parameter sweep
# ---------------------------------------------------------------------------

def sweep_dbscan(
    matrix: np.ndarray,
    domain_labels: list[str],
    ground_truth: dict[str, GroundTruthLabel] | None,
    eps_values: list[float],
    min_samples_values: list[int] | None = None,
    enrichments: list[DomainEnrichment] | None = None,
    quality_threshold: float = 0.40,
) -> list[SweepResult]:
    from cti_agent.clustering.quality import filter_clusters_by_structural_quality

    if min_samples_values is None:
        min_samples_values = [2, 3, 5]
    results: list[SweepResult] = []
    total = len(eps_values) * len(min_samples_values)
    for i, eps in enumerate(eps_values):
        for j, ms in enumerate(min_samples_values):
            cr = run_dbscan(matrix, eps=eps, min_samples=ms, domain_labels=domain_labels)
            ev = evaluate_clustering(cr, matrix, ground_truth)

            post_ev = None
            if enrichments is not None and cr.n_clusters > 0:
                filtered_labels, _ = filter_clusters_by_structural_quality(
                    cr.labels, enrichments, matrix, threshold=quality_threshold,
                )
                filtered_cr = ClusterResult(
                    labels=filtered_labels, algorithm=cr.algorithm, params=cr.params,
                    n_clusters=len(set(filtered_labels)) - (1 if -1 in filtered_labels else 0),
                    n_noise=int(np.sum(filtered_labels == -1)),
                    noise_ratio=round(int(np.sum(filtered_labels == -1)) / len(filtered_labels), 4),
                    domain_labels=domain_labels,
                )
                post_ev = evaluate_clustering(filtered_cr, matrix, ground_truth)

            results.append(SweepResult(
                algorithm="dbscan", params={"eps": eps, "min_samples": ms},
                evaluation=ev, post_filter_evaluation=post_ev,
            ))
            idx = i * len(min_samples_values) + j + 1
            if idx % 10 == 0 or idx == total:
                logger.info("[DBSCAN sweep %d/%d] eps=%.3f ms=%d → %d clusters, noise=%.1f%%",
                            idx, total, eps, ms, ev.n_clusters, ev.noise_ratio * 100)
    return results


def sweep_hdbscan(
    matrix: np.ndarray,
    domain_labels: list[str],
    ground_truth: dict[str, GroundTruthLabel] | None,
    min_cluster_size_values: list[int] | None = None,
    min_samples_values: list[int] | None = None,
    enrichments: list[DomainEnrichment] | None = None,
    quality_threshold: float = 0.20,
) -> list[SweepResult]:
    from cti_agent.clustering.quality import filter_clusters_by_structural_quality

    if min_cluster_size_values is None:
        min_cluster_size_values = [3, 5, 7, 9, 11, 13, 15]
    if min_samples_values is None:
        min_samples_values = [2, 3, 5]
    results: list[SweepResult] = []
    total = len(min_cluster_size_values) * len(min_samples_values)
    for i, mcs in enumerate(min_cluster_size_values):
        for j, ms in enumerate(min_samples_values):
            cr = run_hdbscan(matrix, min_cluster_size=mcs, min_samples=ms, domain_labels=domain_labels)
            ev = evaluate_clustering(cr, matrix, ground_truth)

            post_ev = None
            if enrichments is not None and cr.n_clusters > 0:
                filtered_labels, _ = filter_clusters_by_structural_quality(
                    cr.labels, enrichments, matrix, threshold=quality_threshold,
                )
                filtered_cr = ClusterResult(
                    labels=filtered_labels, algorithm=cr.algorithm, params=cr.params,
                    n_clusters=len(set(filtered_labels)) - (1 if -1 in filtered_labels else 0),
                    n_noise=int(np.sum(filtered_labels == -1)),
                    noise_ratio=round(int(np.sum(filtered_labels == -1)) / len(filtered_labels), 4),
                    domain_labels=domain_labels,
                )
                post_ev = evaluate_clustering(filtered_cr, matrix, ground_truth)

            results.append(SweepResult(
                algorithm="hdbscan", params={"min_cluster_size": mcs, "min_samples": ms},
                evaluation=ev, post_filter_evaluation=post_ev,
            ))
            idx = i * len(min_samples_values) + j + 1
            if idx % 10 == 0 or idx == total:
                logger.info("[HDBSCAN sweep %d/%d] mcs=%d ms=%d → %d clusters, noise=%.1f%%",
                            idx, total, mcs, ms, ev.n_clusters, ev.noise_ratio * 100)
    return results


def find_best_params(
    sweep_results: list[SweepResult],
    metric: str = "silhouette",
) -> SweepResult | None:
    valid = [r for r in sweep_results if getattr(r.evaluation, metric) is not None]
    if not valid:
        return None
    return max(valid, key=lambda r: getattr(r.evaluation, metric))


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def save_cluster_result(
    result: ClusterResult,
    evaluation: ClusterEvaluation,
    output_dir: Path,
    ground_truth: dict[str, GroundTruthLabel] | None = None,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    assignments = []
    for i, domain in enumerate(result.domain_labels):
        entry: dict[str, Any] = {
            "domain": domain,
            "cluster_id": int(result.labels[i]),
        }
        if ground_truth:
            gt = ground_truth.get(domain)
            if gt:
                entry["ground_truth_actor"] = gt.actor
                entry["ground_truth_family"] = gt.family
                entry["group"] = gt.group
        assignments.append(entry)

    (output_dir / "cluster_assignments.json").write_text(
        json.dumps(assignments, indent=2), encoding="utf-8",
    )

    metadata = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "algorithm": result.algorithm,
        "params": result.params,
        "evaluation": asdict(evaluation),
        "domain_count": len(result.domain_labels),
    }
    (output_dir / "cluster_metadata.json").write_text(
        json.dumps(metadata, indent=2, default=str), encoding="utf-8",
    )
    logger.info("Cluster results saved to %s", output_dir)


def save_sweep_report(
    sweep_results: list[SweepResult],
    output_dir: Path,
    algorithm: str,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    report = []
    for r in sweep_results:
        entry: dict[str, Any] = {
            "algorithm": r.algorithm,
            "params": r.params,
            "evaluation": asdict(r.evaluation),
        }
        if r.post_filter_evaluation is not None:
            entry["post_filter_evaluation"] = asdict(r.post_filter_evaluation)
        report.append(entry)
    path = output_dir / f"sweep_report_{algorithm}.json"
    path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    logger.info("Sweep report (%d configs) saved to %s", len(report), path)
