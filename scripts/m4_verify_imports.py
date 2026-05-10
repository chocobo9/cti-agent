"""Quick smoke test: verify all M4.1/4.2/4.3 imports work."""

from cti_agent.agent.schemas import (
    ActorCandidate,
    AttributionState,
    CypherInstruction,
    EvidenceEvaluation,
    QueryAnalysis,
    RoutingDecision,
)
from cti_agent.agent.tools.cypher_templates import CypherTemplateExecutor
from cti_agent.agent.tools.rag_retriever import retrieve_cti_chunks

print("All imports OK")
print("AttributionState fields:", list(AttributionState.__annotations__.keys()))

methods = [m for m in dir(CypherTemplateExecutor) if not m.startswith("_")]
print("CypherTemplateExecutor methods:", methods)

print("retrieve_cti_chunks callable:", callable(retrieve_cti_chunks))
