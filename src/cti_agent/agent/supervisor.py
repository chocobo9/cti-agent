"""Supervisor query analysis node for the CTI attribution agent.

Task 4.4: LangGraph node that calls DeepSeek to classify query intent
and extract entities, then hands off to deterministic routing (4.9).

Design reference: m4_module_h_design.md section 7
"""

from __future__ import annotations

import logging
import os
import re
from functools import lru_cache
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import ValidationError
from tenacity import retry, retry_if_exception_type, stop_after_attempt

from cti_agent.agent.prompts import QUERY_ANALYSIS_SYSTEM_PROMPT
from cti_agent.agent.routing import build_rag_hints, determine_query_type, select_templates
from cti_agent.agent.schemas import QueryAnalysis

logger = logging.getLogger(__name__)

_DOMAIN_RE = re.compile(r"[a-zA-Z0-9][-a-zA-Z0-9]{0,62}(?:\.[a-zA-Z0-9][-a-zA-Z0-9]{0,62})*\.[a-zA-Z]{2,}")


@lru_cache(maxsize=1)
def _get_llm():
    from langchain_deepseek import ChatDeepSeek

    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY environment variable is not set")
    return ChatDeepSeek(model="deepseek-chat", api_key=api_key, temperature=0)


@retry(
    stop=stop_after_attempt(2),
    retry=retry_if_exception_type((ValidationError, KeyError)),
)
def call_query_analysis(llm: Any, query: str) -> QueryAnalysis:
    """Call LLM with structured output to extract intent and entities."""
    structured_llm = llm.with_structured_output(QueryAnalysis)
    return structured_llm.invoke([
        SystemMessage(content=QUERY_ANALYSIS_SYSTEM_PROMPT),
        HumanMessage(content=query),
    ])


_IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


def _fallback_analysis(query: str) -> QueryAnalysis:
    """Regex-based fallback when LLM structured output fails."""
    cleaned = re.sub(r"\[\.\]", ".", query)

    domain_match = _DOMAIN_RE.search(cleaned)
    target_domain = domain_match.group(0).lower() if domain_match else None

    ips = _IP_RE.findall(cleaned)

    if target_domain:
        intent = "attribute_domain"
    elif ips:
        intent = "find_related_infrastructure"
    else:
        intent = "general_cti_query"

    logger.warning(
        "LLM structured output failed, using regex fallback: intent=%s domain=%s ips=%s",
        intent,
        target_domain,
        ips,
    )
    return QueryAnalysis(
        intent=intent,
        target_domain=target_domain,
        mentioned_ips=ips,
        reasoning=f"Fallback: domain={target_domain}, ips={ips}",
    )


def supervisor_query_analysis_node(state: dict) -> dict:
    """LangGraph node: analyze query, classify intent, build routing decision.

    Reads: state["query"]
    Writes: domain, query_type, evidence_chain (append)
    """
    query = state["query"]

    try:
        llm = _get_llm()
        analysis = call_query_analysis(llm, query)
    except Exception:
        logger.exception("Query analysis LLM call failed, using fallback")
        analysis = _fallback_analysis(query)

    if analysis.target_domain:
        cleaned = re.sub(r'\[\.\]', '.', analysis.target_domain)
        cleaned = re.sub(r'^https?://', '', cleaned, flags=re.IGNORECASE)
        cleaned = cleaned.split('/')[0].split('?')[0].split('#')[0].lower().strip('.')
        if cleaned != analysis.target_domain:
            analysis = analysis.model_copy(update={"target_domain": cleaned})

    query_type = determine_query_type(analysis)
    templates = select_templates(analysis)
    rag_hints = build_rag_hints(analysis)

    return {
        "domain": analysis.target_domain,
        "query_type": query_type,
        "_routing_decision": {
            "query_type": query_type,
            "templates": [
                {"template_name": t.template_name, "params": t.params, "priority": t.priority}
                for t in templates
            ],
            "rag_hints": rag_hints,
            "analysis": analysis.model_dump(),
        },
        "evidence_chain": [
            f"Query analyzed: intent={analysis.intent}, query_type={query_type}, target={analysis.target_domain}"
        ],
    }
