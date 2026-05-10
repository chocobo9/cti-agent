"""Incident similarity graph construction for campaign discovery.

Builds a weighted undirected graph where vertices are incidents with
non-empty cluster_tag_sets, and edges connect incidents with Jaccard
similarity > θ_min within a time window.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import igraph as ig

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IncidentRecord:
    incident_id: str
    date: date
    cluster_tag_set: frozenset[int]
    domain_count: int


def load_incidents(path: Path) -> list[IncidentRecord]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    records = []
    for entry in raw:
        d = entry.get("date")
        try:
            inc_date = date.fromisoformat(d[:10]) if d else date(2020, 1, 1)
        except (ValueError, TypeError):
            inc_date = date(2020, 1, 1)
        records.append(IncidentRecord(
            incident_id=entry["incident_id"],
            date=inc_date,
            cluster_tag_set=frozenset(entry.get("cluster_tag_set", [])),
            domain_count=entry.get("domain_count", 0),
        ))
    return records


def jaccard_similarity(set_a: frozenset[int], set_b: frozenset[int]) -> float:
    if not set_a and not set_b:
        return 0.0
    union = set_a | set_b
    if not union:
        return 0.0
    return len(set_a & set_b) / len(union)


def build_similarity_graph(
    incidents: list[IncidentRecord],
    theta_min: float = 0.1,
    time_window_days: int = 90,
    no_time_filter: bool = False,
) -> tuple[ig.Graph, list[IncidentRecord]]:
    """Build incident similarity graph.

    Returns (graph, eligible_incidents) where eligible_incidents are the
    incidents with non-empty cluster_tag_sets that became graph vertices.
    Vertex attribute 'incident_id' maps back to the IncidentRecord.
    """
    eligible = [inc for inc in incidents if inc.cluster_tag_set]
    n = len(eligible)

    g = ig.Graph(n, directed=False)
    g.vs["incident_id"] = [inc.incident_id for inc in eligible]
    g.vs["date"] = [inc.date.isoformat() for inc in eligible]

    edges: list[tuple[int, int]] = []
    weights: list[float] = []
    filtered_by_time = 0
    filtered_by_theta = 0

    for i in range(n):
        for j in range(i + 1, n):
            sim = jaccard_similarity(eligible[i].cluster_tag_set, eligible[j].cluster_tag_set)
            if sim <= theta_min:
                filtered_by_theta += 1
                continue
            if not no_time_filter:
                day_diff = abs((eligible[i].date - eligible[j].date).days)
                if day_diff > time_window_days:
                    filtered_by_time += 1
                    continue
            edges.append((i, j))
            weights.append(sim)

    g.add_edges(edges)
    g.es["weight"] = weights

    logger.info(
        "Similarity graph: %d vertices, %d edges (filtered: %d by theta, %d by time)",
        n, len(edges), filtered_by_theta, filtered_by_time,
    )
    return g, eligible
