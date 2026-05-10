"""Campaign attribute computation from Leiden communities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from cti_agent.campaign.similarity import IncidentRecord, jaccard_similarity


@dataclass(frozen=True)
class CampaignRecord:
    campaign_id: str
    name: str
    confidence_score: float
    first_seen: date
    last_seen: date
    shared_clusters: frozenset[int]
    all_clusters: frozenset[int]
    incident_ids: list[str]
    incident_count: int


def compute_campaigns(
    eligible_incidents: list[IncidentRecord],
    membership: list[int],
) -> list[CampaignRecord]:
    """Build CampaignRecords from Leiden partition membership."""
    communities: dict[int, list[int]] = {}
    for idx, comm_id in enumerate(membership):
        communities.setdefault(comm_id, []).append(idx)

    campaigns: list[CampaignRecord] = []
    for comm_id in sorted(communities):
        indices = communities[comm_id]
        incs = [eligible_incidents[i] for i in indices]

        all_clusters: set[int] = set()
        shared_clusters: set[int] | None = None
        for inc in incs:
            all_clusters |= inc.cluster_tag_set
            if shared_clusters is None:
                shared_clusters = set(inc.cluster_tag_set)
            else:
                shared_clusters &= inc.cluster_tag_set

        if shared_clusters is None:
            shared_clusters = set()

        dates = [inc.date for inc in incs]
        first_seen = min(dates)
        last_seen = max(dates)

        if len(incs) == 1:
            confidence = 0.5
        else:
            sims = []
            for i in range(len(incs)):
                for j in range(i + 1, len(incs)):
                    sims.append(jaccard_similarity(incs[i].cluster_tag_set, incs[j].cluster_tag_set))
            confidence = sum(sims) / len(sims) if sims else 0.0

        if not shared_clusters and len(incs) > 1:
            confidence *= 0.5

        campaigns.append(CampaignRecord(
            campaign_id=f"campaign_{comm_id:03d}",
            name=f"Campaign-{comm_id:03d}",
            confidence_score=round(confidence, 4),
            first_seen=first_seen,
            last_seen=last_seen,
            shared_clusters=frozenset(shared_clusters),
            all_clusters=frozenset(all_clusters),
            incident_ids=[inc.incident_id for inc in incs],
            incident_count=len(incs),
        ))

    return campaigns
