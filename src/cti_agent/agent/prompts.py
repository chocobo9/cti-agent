"""LLM prompt templates for the CTI attribution agent.

System prompts (domain knowledge) live in skills/*.
User message templates (with format variables) live here.
"""

QUERY_ANALYSIS_SYSTEM_PROMPT = """\
You are a CTI analyst assistant.
Analyze the user's query and extract structured information.

## Intent categories:
- attribute_domain: WHO is behind a specific domain
- investigate_actor: Understand an actor's infrastructure/campaigns
- find_related_infrastructure: Find domains related to an IP/ASN
- general_cti_query: General CTI question, no specific IOC

## Entity extraction rules:
- target_domain: Primary domain (strip protocols/paths)
- mentioned_ips: IPv4/IPv6 addresses
- mentioned_actors: Threat actor/group names (canonical names)
- mentioned_malware: Malware family names
- behavioral_description: Attack techniques/TTPs (only if user describes BEHAVIOR, not just names)

## Examples:
Query: "Who is behind evil.com?"
→ intent: attribute_domain, target_domain: "evil.com"

Query: "What infrastructure does Lazarus Group use?"
→ intent: investigate_actor, mentioned_actors: ["Lazarus Group"]

Query: "evil.com uses spear-phishing with macro-enabled docs"
→ intent: attribute_domain, target_domain: "evil.com",
  behavioral_description: "spear-phishing with macro-enabled documents"

Query: "What APT groups are known for supply chain attacks?"
→ intent: general_cti_query, behavioral_description: "supply chain attacks"

Output ONLY the structured JSON."""


QUERY_REWRITING_USER_TEMPLATE = """\
Original query: {query}

Entities identified by analyst:
- Domains: {domains}
- Actors: {actors}
- IPs: {ips}
- Behavior: {behavior}

Suggested search directions: {rag_hints}

{graph_context}

Generate 2-3 diverse retrieval queries:"""


EVIDENCE_EVALUATION_USER_TEMPLATE = """\
## Query
{query}

## Target domain
{domain}

## Graph evidence (infrastructure analysis summaries)
{graph_evidence}

## RAG evidence (CTI report chunks)
{rag_evidence}

## Temporal context
{temporal_description}

## MaaS indicators
{maas_indicators}

Evaluate the evidence and provide your attribution assessment:"""


REPORT_NARRATIVE_USER_TEMPLATE = """\
## Attribution Data
- Query: {query}
- Domain: {domain}
- Query type: {query_type}
- Confidence: {confidence}
- Attribution result: {attribution_result}
- Shared infrastructure: {is_shared_infrastructure}
- Shared infrastructure note: {shared_infra_note}
- Enrichment suggested: {enrichment_suggested}

## Candidate Actors
{candidates}

## Campaign Associations
{campaigns}

## Infrastructure Evidence
{infrastructure_evidence}

## Intelligence Evidence
{intelligence_evidence}

Based on the above data and the report writing guidelines in your system prompt, write a complete attribution report."""
