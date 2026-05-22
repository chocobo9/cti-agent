import type { AttributionState, NodeEvent } from '../types/AttributionState';

const VALID_NODE_TYPES = ['node_start', 'node_done', 'node_error'];

export function parseNodeEvent(data: unknown): NodeEvent | null {
  if (typeof data !== 'object' || data === null) return null;
  const obj = data as Record<string, unknown>;
  if (typeof obj.type !== 'string' || !VALID_NODE_TYPES.includes(obj.type)) return null;
  if (typeof obj.node_id !== 'string') return null;
  if (typeof obj.ts !== 'number') return null;
  return {
    type: obj.type as NodeEvent['type'],
    node_id: obj.node_id,
    ts: obj.ts,
    duration_ms: typeof obj.duration_ms === 'number' ? obj.duration_ms : undefined,
    error: typeof obj.error === 'string' ? obj.error : undefined,
  };
}

const VALID_RESULTS = ['high_confidence', 'medium_confidence', 'low_confidence', 'insufficient'];

export function parseAttributionState(data: unknown): AttributionState | null {
  if (typeof data !== 'object' || data === null) return null;
  const obj = data as Record<string, unknown>;

  if (typeof obj.attribution_result !== 'string' || !VALID_RESULTS.includes(obj.attribution_result)) return null;
  if (typeof obj.query !== 'string') return null;
  if (typeof obj.domain !== 'string') return null;
  if (typeof obj.confidence !== 'number') return null;

  return {
    query: obj.query,
    domain: obj.domain,
    query_type: typeof obj.query_type === 'string' ? obj.query_type as AttributionState['query_type'] : 'structural',
    attribution_result: obj.attribution_result as AttributionState['attribution_result'],
    confidence: obj.confidence,
    temporal_confidence: typeof obj.temporal_confidence === 'number' ? obj.temporal_confidence : 0,
    is_shared_infrastructure: typeof obj.is_shared_infrastructure === 'boolean' ? obj.is_shared_infrastructure : false,
    needs_more_evidence: typeof obj.needs_more_evidence === 'boolean' ? obj.needs_more_evidence : false,
    candidate_actors: Array.isArray(obj.candidate_actors) ? obj.candidate_actors as AttributionState['candidate_actors'] : [],
    enrichment: isEnrichment(obj.enrichment) ? obj.enrichment : emptyEnrichment(),
    graph_paths: Array.isArray(obj.graph_paths) ? obj.graph_paths as AttributionState['graph_paths'] : [],
    rag_chunks: Array.isArray(obj.rag_chunks) ? obj.rag_chunks as AttributionState['rag_chunks'] : [],
    evidence_chain: Array.isArray(obj.evidence_chain) ? obj.evidence_chain as string[] : [],
    narrative: typeof obj.narrative === 'string' ? obj.narrative : '',
    sources: Array.isArray(obj.sources) ? obj.sources as AttributionState['sources'] : [],
  };
}

function isEnrichment(v: unknown): v is AttributionState['enrichment'] {
  if (typeof v !== 'object' || v === null) return false;
  const e = v as Record<string, unknown>;
  return Array.isArray(e.passive_dns) && typeof e.rdap === 'object';
}

function emptyEnrichment(): AttributionState['enrichment'] {
  return {
    passive_dns: [],
    current_ips: [],
    rdap: { creation_date: '', expiration_date: '', registrar: '' },
    certificates: [],
    geoip: [],
    jarm_hash: '',
    favicon_hash: '',
  };
}
