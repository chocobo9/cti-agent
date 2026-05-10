"""Infrastructure Agent node — executes Cypher templates against Neo4j.

Task 4.5: Reads CypherInstruction list from state, executes in parallel
via asyncio.to_thread (Option B — wraps existing sync CypherTemplateExecutor),
classifies results, triggers followup templates, writes graph_paths to state.

Future work (Option A): native neo4j.AsyncGraphDatabase for true async I/O.
"""

from __future__ import annotations

import asyncio
import logging
from functools import lru_cache
from typing import Any

from neo4j.exceptions import ServiceUnavailable, TransientError
from rapidfuzz import process as fuzz_process
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from cti_agent.agent.routing import select_followup_templates
from cti_agent.agent.schemas import QueryAnalysis
from cti_agent.agent.tools.cypher_templates import CypherTemplateExecutor
from cti_agent.graph.client import Neo4jClient
from cti_agent.graph.config import get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Compression limits per template (user-approved values)
# ---------------------------------------------------------------------------

_COMPRESS_LIMITS: dict[str, dict[str, int]] = {
    "domain_infrastructure": {"ips": 20, "certificates": 20},
    "domain_to_actor": {},
    "actor_to_domains": {"domains": 50},
    "shared_infrastructure": {"shared_domains": 20},
    "certificate_pivot": {"related_domains": 15},
    "reverse_ip_lookup": {"domains": 30},
    "similar_incidents": {"similar_incidents": 10},
    "active_campaigns": {},
}

# ---------------------------------------------------------------------------
# Singleton executor
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _get_executor() -> CypherTemplateExecutor:
    settings = get_settings()
    client = Neo4jClient(settings)
    return CypherTemplateExecutor(client)


@lru_cache(maxsize=1)
def _get_client() -> Neo4jClient:
    return Neo4jClient(get_settings())


# ---------------------------------------------------------------------------
# Template execution with retry
# ---------------------------------------------------------------------------


_RETRYABLE = (ServiceUnavailable, TransientError, ConnectionError, OSError)


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    retry=retry_if_exception_type(_RETRYABLE),
    reraise=True,
)
def _execute_template_sync(
    executor: CypherTemplateExecutor, template_name: str, params: dict[str, Any]
) -> dict[str, Any]:
    method = getattr(executor, template_name, None)
    if method is None:
        raise ValueError(f"Unknown template: {template_name}")
    if "ip" in params and template_name == "reverse_ip_lookup":
        return method(ip=params["ip"])
    if "asn_number" in params and template_name == "reverse_ip_lookup":
        return method(asn_number=params["asn_number"])
    if template_name == "similar_incidents":
        return method(params["cluster_tag_set"])
    if template_name == "active_campaigns":
        return method(**params)
    first_param = next(iter(params.values()), None)
    return method(first_param)


async def _execute_one(
    executor: CypherTemplateExecutor, template_name: str, params: dict[str, Any]
) -> dict[str, Any]:
    try:
        result = await asyncio.to_thread(
            _execute_template_sync, executor, template_name, params
        )
        return {"template": template_name, "params": params, "result": result, "error": None}
    except Exception as exc:
        logger.exception("Template %s(%s) failed", template_name, params)
        return {"template": template_name, "params": params, "result": None, "error": str(exc)}


# ---------------------------------------------------------------------------
# Result classification
# ---------------------------------------------------------------------------


_PRIMARY_KEYS = frozenset({"domain", "actor", "target"})


def _is_result_empty(result: dict[str, Any]) -> bool:
    for key, val in result.items():
        if key in _PRIMARY_KEYS:
            continue
        if isinstance(val, list) and len(val) > 0:
            return False
        if isinstance(val, dict) and val:
            return False
    return True


def _has_null_primary(result: dict[str, Any]) -> bool:
    for key in ("domain", "actor", "target"):
        if key in result and result[key] is None:
            return True
    return False


