export type AttributionResult = 'high_confidence' | 'medium_confidence' | 'low_confidence' | 'insufficient';
export type CypherStatus = 'success' | 'empty' | 'error' | 'no_match';
export type Source = 'graph' | 'rag' | 'llm';

export interface CandidateActor {
  actor_name: string;
  confidence: number;
  source: Source;
  supporting_evidence: string[];
}

export interface PassiveDnsRecord {
  ip: string;
  first_seen: string;
  last_seen: string;
}

export interface RdapInfo {
  creation_date: string;
  expiration_date: string;
  registrar: string;
}

export interface Certificate {
  fingerprint: string;
  issuer: string;
  san_list: string[];
  not_before: string;
  not_after: string;
}

export interface GeoIpRecord {
  ip: string;
  asn_number: number;
  asn_name: string;
  country: string;
  city: string;
}

export interface Enrichment {
  passive_dns: PassiveDnsRecord[];
  current_ips: string[];
  rdap: RdapInfo;
  certificates: Certificate[];
  geoip: GeoIpRecord[];
  jarm_hash: string;
  favicon_hash: string;
}

export interface GraphPath {
  status: CypherStatus;
  template: string;
  summary: string;
}

export interface RagChunk {
  chunk_id: string;
  source: string;
  rrf_score: number;
  snippet: string;
}

export interface SourceEntry {
  type: 'graph' | 'rag';
  detail: string;
}

export interface AttributionState {
  query: string;
  domain: string;
  query_type: 'structural' | 'semantic' | 'mixed';

  attribution_result: AttributionResult;
  confidence: number;
  temporal_confidence: number;
  is_shared_infrastructure: boolean;
  needs_more_evidence: boolean;

  candidate_actors: CandidateActor[];

  enrichment: Enrichment;

  graph_paths: GraphPath[];
  rag_chunks: RagChunk[];
  evidence_chain: string[];
  narrative: string;
  sources: SourceEntry[];
}

export type NodeStatus = 'done' | 'running' | 'error' | 'queued';

export interface NodeEvent {
  type: 'node_start' | 'node_done' | 'node_error';
  node_id: string;
  ts: number;
  duration_ms?: number;
  error?: string;
}
