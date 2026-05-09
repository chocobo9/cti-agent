"""End-to-end attribution evaluation against ground truth.

Loads ~635 GROUND_TRUTH_ATTRIBUTION edges from Neo4j, runs the attribution
pipeline on each domain, and computes precision/recall/F1 at top-k.

Usage::

    python -u scripts/eval_attribution.py --sample 10 --delay 3
    python -u scripts/eval_attribution.py --entity-type threat_actor --sample 20
    python -u scripts/eval_attribution.py --concurrency 3 --output-dir data/eval

Estimated runtime: ~60s/domain × 635 domains = ~11h full run.
Use --sample for development iteration.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import logging
import os
import random
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from rapidfuzz import fuzz

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

_FUZZY_THRESHOLD = 85


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class GroundTruth:
    domain: str
    actor: str
    entity_type: str


@dataclass
class EvalResult:
    domain: str
    expected_actors: list[str]
    entity_type: str
    predicted_actors: list[dict] = field(default_factory=list)
    confidence: float = 0.0
    attribution_result: str = ""
    iterations: int = 0
    error: str | None = None
    wall_seconds: float = 0.0
    top1_match: bool = False
    top3_match: bool = False
    top5_match: bool = False
    matched_source: str | None = None


# ---------------------------------------------------------------------------
# Step 1: Load ground truth from Neo4j
# ---------------------------------------------------------------------------


def load_ground_truth(entity_type: str | None = None) -> list[GroundTruth]:
    from cti_agent.graph.client import Neo4jClient
    from cti_agent.graph.config import get_settings

    query = """
    MATCH (d:Domain)-[r:GROUND_TRUTH_ATTRIBUTION]->(a:Actor)
    RETURN d.name AS domain, a.name AS actor, a.entity_type AS entity_type
    """
    settings = get_settings()
    with Neo4jClient(settings) as client:
        rows = client.execute_read(query)

    gt_list = [
        GroundTruth(
            domain=r["domain"],
            actor=r["actor"],
            entity_type=r.get("entity_type") or "unknown",
        )
        for r in rows
        if r.get("domain") and r.get("actor")
    ]

    if entity_type:
        gt_list = [g for g in gt_list if g.entity_type == entity_type]

    logger.info("Loaded %d ground truth edges (%s)", len(gt_list), entity_type or "all")
    return gt_list


def group_by_domain(gt_list: list[GroundTruth]) -> dict[str, list[GroundTruth]]:
    groups: dict[str, list[GroundTruth]] = defaultdict(list)
    for g in gt_list:
        groups[g.domain].append(g)
    return dict(groups)


# ---------------------------------------------------------------------------
# Step 2: Run attribution pipeline
# ---------------------------------------------------------------------------


async def run_attribution(domain: str) -> dict[str, Any]:
    from cti_agent.agent.graph import compile_attribution_graph
    from cti_agent.agent.nodes.report import AttributionReport

    graph = compile_attribution_graph()
    state = await graph.ainvoke({"query": f"Who is behind {domain}?"})

    report_data = state.get("attribution_report") or {}
    return {
        "candidate_actors": report_data.get("candidate_actors", []),
        "confidence": report_data.get("confidence", 0.0),
        "attribution_result": report_data.get("attribution_result", ""),
        "iterations": report_data.get("iterations_performed", 0),
        "enrichment_suggested": report_data.get("enrichment_suggested", False),
    }


def _fuzzy_match(predicted: str, expected: str) -> bool:
    if predicted.lower() == expected.lower():
        return True
    return fuzz.ratio(predicted.lower(), expected.lower()) >= _FUZZY_THRESHOLD


def evaluate_one(
    domain: str,
    expected_actors: list[str],
    entity_type: str,
    pipeline_result: dict[str, Any],
    error: str | None,
    wall_seconds: float,
) -> EvalResult:
    result = EvalResult(
        domain=domain,
        expected_actors=expected_actors,
        entity_type=entity_type,
        error=error,
        wall_seconds=wall_seconds,
    )

    if error:
        return result

    candidates = pipeline_result.get("candidate_actors", [])
    result.predicted_actors = candidates
    result.confidence = pipeline_result.get("confidence", 0.0)
    result.attribution_result = pipeline_result.get("attribution_result", "")
    result.iterations = pipeline_result.get("iterations", 0)

    for k, attr in [(1, "top1_match"), (3, "top3_match"), (5, "top5_match")]:
        top_k_names = [c.get("actor_name", "") for c in candidates[:k]]
        matched = any(
            _fuzzy_match(pred, exp)
            for pred in top_k_names
            for exp in expected_actors
        )
        setattr(result, attr, matched)

    if result.top1_match and candidates:
        result.matched_source = candidates[0].get("source", "unknown")

    return result


async def run_eval_batch(
    domain_groups: dict[str, list[GroundTruth]],
    concurrency: int = 1,
    delay: float = 3.0,
) -> list[EvalResult]:
    try:
        from tqdm import tqdm
    except ImportError:
        tqdm = None

    domains = list(domain_groups.keys())
    results: list[EvalResult] = []
    semaphore = asyncio.Semaphore(concurrency)

    async def _process(domain: str) -> EvalResult:
        async with semaphore:
            gts = domain_groups[domain]
            expected_actors = list({g.actor for g in gts})
            entity_type = gts[0].entity_type

            t0 = time.monotonic()
            error = None
            pipeline_result: dict[str, Any] = {}
            try:
                pipeline_result = await run_attribution(domain)
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
                logger.warning("Pipeline error for %s: %s", domain, error)
            elapsed = time.monotonic() - t0

            if delay > 0:
                await asyncio.sleep(delay)

            return evaluate_one(
                domain, expected_actors, entity_type,
                pipeline_result, error, elapsed,
            )

    if tqdm and concurrency == 1:
        pbar = tqdm(total=len(domains), desc="Evaluating", unit="domain")
        for domain in domains:
            r = await _process(domain)
            results.append(r)
            status = "HIT" if r.top1_match else ("ERR" if r.error else "MISS")
            pbar.set_postfix_str(f"{domain[:25]} → {status} ({r.confidence:.2f})")
            pbar.update(1)
        pbar.close()
    elif concurrency > 1:
        logger.info("Running with concurrency=%d", concurrency)
        tasks = [_process(d) for d in domains]
        if tqdm:
            for coro in tqdm(
                asyncio.as_completed(tasks),
                total=len(tasks),
                desc="Evaluating",
                unit="domain",
            ):
                results.append(await coro)
        else:
            results = await asyncio.gather(*tasks)
    else:
        for i, domain in enumerate(domains):
            r = await _process(domain)
            results.append(r)
            logger.info("[%d/%d] %s → %s (conf=%.2f, %.1fs)",
                        i + 1, len(domains), domain,
                        "HIT" if r.top1_match else "MISS",
                        r.confidence, r.wall_seconds)

    return results


# ---------------------------------------------------------------------------
# Step 3: Compute metrics
# ---------------------------------------------------------------------------


def compute_metrics(results: list[EvalResult]) -> dict[str, Any]:
    total = len(results)
    errors = [r for r in results if r.error]
    no_pred = [r for r in results if not r.error and not r.predicted_actors]
    with_pred = [r for r in results if not r.error and r.predicted_actors]

    top1_correct = sum(1 for r in results if r.top1_match)
    top3_correct = sum(1 for r in results if r.top3_match)
    top5_correct = sum(1 for r in results if r.top5_match)

    precision = top1_correct / len(with_pred) if with_pred else 0
    recall = top1_correct / total if total else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0

    correct_confs = [r.confidence for r in results if r.top1_match]
    incorrect_confs = [r.confidence for r in with_pred if not r.top1_match]

    source_counts = Counter(r.matched_source for r in results if r.top1_match and r.matched_source)

    by_type: dict[str, dict[str, Any]] = {}
    for etype in ("threat_actor", "malware_family"):
        subset = [r for r in results if r.entity_type == etype]
        if subset:
            t1 = sum(1 for r in subset if r.top1_match)
            wp = [r for r in subset if not r.error and r.predicted_actors]
            by_type[etype] = {
                "total": len(subset),
                "top1_correct": t1,
                "top1_precision": t1 / len(wp) if wp else 0,
                "top1_recall": t1 / len(subset) if subset else 0,
            }

    return {
        "total_domains": total,
        "errors": len(errors),
        "no_prediction": len(no_pred),
        "with_prediction": len(with_pred),
        "top1_correct": top1_correct,
        "top3_correct": top3_correct,
        "top5_correct": top5_correct,
        "top1_precision": round(precision, 4),
        "top1_recall": round(recall, 4),
        "top1_f1": round(f1, 4),
        "top3_accuracy": round(top3_correct / total, 4) if total else 0,
        "top5_accuracy": round(top5_correct / total, 4) if total else 0,
        "mean_confidence_correct": round(sum(correct_confs) / len(correct_confs), 3) if correct_confs else None,
        "mean_confidence_incorrect": round(sum(incorrect_confs) / len(incorrect_confs), 3) if incorrect_confs else None,
        "error_rate": round(len(errors) / total, 4) if total else 0,
        "no_prediction_rate": round(len(no_pred) / total, 4) if total else 0,
        "source_distribution": dict(source_counts),
        "by_entity_type": by_type,
    }


# ---------------------------------------------------------------------------
# Step 4: Output
# ---------------------------------------------------------------------------


def save_results(
    results: list[EvalResult],
    metrics: dict[str, Any],
    output_dir: Path,
) -> tuple[Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    detail_path = output_dir / f"attribution_eval_{ts}.json"
    detail_data = {
        "timestamp": ts,
        "metrics": metrics,
        "results": [
            {
                "domain": r.domain,
                "expected_actors": r.expected_actors,
                "entity_type": r.entity_type,
                "predicted_actors": r.predicted_actors,
                "confidence": r.confidence,
                "attribution_result": r.attribution_result,
                "iterations": r.iterations,
                "top1_match": r.top1_match,
                "top3_match": r.top3_match,
                "top5_match": r.top5_match,
                "matched_source": r.matched_source,
                "error": r.error,
                "wall_seconds": round(r.wall_seconds, 1),
            }
            for r in results
        ],
    }
    with open(detail_path, "w", encoding="utf-8") as f:
        json.dump(detail_data, f, indent=2, ensure_ascii=False, default=str)

    summary_path = output_dir / f"attribution_eval_summary_{ts}.csv"
    with open(summary_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["metric", "value"])
        for k, v in metrics.items():
            if isinstance(v, dict):
                for sub_k, sub_v in v.items():
                    writer.writerow([f"{k}.{sub_k}", sub_v])
            else:
                writer.writerow([k, v])

    confusion_path = output_dir / f"confusion_matrix_{ts}.csv"
    pairs: list[tuple[str, str]] = []
    for r in results:
        predicted = r.predicted_actors[0].get("actor_name", "(none)") if r.predicted_actors else "(none)"
        for exp in r.expected_actors:
            pairs.append((exp, predicted))
    actor_set = sorted({a for p in pairs for a in p})
    matrix: dict[str, Counter] = {a: Counter() for a in actor_set}
    for exp, pred in pairs:
        matrix[exp][pred] += 1
    with open(confusion_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["expected \\ predicted"] + actor_set)
        for exp in actor_set:
            writer.writerow([exp] + [matrix[exp].get(a, 0) for a in actor_set])

    return detail_path, summary_path, confusion_path


def print_summary(metrics: dict[str, Any]) -> None:
    print("\n" + "=" * 60)
    print("ATTRIBUTION EVALUATION RESULTS")
    print("=" * 60)

    print(f"\nDomains evaluated: {metrics['total_domains']}")
    print(f"  With predictions: {metrics['with_prediction']}")
    print(f"  No prediction:    {metrics['no_prediction']} ({metrics['no_prediction_rate']:.1%})")
    print(f"  Errors:           {metrics['errors']} ({metrics['error_rate']:.1%})")

    print(f"\nTop-1 Precision: {metrics['top1_precision']:.4f}")
    print(f"Top-1 Recall:    {metrics['top1_recall']:.4f}")
    print(f"Top-1 F1:        {metrics['top1_f1']:.4f}")
    print(f"Top-3 Accuracy:  {metrics['top3_accuracy']:.4f}")
    print(f"Top-5 Accuracy:  {metrics['top5_accuracy']:.4f}")

    if metrics["mean_confidence_correct"] is not None:
        print(f"\nMean confidence (correct):   {metrics['mean_confidence_correct']:.3f}")
    if metrics["mean_confidence_incorrect"] is not None:
        print(f"Mean confidence (incorrect): {metrics['mean_confidence_incorrect']:.3f}")

    if metrics["source_distribution"]:
        print("\nSource distribution (correct attributions):")
        for src, count in sorted(metrics["source_distribution"].items()):
            print(f"  {src}: {count}")

    if metrics.get("by_entity_type"):
        print("\nBy entity type:")
        for etype, vals in metrics["by_entity_type"].items():
            print(f"  {etype}: {vals['top1_correct']}/{vals['total']} "
                  f"(P={vals['top1_precision']:.3f}, R={vals['top1_recall']:.3f})")


# ---------------------------------------------------------------------------
# Step 5: LangSmith integration (optional)
# ---------------------------------------------------------------------------


def upload_to_langsmith(
    gt_groups: dict[str, list[GroundTruth]],
    results: list[EvalResult],
) -> None:
    try:
        from langsmith import Client
    except ImportError:
        logger.info("langsmith not installed, skipping upload")
        return

    if not os.environ.get("LANGSMITH_API_KEY"):
        logger.info("LANGSMITH_API_KEY not set, skipping upload")
        return

    client = Client()

    dataset_name = "cti-attribution-ground-truth"
    try:
        dataset = client.create_dataset(
            dataset_name,
            description="Ground truth domain→actor pairs for attribution evaluation",
        )
    except Exception:
        datasets = list(client.list_datasets(dataset_name=dataset_name))
        dataset = datasets[0] if datasets else None
        if not dataset:
            logger.warning("Could not create or find LangSmith dataset")
            return

    result_map = {r.domain: r for r in results}
    for domain, gts in gt_groups.items():
        r = result_map.get(domain)
        try:
            client.create_example(
                inputs={"domain": domain},
                outputs={
                    "expected_actor": gts[0].actor,
                    "entity_type": gts[0].entity_type,
                    "top1_match": r.top1_match if r else None,
                    "predicted_actor": r.predicted_actors[0].get("actor_name") if r and r.predicted_actors else None,
                    "confidence": r.confidence if r else None,
                },
                dataset_id=dataset.id,
            )
        except Exception:
            pass

    logger.info("Uploaded %d examples to LangSmith dataset '%s'", len(gt_groups), dataset_name)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate attribution pipeline against ground truth")
    parser.add_argument("--sample", type=int, default=None, help="Random sample size (default: all)")
    parser.add_argument("--output-dir", type=Path, default=Path("data/eval"), help="Output directory")
    parser.add_argument("--delay", type=float, default=3.0, help="Delay between queries in seconds")
    parser.add_argument("--concurrency", type=int, default=1, help="Concurrent queries (max 5)")
    parser.add_argument("--entity-type", choices=["threat_actor", "malware_family"], default=None, help="Filter by entity type")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for sampling")
    parser.add_argument("--upload-langsmith", action="store_true", help="Upload results to LangSmith")
    args = parser.parse_args()

    args.concurrency = min(args.concurrency, 5)

    gt_list = load_ground_truth(entity_type=args.entity_type)
    gt_groups = group_by_domain(gt_list)
    logger.info("Unique domains: %d", len(gt_groups))

    if args.sample and args.sample < len(gt_groups):
        random.seed(args.seed)
        sampled_keys = random.sample(list(gt_groups.keys()), args.sample)
        gt_groups = {k: gt_groups[k] for k in sampled_keys}
        logger.info("Sampled %d domains (seed=%d)", args.sample, args.seed)

    total_start = time.monotonic()
    results = asyncio.run(
        run_eval_batch(gt_groups, concurrency=args.concurrency, delay=args.delay)
    )
    total_elapsed = time.monotonic() - total_start

    metrics = compute_metrics(results)
    metrics["total_wall_seconds"] = round(total_elapsed, 1)
    metrics["avg_seconds_per_domain"] = round(total_elapsed / len(results), 1) if results else 0

    print_summary(metrics)

    detail_path, summary_path, confusion_path = save_results(results, metrics, args.output_dir)
    print(f"\nDetailed results: {detail_path}")
    print(f"Summary CSV:      {summary_path}")
    print(f"Confusion matrix: {confusion_path}")
    print(f"Total wall time:  {total_elapsed:.0f}s ({total_elapsed/60:.1f} min)")

    if args.upload_langsmith:
        upload_to_langsmith(gt_groups, results)


if __name__ == "__main__":
    main()
