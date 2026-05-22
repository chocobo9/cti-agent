import type { AttributionState } from '../types/AttributionState';
import { NODE_SUBS } from '../fixtures/nodeConfig';

export function getNodeSub(id: string, state: AttributionState): string {
  switch (id) {
    case 'supervisor':
      return `query_type → ${state.query_type}`;
    case 'infrastructure':
      return `${state.graph_paths.length} templates · ${state.graph_paths.filter((g) => g.status === 'success').length} success / ${state.graph_paths.filter((g) => g.status !== 'success').length} other`;
    case 'intelligence':
      return `${state.rag_chunks.length} chunks · top ${state.rag_chunks.filter((c) => c.rrf_score > 0.6).length} RRF > 0.6`;
    case 'graph_probe':
      return `${state.candidate_actors.length} candidate actors validated`;
    case 'evidence_eval':
      return `confidence = ${state.confidence.toFixed(2)} · ${state.needs_more_evidence ? 'iterate' : 'no iter.'}`;
    case 'report':
      return `${state.sources.length} sources · narrative ${state.narrative.length} chars`;
    default:
      return NODE_SUBS[id] ?? '';
  }
}

export function makePlaceholderState(query: string): AttributionState {
  return {
    query,
    domain: query ? extractDomain(query) : '—',
    query_type: 'structural',
    attribution_result: 'insufficient',
    confidence: 0,
    temporal_confidence: 0,
    is_shared_infrastructure: false,
    needs_more_evidence: false,
    candidate_actors: [],
    enrichment: {
      passive_dns: [],
      current_ips: [],
      rdap: { creation_date: '', expiration_date: '', registrar: '' },
      certificates: [],
      geoip: [],
      jarm_hash: '',
      favicon_hash: '',
    },
    graph_paths: [],
    rag_chunks: [],
    evidence_chain: [],
    narrative: '',
    sources: [],
  };
}

export function extractDomain(query: string): string {
  const match = query.match(/[a-zA-Z0-9][-a-zA-Z0-9]*\.[a-zA-Z]{2,}/);
  return match ? match[0] : '—';
}
