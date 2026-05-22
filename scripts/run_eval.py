"""Run full evaluation against eval_query_set_4pattern.json.

Usage:
    cd cti-agent
    python -u scripts/run_eval.py
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.WARNING, format="%(name)s %(message)s")
logging.getLogger("cti_agent.agent.nodes.evidence_eval").setLevel(logging.INFO)

from cti_agent.agent.graph import compile_attribution_graph
from cti_agent.agent.nodes.report import AttributionReport, render_report_markdown


EVAL_PATH = Path(__file__).parent.parent / "help" / "eval_query_set_4pattern.json"


async def run_one(graph, case: dict) -> dict:
    qid = case["id"]
    query = case["query"]
    gt_actor = case.get("ground_truth_actor")
    gt_type = case.get("ground_truth_type", "")
    pattern = case.get("pattern", "")

    print(f"\n{'='*70}")
    print(f"[{qid}] pattern={pattern} | {query}")
    print(f"  ground_truth: {gt_actor} ({gt_type})")
    print("-" * 70)

    t0 = time.monotonic()
    try:
        state = await graph.ainvoke({"query": query})
    except Exception as exc:
        elapsed = time.monotonic() - t0
        print(f"  ERROR: {exc}")
        return {
            "id": qid, "pattern": pattern, "query": query,
            "ground_truth": gt_actor, "gt_type": gt_type,
            "status": "ERROR", "error": str(exc),
            "wall_seconds": round(elapsed, 1),
        }
    elapsed = time.monotonic() - t0

    report_data = state.get("attribution_report")
    if not report_data:
        print(f"  NO REPORT")
        return {
            "id": qid, "pattern": pattern, "query": query,
            "ground_truth": gt_actor, "gt_type": gt_type,
            "status": "NO_REPORT", "wall_seconds": round(elapsed, 1),
        }

    report = AttributionReport(**report_data)

    primary = report.primary_actor or "-"
    conf = report.confidence
    iters = report.iterations_performed
    route = report.query_type
    shared = report.is_shared_infrastructure
    candidates = [a.get("actor_name", "?") for a in report.candidate_actors]

    hit = False
    if isinstance(gt_actor, list):
        hit = any(g == primary for g in gt_actor) or any(g in candidates for g in gt_actor)
    elif gt_actor:
        hit = (primary == gt_actor)
    else:
        hit = conf < 0.3

    partial = False
    if not hit and gt_actor:
        if isinstance(gt_actor, list):
            partial = any(g in candidates for g in gt_actor)
        else:
            partial = gt_actor in candidates

    status = "HIT" if hit else ("PARTIAL" if partial else "MISS")

    print(f"  Result: {status} | primary={primary} | conf={conf:.3f} | route={route}")
    print(f"  Candidates: {candidates}")
    print(f"  Shared infra: {shared} | Iterations: {iters}")
    print(f"  Wall time: {elapsed:.1f}s")

    return {
        "id": qid, "pattern": pattern, "query": query,
        "ground_truth": gt_actor, "gt_type": gt_type,
        "status": status,
        "primary_actor": primary,
        "candidates": candidates,
        "confidence": round(conf, 3),
        "route": route,
        "iterations": iters,
        "shared_infra": shared,
        "wall_seconds": round(elapsed, 1),
    }


async def main():
    with open(EVAL_PATH, encoding="utf-8") as f:
        cases = json.load(f)

    print("=" * 70)
    print(f"EVAL: {len(cases)} queries from {EVAL_PATH.name}")
    print("=" * 70)
    print("Compiling attribution graph...")
    graph = compile_attribution_graph()

    total_start = time.monotonic()
    results = []
    for case in cases:
        r = await run_one(graph, case)
        results.append(r)

    total_elapsed = time.monotonic() - total_start

    print(f"\n{'='*70}")
    print("SUMMARY")
    print("=" * 70)
    print(f"{'#':<4} {'Pattern':<14} {'Status':<6} {'Conf':<7} {'Route':<12} {'Primary':<25} {'GT':<25} {'Time':>7}")
    print("-" * 105)

    for r in results:
        gt = str(r.get("ground_truth", "-"))[:24]
        primary = r.get("primary_actor", "-")[:24]
        conf = f"{r['confidence']:.3f}" if "confidence" in r else "N/A"
        route = r.get("route", "N/A")
        time_str = f"{r['wall_seconds']:.1f}s"
        print(f"{r['id']:<4} {r['pattern']:<14} {r['status']:<6} {conf:<7} {route:<12} {primary:<25} {gt:<25} {time_str:>7}")

    hits = sum(1 for r in results if r["status"] == "HIT")
    total = len(results)
    print(f"\nHit rate: {hits}/{total} ({hits/total*100:.0f}%)")
    print(f"Total wall time: {total_elapsed:.1f}s ({total_elapsed/60:.1f} min)")

    report_dir = Path("data/reports")
    report_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_path = report_dir / f"eval_4pattern_{ts}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": ts,
            "total_queries": total,
            "hits": hits,
            "hit_rate": round(hits / total, 3),
            "total_wall_seconds": round(total_elapsed, 1),
            "results": results,
        }, f, indent=2, ensure_ascii=False, default=str)
    print(f"Results saved to: {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
