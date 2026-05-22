import type { AttributionState } from '../types/AttributionState';

export const sampleState: AttributionState = {
  query: '谁控制 hamadryas.online？',
  domain: 'hamadryas.online',
  query_type: 'structural',

  attribution_result: 'high_confidence',
  confidence: 0.85,
  temporal_confidence: 0.72,
  is_shared_infrastructure: false,
  needs_more_evidence: false,

  candidate_actors: [
    {
      actor_name: 'TA-577',
      confidence: 0.85,
      source: 'graph',
      supporting_evidence: [
        'graph: domain → cluster(tag-xyz) → actor(TA-577)  via T2_domain_to_actor',
        'rag: OTX pulse otx-1234 — "TA-577 observed using Njalla-registered domains on M247/RO for Pikabot delivery"',
        'graph: shared cert SAN with 3 known TA-577 domains  via T3_infrastructure_pivot',
      ],
    },
    {
      actor_name: 'Storm-1811',
      confidence: 0.60,
      source: 'rag',
      supporting_evidence: [
        'rag: campaign report blog-789 — infrastructure overlaps with Storm-1811 (Oct 2025)',
        'llm: DeepSeek inference based on temporal & ASN co-occurrence',
      ],
    },
    {
      actor_name: 'Hive0118',
      confidence: 0.34,
      source: 'llm',
      supporting_evidence: [
        'llm: alias relationship inferred — same cluster historically reported as Hive0118',
      ],
    },
  ],

  enrichment: {
    passive_dns: [
      { ip: '185.244.42.91', first_seen: '2025-09-22', last_seen: '2025-11-14' },
      { ip: '91.219.236.18', first_seen: '2025-09-29', last_seen: '2025-11-14' },
      { ip: '45.137.190.222', first_seen: '2025-10-08', last_seen: '2025-11-01' },
    ],
    current_ips: ['185.244.42.91', '91.219.236.18'],
    rdap: {
      creation_date: '2025-09-14',
      expiration_date: '2026-09-14',
      registrar: 'Njalla AB',
    },
    certificates: [
      {
        fingerprint: 'a3f5c8e2…c9f3',
        issuer: "Let's Encrypt",
        san_list: ['*.hamadryas.online', 'hamadryas.online'],
        not_before: '2025-09-22',
        not_after: '2025-12-21',
      },
      {
        fingerprint: 'd8b1f44a…12ab',
        issuer: "Let's Encrypt",
        san_list: ['auth.hamadryas.online'],
        not_before: '2025-09-26',
        not_after: '2025-12-25',
      },
    ],
    geoip: [
      { ip: '185.244.42.91', asn_number: 9009, asn_name: 'M247 Ltd', country: 'RO', city: 'Bucharest' },
      { ip: '91.219.236.18', asn_number: 49447, asn_name: 'NTL LLC', country: 'RU', city: 'Moscow' },
      { ip: '45.137.190.222', asn_number: 59729, asn_name: 'NeTerra', country: 'BG', city: 'Sofia' },
    ],
    jarm_hash: '2ad2ad0002ad2ad22c2ad2ad2ad2ad…',
    favicon_hash: 'ab12c3d4e5f6789a…',
  },

  graph_paths: [
    { status: 'success', template: 'T1_domain_infrastructure', summary: '1 active IP, 2 historical IPs, 2 certificates' },
    { status: 'success', template: 'T2_domain_to_actor', summary: 'linked to TA-577 via cluster tag-xyz' },
    { status: 'success', template: 'T3_infrastructure_pivot', summary: '3 sibling domains share SAN pattern' },
    { status: 'empty', template: 'T5_certificate_pivot', summary: 'no further matches' },
    { status: 'success', template: 'T7_temporal_correlation', summary: 'campaign Storm-1811 active 2025-09 → now' },
  ],

  rag_chunks: [
    { chunk_id: 'otx-1234', source: 'otx', rrf_score: 0.82, snippet: 'TA-577 observed using Njalla-registered domains with M247 hosting for Pikabot delivery in late 2025.' },
    { chunk_id: 'mitre-456', source: 'mitre', rrf_score: 0.71, snippet: 'Storm-1811 campaign targeting financial sector via spearphishing links to credential-harvesting kits.' },
    { chunk_id: 'blog-789', source: 'blog', rrf_score: 0.66, snippet: 'Latrodectus loader infrastructure showed overlap with TA-577 in October 2025 reporting.' },
  ],

  evidence_chain: [
    'R1 infrastructure: T1 found 1 active IP (M247/RO), T2 linked to TA-577 via cluster tag-xyz',
    'R1 intelligence: 12 RAG chunks retrieved, top 3 (RRF > 0.6) corroborate TA-577 association',
    'graph_probe: validated actor TA-577 exists in graph (5 related domains, 2 active campaigns)',
    'evidence_eval: confidence = 0.85, temporal_confidence = 0.72, high_confidence — no iteration needed',
    'report: synthesized graph + RAG into attribution narrative',
  ],

  narrative:
    'hamadryas.online is attributed to TA-577 with high confidence (0.85). ' +
    'The domain was registered through Njalla on 2025-09-14 and currently resolves to ' +
    'M247 (RO) and NTL (RU) infrastructure historically associated with this cluster. ' +
    'Two RAG sources (OTX, MITRE) describe identical TTPs; graph templates T2 and T3 ' +
    'connect the domain to TA-577 via shared cluster tag-xyz and SAN-pattern siblings. ' +
    'Storm-1811 surfaces as a secondary candidate (0.60) based on RAG overlap.',

  sources: [
    { type: 'graph', detail: 'T2_domain_to_actor — cluster tag-xyz' },
    { type: 'graph', detail: 'T3_infrastructure_pivot — SAN pattern' },
    { type: 'rag', detail: 'otx-1234 (OTX pulse)' },
    { type: 'rag', detail: 'mitre-456 (MITRE ATT&CK group page)' },
  ],
};
