"""Domain input models and JSONL file loader for the M1 batch pipeline.

DomainInput represents a single domain to enrich, along with optional ground
truth metadata (source, actor, family, shared_infrastructure) that gets
persisted on the Neo4j Domain node for downstream evaluation.

File format — JSONL (one JSON object per line):
    {"domain": "evil.com", "source": "otx", "actor": "Comment Crew"}
    {"domain": "malware.net", "source": "threatfox", "family": "ClearFake"}

    Required: domain (str)
    Optional: source (str, default "unknown"), actor (str|null),
              family (str|null), shared_infrastructure (bool, default false)
    Lines starting with # and blank lines are skipped.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class DomainInput(BaseModel):
    """A domain to enrich with optional ground truth metadata.

    Attributes:
        domain: The domain name to enrich (e.g. "evil.com").
        source: Where this domain came from ("otx", "threatfox", etc.).
        actor: Ground truth threat actor attribution, if known.
        family: Ground truth malware family, if known.
        shared_infrastructure: True if this domain uses shared/MaaS infra
            (e.g. Cobalt Strike, Phorpiex). These domains should NOT be
            attributed to a single actor.
    """

    domain: str
    source: str = "unknown"
    actor: str | None = None
    family: str | None = None
    shared_infrastructure: bool = False
    group: str | None = None
    pulse_id: str | None = None
    first_seen: str | None = None


def load_domains_from_file(path: Path) -> list[DomainInput]:
    """Load domain inputs from a JSONL file (one JSON object per line).

    Invalid lines are logged and skipped — the pipeline continues with
    whatever valid entries were parsed.
    """
    entries: list[DomainInput] = []
    text = path.read_text(encoding="utf-8")
    for line_num, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            data = json.loads(line)
            entries.append(DomainInput.model_validate(data))
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning("Skipping invalid line %d in %s: %s", line_num, path, exc)
    return entries