def _fuzzy_match_entity(
    client: Neo4jClient, label: str, value: str, limit: int = 3
) -> list[str]:
    query = f"MATCH (n:{label}) RETURN n.name AS name"
    try:
        rows = client.execute_read(query)
    except Exception:
        return []
    names = [r["name"] for r in rows if r.get("name")]
    if not names:
        return []
    matches = fuzz_process.extract(value, names, limit=limit, score_cutoff=50)
    return [m[0] for m in matches]


def _classify_result(
    template_name: str, params: dict[str, Any], result: dict[str, Any] | None, error: str | None
) -> dict[str, Any]:
    if error is not None:
        return {"status": "error", "template": template_name, "params": params, "data": {}, "suggestion": None, "error": error}

    if result is None or _has_null_primary(result):
        param_val = next(iter(params.values()), None)
        label_map = {
            "domain_infrastructure": "Domain",
            "domain_to_actor": "Domain",
            "shared_infrastructure": "Domain",
            "certificate_pivot": "Domain",
            "actor_to_domains": "Actor",
            "active_campaigns": "Actor",
            "reverse_ip_lookup": "IP",
        }
        label = label_map.get(template_name)
        suggestions = []
        if label and param_val and isinstance(param_val, str):
            try:
                suggestions = _fuzzy_match_entity(_get_client(), label, param_val)
            except Exception:
                pass
        return {
            "status": "no_match",
            "template": template_name,
            "params": params,
            "data": result or {},
            "suggestion": suggestions if suggestions else None,
            "error": None,
        }

    if _is_result_empty(result):
        return {"status": "empty", "template": template_name, "params": params, "data": result, "suggestion": None, "error": None}

    return {"status": "success", "template": template_name, "params": params, "data": result, "suggestion": None, "error": None}


# ---------------------------------------------------------------------------
# Result compression
# ---------------------------------------------------------------------------


def _compress_result(template_name: str, result: dict[str, Any]) -> dict[str, Any]:
    limits = _COMPRESS_LIMITS.get(template_name, {})
    if not limits:
        return result
    compressed = dict(result)
    for key, max_rows in limits.items():
        if key in compressed and isinstance(compressed[key], list):
            compressed[key] = compressed[key][:max_rows]
    return compressed


# ---------------------------------------------------------------------------
# Evidence summary generation
# ---------------------------------------------------------------------------


def _build_evidence_summary(template_name: str, params: dict[str, Any], result: dict[str, Any]) -> str:
    target = next(iter(params.values()), "?")

    if template_name == "domain_infrastructure":
        n_ips = len(result.get("ips", []))
        asns = result.get("asns", [])
        asn_str = ", ".join(f"AS{a.get('number', '?')} ({a.get('name', '?')})" for a in asns[:3])
        n_certs = len(result.get("certificates", []))
        shared = any(a.get("is_shared_hosting") for a in asns)
        return f"T1: domain {target} resolves to {n_ips} IPs, {asn_str or 'no ASN'}, {n_certs} certs, shared_hosting={shared}"

    if template_name == "domain_to_actor":
        actors = [a.get("name", "?") for a in result.get("actors", [])]
        tags = result.get("cluster_tag_set", [])
        campaigns = [c.get("name", "?") for c in result.get("campaigns", [])]
        return f"T2: domain {target} -> actors={actors or 'none'}, clusters={tags or 'none'}, campaigns={campaigns or 'none'}"

    if template_name == "actor_to_domains":
        n_domains = len(result.get("domains", []))
        n_clusters = len(result.get("clusters", []))
        n_campaigns = len(result.get("campaigns", []))
        return f"T3: actor {target} -> {n_domains} domains, {n_clusters} clusters, {n_campaigns} campaigns"

    if template_name == "shared_infrastructure":
        n_shared = len(result.get("shared_domains", []))
        return f"T4: domain {target} shares infrastructure with {n_shared} other domains"

    if template_name == "certificate_pivot":
        n_related = len(result.get("related_domains", []))
        return f"T5: domain {target} shares certificates with {n_related} other domains"

    if template_name == "reverse_ip_lookup":
        n_domains = len(result.get("domains", []))
        return f"T6: {target} -> {n_domains} domains"

    if template_name == "similar_incidents":
        n_similar = len(result.get("similar_incidents", []))
        return f"T7: cluster tags {target} -> {n_similar} similar incidents"

    if template_name == "active_campaigns":
        n_campaigns = len(result.get("campaigns", []))
        n_domains = len(result.get("domains", []))
        return f"T8: {target} -> {n_campaigns} active campaigns, {n_domains} domains"

    return f"{template_name}({target}): completed"


