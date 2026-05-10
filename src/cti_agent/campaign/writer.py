"""Write campaign discovery results to Neo4j."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from cti_agent.campaign.actor_mapping import ActorAttribution
from cti_agent.campaign.attributes import CampaignRecord
from cti_agent.graph.repository import GraphRepository

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WriteSummary:
    campaigns_written: int
    belongs_to_edges: int
    actors_written: int
    attributed_to_edges: int


def write_campaigns_to_neo4j(
    repo: GraphRepository,
    campaigns: list[CampaignRecord],
    attributions: list[ActorAttribution],
) -> WriteSummary:
    actors_created: set[str] = set()
    belongs_to_count = 0

    for campaign in campaigns:
        repo.merge_campaign(
            campaign_id=campaign.campaign_id,
            name=campaign.name,
            confidence_score=campaign.confidence_score,
            first_seen=campaign.first_seen,
            last_seen=campaign.last_seen,
        )
        for inc_id in campaign.incident_ids:
            repo.merge_belongs_to_campaign(incident_id=inc_id, campaign_id=campaign.campaign_id)
            belongs_to_count += 1

    logger.info("Wrote %d Campaign nodes, %d BELONGS_TO_CAMPAIGN edges", len(campaigns), belongs_to_count)

    attr_count = 0
    for attr in attributions:
        if attr.primary_actor == "Unknown":
            continue
        if attr.primary_actor not in actors_created:
            repo.merge_actor(name=attr.primary_actor)
            actors_created.add(attr.primary_actor)
        repo.merge_attributed_to(
            campaign_id=attr.campaign_id,
            actor_name=attr.primary_actor,
            confidence=attr.confidence,
            evidence_summary=attr.evidence_summary,
        )
        attr_count += 1

    logger.info("Wrote %d Actor nodes, %d ATTRIBUTED_TO edges", len(actors_created), attr_count)

    return WriteSummary(
        campaigns_written=len(campaigns),
        belongs_to_edges=belongs_to_count,
        actors_written=len(actors_created),
        attributed_to_edges=attr_count,
    )
