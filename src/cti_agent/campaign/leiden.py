"""Leiden community detection wrapper with stability protocol.

Wraps the leidenalg package to provide a clean interface with
10-run median modularity selection for deterministic results.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import igraph as ig
import leidenalg

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LeidenResult:
    membership: list[int]
    modularity: float
    n_communities: int
    community_sizes: list[int]


def run_leiden(
    graph: ig.Graph,
    resolution: float = 1.0,
    seed: int | None = None,
) -> LeidenResult:
    if graph.vcount() == 0:
        return LeidenResult(membership=[], modularity=0.0, n_communities=0, community_sizes=[])

    if graph.ecount() == 0:
        membership = list(range(graph.vcount()))
        return LeidenResult(
            membership=membership,
            modularity=0.0,
            n_communities=graph.vcount(),
            community_sizes=[1] * graph.vcount(),
        )

    partition = leidenalg.find_partition(
        graph,
        leidenalg.RBConfigurationVertexPartition,
        weights="weight",
        resolution_parameter=resolution,
        seed=seed,
    )

    membership = list(partition.membership)
    n_communities = len(set(membership))
    sizes = sorted([len(c) for c in partition], reverse=True)

    return LeidenResult(
        membership=membership,
        modularity=float(partition.modularity),
        n_communities=n_communities,
        community_sizes=sizes,
    )


def run_leiden_stable(
    graph: ig.Graph,
    resolution: float = 1.0,
    n_runs: int = 10,
) -> LeidenResult:
    """Run Leiden n_runs times, return partition with median modularity."""
    if graph.vcount() == 0 or graph.ecount() == 0:
        return run_leiden(graph, resolution)

    results = [run_leiden(graph, resolution, seed=i) for i in range(n_runs)]
    results.sort(key=lambda r: r.modularity)
    return results[len(results) // 2]
