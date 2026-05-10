"""Campaign to actor mapping via majority vote."""

from __future__ import annotations

import json
import logging
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from cti_agent.campaign.attributes import CampaignRecord

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ActorAttribution:
    campaign_id: str
    primary_actor: str
    confidence: float
    vote_distribution: dict[str, int]
    is_shared_infrastructure: bool
    evidence_summary: str


def build_ground_truth_map(
    dataset_path: Path,
    incident_domains: dict[str, list[str]],
) -> dict[str, str]:
    """Map incident_id → majority actor/family label from dataset.

    For OTX incidents: look up domains' actor labels, take majority.
    For ThreatFox incidents: family is in the incident_id itself.
    """
    domain_labels: dict[str, str] = {}
    for line in dataset_path.read_text(encoding="utf-8").strip().split("\n"):
        entry = json.loads(line)
        label = entry.get("actor") or entry.get("family") or "unknown"
        domain_labels[entry["domain"]] = label

    gt_map: dict[str, str] = {}
    for incident_id, domains in incident_domains.items():
        if incident_id.startswith("threatfox|"):
            gt_map[incident_id] = incident_id.split("|", 1)[1]
            continue

        labels = [domain_labels[d] for d in domains if d in domain_labels]
        if labels:
            gt_map[incident_id] = Counter(labels).most_common(1)[0][0]
        else:
            gt_map[incident_id] = "unknown"

    return gt_map


def build_shared_infra_set(dataset_path: Path) -> set[str]:
    """Return set of domains marked as shared_infrastructure in the dataset."""
    shared = set()
    for line in dataset_path.read_text(encoding="utf-8").strip().split("\n"):
        entry = json.loads(line)
        if entry.get("shared_infrastructure"):
            shared.add(entry["domain"])
    return shared


def map_campaigns_to_actors(
    campaigns: list[CampaignRecord],
    incident_ground_truth: dict[str, str],
    incident_domains: dict[str, list[str]],
    shared_infra_domains: set[str],
) -> list[ActorAttribution]:
    attributions: list[ActorAttribution] = []

    for campaign in campaigns:
        votes: Counter[str] = Counter()
        has_shared_infra = False

        for inc_id in campaign.incident_ids:
            label = incident_ground_truth.get(inc_id, "unknown")
            votes[label] += 1

            domains = incident_domains.get(inc_id, [])
            if any(d in shared_infra_domains for d in domains):
                has_shared_infra = True

        if not votes:
            attributions.append(ActorAttribution(
                campaign_id=campaign.campaign_id,
                primary_actor="Unknown",
                confidence=0.0,
                vote_distribution={},
                is_shared_infrastructure=False,
                evidence_summary="No ground truth available",
            ))
            continue

        primary, primary_count = votes.most_common(1)[0]
        total = sum(votes.values())
        confidence = round(primary_count / total, 4)

        if confidence < 0.5 or has_shared_infra:
            has_shared_infra = True
            confidence = round(confidence * 0.5, 4)

        other_actors = [f"{actor}({count})" for actor, count in votes.most_common() if actor != primary]
        shared_str = f" Shared clusters: {sorted(campaign.shared_clusters)}." if campaign.shared_clusters else ""
        evidence = f"{primary_count}/{total} incidents attributed to {primary}."
        if other_actors:
            evidence += f" Others: {', '.join(other_actors)}."
        evidence += shared_str

        attributions.append(ActorAttribution(
            campaign_id=campaign.campaign_id,
            primary_actor=primary,
            confidence=confidence,
            vote_distribution=dict(votes),
            is_shared_infrastructure=has_shared_infra,
            evidence_summary=evidence,
        ))

    return attributions
