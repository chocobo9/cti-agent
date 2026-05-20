"""Graph-probe helper functions — extract IOCs from RAG chunks and match
against the Neo4j knowledge graph.

This module contains only deterministic logic (regex, set operations, Cypher
reads).  The main node function ``graph_probe_node`` is defined in a later step.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any

import structlog

from cti_agent.agent.tools.cypher_templates import CypherTemplateExecutor
from cti_agent.graph.client import Neo4jClient
from cti_agent.graph.config import get_settings

logger = structlog.get_logger(__name__)

# --- Domain regex (normal + defanged) ---
_DOMAIN_RE = re.compile(
    r"(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\[?\.\]?)"
    r"+[a-zA-Z]{2,63}",
)

# --- IPv4 regex (normal + defanged) ---
_IPV4_RE = re.compile(
    r"\b(?:\d{1,3}\[?\.\]?){3}\d{1,3}\b"
)

# --- ASN regex ---
_ASN_RE = re.compile(r"\bAS(\d{3,6})\b")  # 注意大写 AS

# 排除的 false positive patterns
_EXCLUDED_DOMAINS = frozenset({
    "example.com", "example.org", "example.net",
    "localhost", "schema.org", "w3.org",
})
_PRIVATE_IP_PREFIXES = ("0.", "10.", "127.", "169.254.", "172.16.", "172.17.",
                        "172.18.", "172.19.", "172.20.", "172.21.", "172.22.",
                        "172.23.", "172.24.", "172.25.", "172.26.", "172.27.",
                        "172.28.", "172.29.", "172.30.", "172.31.", "192.168.", "255.")

# Probe limits
_MAX_PROBE_DOMAINS = 5
_MAX_PROBE_IPS = 3
_MAX_PROBE_ACTORS = 3


# ---------------------------------------------------------------------------
# Refang
# ---------------------------------------------------------------------------


def _refang(text: str) -> str:
    """Normalize defanged IOCs: [.] -> . and hxxp -> http."""
    return text.replace("[.]", ".").replace("[:]", ":").replace("hxxp", "http")


# ---------------------------------------------------------------------------
# Entity extraction
# ---------------------------------------------------------------------------


def extract_entities_from_chunks(
    rag_chunks: list[dict[str, Any]],
) -> dict[str, set[str]]:
    """Extract domain, IP, and ASN entities from RAG chunk content.

    Returns {"domains": set, "ips": set, "asns": set}.
    Does NOT extract actors — actor matching requires the known_actors lookup
    and is handled separately in _match_known_actors().
    """
    domains: set[str] = set()
    ips: set[str] = set()
    asns: set[str] = set()

    for chunk in rag_chunks:
        text = chunk.get("content", "")
        refanged = _refang(text)

        for m in _DOMAIN_RE.finditer(refanged):
            d = m.group(0).lower()
            # 至少有一个 dot 且 TLD >= 2 chars
            if "." in d and d not in _EXCLUDED_DOMAINS:
                domains.add(d)

        for m in _IPV4_RE.finditer(refanged):
            ip = _refang(m.group(0))
            if not ip.startswith(_PRIVATE_IP_PREFIXES):
                # 验证每段 0-255
                parts = ip.split(".")
                if len(parts) == 4 and all(0 <= int(p) <= 255 for p in parts):
                    ips.add(ip)

        for m in _ASN_RE.finditer(text):
            asns.add(f"AS{m.group(1)}")

    return {"domains": domains, "ips": ips, "asns": asns}


# ---------------------------------------------------------------------------
# Actor matching
# ---------------------------------------------------------------------------


def _match_known_actors(
    rag_chunks: list[dict[str, Any]],
    known_actors: dict[str, str],  # {lowercase_name_or_alias: canonical_name}
) -> set[str]:
    """Match known actor names/aliases in RAG chunk content."""
    found: set[str] = set()
    for chunk in rag_chunks:
        text_lower = chunk.get("content", "").lower()
        for alias_lower, canonical in known_actors.items():
            if alias_lower in text_lower:
                found.add(canonical)
    return found


# ---------------------------------------------------------------------------
# Known-actor cache
# ---------------------------------------------------------------------------

_ACTOR_CACHE: dict[str, str] | None = None


def _load_known_actors(client: Neo4jClient) -> dict[str, str]:
    """Load actor name + aliases from Neo4j. Cached after first call."""
    global _ACTOR_CACHE  # noqa: PLW0603
    if _ACTOR_CACHE is not None:
        return _ACTOR_CACHE

    rows = client.execute_read(
        "MATCH (a:Actor) RETURN a.name AS name, a.aliases AS aliases"
    )
    lookup: dict[str, str] = {}
    for row in rows:
        name = row.get("name", "")
        if name:
            lookup[name.lower()] = name
            for alias in (row.get("aliases") or []):
                if alias:
                    lookup[alias.lower()] = name
    _ACTOR_CACHE = lookup
    return lookup


# ---------------------------------------------------------------------------
# Filter entities that exist in graph
# ---------------------------------------------------------------------------


def _filter_existing_entities(
    client: Neo4jClient,
    domains: set[str],
    ips: set[str],
) -> tuple[list[str], list[str]]:
    """Check which domains/IPs exist in Neo4j, sorted by attribution depth."""
    # Domain existence + attribution depth
    if domains:
        domain_rows = client.execute_read(
            """
            UNWIND $domains AS d
            MATCH (dom:Domain {name: d})
            OPTIONAL MATCH (dom)-[:PART_OF]->(:Incident)
                          -[:BELONGS_TO_CAMPAIGN]->(:Campaign)
                          -[:ATTRIBUTED_TO]->(a:Actor)
            RETURN dom.name AS domain, count(DISTINCT a) AS actor_count
            ORDER BY actor_count DESC
            """,
            {"domains": list(domains)},
        )
        sorted_domains = [r["domain"] for r in domain_rows][:_MAX_PROBE_DOMAINS]
    else:
        sorted_domains = []

    # IP existence
    if ips:
        ip_rows = client.execute_read(
            "UNWIND $ips AS i MATCH (ip:IP {address: i}) RETURN ip.address AS ip",
            {"ips": list(ips)},
        )
        sorted_ips = [r["ip"] for r in ip_rows][:_MAX_PROBE_IPS]
    else:
        sorted_ips = []

    return sorted_domains, sorted_ips


# ---------------------------------------------------------------------------
# Dedup already-queried templates
# ---------------------------------------------------------------------------


def _compute_already_queried(graph_paths: list[dict]) -> set[str]:
    """Build set of (template, param_key) pairs already executed."""
    already: set[str] = set()
    for p in graph_paths:
        template = p.get("template", "")
        params = p.get("params", {})
        key = f"{template}|{sorted(params.items())}"
        already.add(key)
    return already


# ---------------------------------------------------------------------------
# Evidence summary for graph_probe results
# ---------------------------------------------------------------------------


def _summarize_result(
    template_name: str, params: dict[str, Any], result: dict[str, Any],
) -> str:
    """Generate a GP:-prefixed evidence summary string.

    Mirrors the format of ``infrastructure._build_evidence_summary`` but uses
    a ``GP:`` prefix so downstream consumers can distinguish provenance.
    Covers the four templates used by graph_probe (T2, T3, T6, T8); unknown
    templates get a generic fallback.
    """
    target = next(iter(params.values()), "?")

    if template_name == "domain_to_actor":
        actors = [a.get("name", "?") for a in result.get("actors", [])]
        tags = result.get("cluster_tag_set", [])
        campaigns = [c.get("name", "?") for c in result.get("campaigns", [])]
        return (
            f"GP:domain_to_actor({target}): "
            f"actors={actors or 'none'}, "
            f"clusters={tags or 'none'}, "
            f"campaigns={campaigns or 'none'}"
        )

    if template_name == "actor_to_domains":
        n_domains = len(result.get("domains", []))
        n_clusters = len(result.get("clusters", []))
        n_campaigns = len(result.get("campaigns", []))
        return (
            f"GP:actor_to_domains({target}): "
            f"{n_domains} domains, {n_clusters} clusters, {n_campaigns} campaigns"
        )

    if template_name == "reverse_ip_lookup":
        n_domains = len(result.get("domains", []))
        return f"GP:reverse_ip_lookup({target}): {n_domains} domains"

    if template_name == "active_campaigns":
        n_campaigns = len(result.get("campaigns", []))
        return f"GP:active_campaigns({target}): {n_campaigns} campaigns"

    # Generic fallback for unexpected templates
    return f"GP:{template_name}({target}): completed"


# ---------------------------------------------------------------------------
# Main LangGraph node
# ---------------------------------------------------------------------------


async def graph_probe_node(state: dict) -> dict:
    """Extract entities from RAG chunks and probe the graph for matches.

    Reads: rag_chunks, graph_paths (for dedup)
    Writes: graph_paths (append), evidence_chain (append)

    When rag_chunks is empty or no new entities are found in the graph,
    this node passes through with empty additions (valid no-op).
    """
    rag_chunks = state.get("rag_chunks", [])

    if not rag_chunks:
        return {
            "graph_paths": [],
            "evidence_chain": ["GraphProbe: no RAG chunks to probe"],
        }

    # 1. Extract entities from chunk content
    entities = extract_entities_from_chunks(rag_chunks)

    # 2. Match known actors (lookup table)
    settings = get_settings()
    client = Neo4jClient(settings)

    query_type = state.get("_routing_decision", {}).get("query_type", "semantic")
    if query_type == "structural":
        matched_actors: set[str] = set()
    else:
        known_actors = _load_known_actors(client)
        matched_actors = _match_known_actors(rag_chunks, known_actors)

    # 3. Existence check + truncation
    existing_domains, existing_ips = _filter_existing_entities(
        client, entities["domains"], entities["ips"]
    )

    # 4. Diff-set: remove entities already queried by infrastructure
    already_queried = _compute_already_queried(state.get("graph_paths", []))
    from cti_agent.agent.routing import build_templates_from_entities

    candidate_templates = build_templates_from_entities(
        existing_domains, existing_ips, list(matched_actors)
    )
    new_templates = [
        t for t in candidate_templates
        if f"{t.template_name}|{sorted(t.params.items())}" not in already_queried
    ]

    if not new_templates:
        return {
            "graph_paths": [],
            "evidence_chain": ["GraphProbe: no new entities to probe after dedup"],
        }

    # 5. Execute Cypher templates
    executor = CypherTemplateExecutor(client)
    graph_paths: list[dict] = []
    evidence_chain: list[str] = []

    for tmpl in new_templates:
        try:
            method = getattr(executor, tmpl.template_name)
            result = await asyncio.to_thread(method, **tmpl.params)
            is_empty = not any(
                v for v in result.values()
                if isinstance(v, list) and len(v) > 0
            ) if isinstance(result, dict) else True

            path_entry = {
                "template": tmpl.template_name,
                "params": dict(tmpl.params),
                "status": "empty" if is_empty else "success",
                "data": result if not is_empty else None,
                "source": "graph_probe",
            }
            graph_paths.append(path_entry)

            if not is_empty:
                evidence_chain.append(
                    _summarize_result(tmpl.template_name, tmpl.params, result)
                )
        except Exception as exc:
            logger.exception(
                "graph_probe template failed", template=tmpl.template_name,
            )
            graph_paths.append({
                "template": tmpl.template_name,
                "params": dict(tmpl.params),
                "status": "error",
                "error": str(exc)[:200],
                "source": "graph_probe",
            })

    probe_summary = (
        "GraphProbe: extracted "
        f"{len(entities['domains'])}d/{len(entities['ips'])}ip/"
        f"{len(matched_actors)}actor from RAG -> "
        f"{len(existing_domains)}d/{len(existing_ips)}ip exist in graph -> "
        f"{len(new_templates)} new queries -> "
        f"{sum(1 for p in graph_paths if p['status'] == 'success')} success"
    )
    evidence_chain.insert(0, probe_summary)

    return {
        "graph_paths": graph_paths,
        "evidence_chain": evidence_chain,
    }