# ---------------------------------------------------------------------------
# Main LangGraph node
# ---------------------------------------------------------------------------


async def infrastructure_agent_node(state: dict) -> dict:
    """Execute Cypher templates from routing decision, classify and compress results."""
    routing = state.get("_routing_decision") or {}
    templates_raw = routing.get("templates", [])

    if not templates_raw:
        return {
            "graph_paths": [],
            "evidence_chain": ["Infrastructure: no templates to execute"],
        }

    executor = _get_executor()

    priority_0 = [t for t in templates_raw if t.get("priority", 0) == 0]
    priority_1 = [t for t in templates_raw if t.get("priority", 0) == 1]

    async def _run_batch(batch: list[dict]) -> list[dict]:
        tasks = [
            _execute_one(executor, t["template_name"], t["params"])
            for t in batch
        ]
        return await asyncio.gather(*tasks)

    raw_results = list(await _run_batch(priority_0))

    if priority_1:
        raw_results.extend(await _run_batch(priority_1))

    graph_paths: list[dict] = []
    evidence_chain: list[str] = []
    errors: list[str] = []
    enrichment_suggested = False

    first_round_results: dict[str, Any] = {}

    for item in raw_results:
        classified = _classify_result(
            item["template"], item["params"], item["result"], item["error"]
        )

        if classified["status"] == "success":
            compressed = _compress_result(item["template"], classified["data"])
            classified["data"] = compressed
            evidence_chain.append(
                _build_evidence_summary(item["template"], item["params"], compressed)
            )
            first_round_results[item["template"]] = compressed

        elif classified["status"] == "no_match":
            evidence_chain.append(
                f"{item['template']}({next(iter(item['params'].values()), '?')}): entity not found in graph"
                + (f", did you mean: {classified['suggestion']}" if classified["suggestion"] else "")
            )
            enrichment_suggested = True

        elif classified["status"] == "error":
            errors.append(f"{item['template']}: {item['error']}")

        graph_paths.append(classified)

    analysis_data = routing.get("analysis")
    if analysis_data and first_round_results:
        try:
            analysis = QueryAnalysis.model_validate(analysis_data)
            followups = select_followup_templates(analysis, first_round_results)
            if followups:
                followup_batch = [
                    {"template_name": f.template_name, "params": f.params, "priority": f.priority}
                    for f in followups
                ]
                followup_results = await _run_batch(followup_batch)
                for item in followup_results:
                    classified = _classify_result(
                        item["template"], item["params"], item["result"], item["error"]
                    )
                    if classified["status"] == "success":
                        compressed = _compress_result(item["template"], classified["data"])
                        classified["data"] = compressed
                        evidence_chain.append(
                            _build_evidence_summary(item["template"], item["params"], compressed)
                        )
                    elif classified["status"] == "error":
                        errors.append(f"{item['template']}: {item['error']}")
                    graph_paths.append(classified)
        except Exception:
            logger.exception("Followup template selection failed")

    result: dict[str, Any] = {
        "graph_paths": graph_paths,
        "evidence_chain": evidence_chain,
        "enrichment_suggested": enrichment_suggested,
    }
    if errors:
        result["error_count"] = len(errors)
        result["last_error"] = errors[-1]

    return result
