"""Verification script for Chainlit migration.

Tests 7 scenarios using the same code path as app_chainlit.py:
graph.ainvoke({"query": user_text}) — user's original text, no template rewrites.

Usage::

    cd cti-agent
    python -m scripts.verify_chainlit_migration
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(env_path)

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


async def run_query(graph, query: str, label: str) -> dict | None:
    print(f"\n{'='*70}")
    print(f"[{label}] Input: {query!r}")
    print(f"{'='*70}")

    try:
        state = await graph.ainvoke({"query": query})
    except Exception as exc:
        print(f"  ERROR: {type(exc).__name__}: {exc}")
        return None

    preserved = state.get("query")
    print(f"  state[\"query\"] = {preserved!r}")
    print(f"  QUERY PRESERVED: {preserved == query}")

    query_type = state.get("query_type", "?")
    # Extract intent from evidence_chain (original analysis preserved there;
    # _routing_decision gets overwritten by evidence_eval Round 2)
    intent = "?"
    for entry in state.get("evidence_chain", []):
        if entry.startswith("Query analyzed: intent="):
            intent = entry.split("intent=")[1].split(",")[0]
            break
    print(f"  intent={intent}, query_type={query_type}")

    confidence = state.get("confidence", 0)
    candidates = state.get("candidate_actors", [])
    enrichment_suggested = state.get("enrichment_suggested", False)
    actor_names = [c.get("actor_name", "?") for c in candidates]
    print(f"  confidence={confidence}, actors={actor_names}")
    print(f"  enrichment_suggested={enrichment_suggested}")

    report_data = state.get("attribution_report")
    if report_data:
        from cti_agent.agent.nodes.report import AttributionReport

        report = AttributionReport(**report_data)
        print(f"  report.attribution_result={report.attribution_result}")
        if report.primary_actor:
            print(f"  report.primary_actor={report.primary_actor}")

    return state


async def main():
    from cti_agent.agent.graph import compile_attribution_graph

    print("Compiling attribution graph...")
    graph = compile_attribution_graph()
    print("Graph compiled.\n")

    results = {}

    # 1. Domain attribution — structural route, expect Gamaredon
    results["1"] = await run_query(
        graph, "hamadryas.online", "1: Domain attribution"
    )

    # 2. General CTI query — semantic route, no attribution pipeline needed
    results["2"] = await run_query(
        graph, "什么组织擅长供应链攻击", "2: General CTI (Chinese)"
    )

    # 3. Mixed query — behavioral description + mentioned actors
    results["3"] = await run_query(
        graph,
        "evil.com 用了 DGA 模式，跟 Gamaredon 的手法很像",
        "3: Mixed query (Chinese)",
    )

    # 4. Domain not in DB — enrichment_suggested=true
    results["4"] = await run_query(
        graph, "notarealdomainabc123.com", "4: Unknown domain"
    )

    # 5. Actor investigation — structural route
    results["5"] = await run_query(
        graph, "FIN7 最近有什么活动", "5: Actor investigation (Chinese)"
    )

    # 6. Reverse IP lookup — structural route
    results["6"] = await run_query(
        graph, "89.108.83.235 这个IP背后是谁", "6: Reverse IP (Chinese)"
    )

    # 7. English behavioral query with domain
    results["7"] = await run_query(
        graph,
        "photopoststories.com uses spear-phishing with macro-enabled docs targeting government agencies",
        "7: English mixed with behavioral description",
    )

    # Summary
    print(f"\n{'='*70}")
    print("VERIFICATION SUMMARY")
    print(f"{'='*70}")
    all_preserved = True
    for label, state in results.items():
        if state is None:
            print(f"  [{label}] FAILED — pipeline error")
            all_preserved = False
        else:
            preserved = state.get("query") == {
                "1": "hamadryas.online",
                "2": "什么组织擅长供应链攻击",
                "3": "evil.com 用了 DGA 模式，跟 Gamaredon 的手法很像",
                "4": "notarealdomainabc123.com",
                "5": "FIN7 最近有什么活动",
                "6": "89.108.83.235 这个IP背后是谁",
                "7": "photopoststories.com uses spear-phishing with macro-enabled docs targeting government agencies",
            }[label]
            status = "PASS" if preserved else "FAIL"
            if not preserved:
                all_preserved = False
            intent = "?"
            for entry in state.get("evidence_chain", []):
                if entry.startswith("Query analyzed: intent="):
                    intent = entry.split("intent=")[1].split(",")[0]
                    break
            qt = state.get("query_type", "?")
            print(f"  [{label}] query_preserved={status}, intent={intent}, query_type={qt}")

    print(f"\n  ALL QUERIES PRESERVED: {all_preserved}")


if __name__ == "__main__":
    asyncio.run(main())
