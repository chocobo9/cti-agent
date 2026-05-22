// Shared intel data + small UI atoms.
// SHAPE IS ALIGNED WITH BACKEND `AttributionState` — no risk_score, no VT,
// no MITRE TTP mapping, no Playbook. Built around the attribution-confidence
// pipeline (supervisor → infrastructure → intelligence → graph_probe →
// evidence_eval → report).

const INTEL = {
  query: '谁控制 hamadryas.online？',
  domain: 'hamadryas.online',
  query_type: 'structural',

  // Attribution evaluation
  attribution_result: 'high_confidence',  // high_/medium_/low_confidence / insufficient
  confidence: 0.85,
  temporal_confidence: 0.72,              // 180d half-life decay
  is_shared_infrastructure: false,
  needs_more_evidence: false,

  // Candidate actors (ranked) — from graph path / RAG / LLM inference
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

  // Enrichment data (pre-staged in Neo4j; surfaced by graph queries)
  enrichment: {
    passive_dns: [
      { ip: '185.244.42.91',  first_seen: '2025-09-22', last_seen: '2025-11-14' },
      { ip: '91.219.236.18',  first_seen: '2025-09-29', last_seen: '2025-11-14' },
      { ip: '45.137.190.222', first_seen: '2025-10-08', last_seen: '2025-11-01' },
    ],
    current_ips: ['185.244.42.91', '91.219.236.18'],
    rdap: {
      creation_date: '2025-09-14',
      expiration_date: '2026-09-14',
      registrar: 'Njalla AB',
    },
    certificates: [
      { fingerprint: 'a3f5c8e2…c9f3', issuer: "Let's Encrypt", san_list: ['*.hamadryas.online', 'hamadryas.online'], not_before: '2025-09-22', not_after: '2025-12-21' },
      { fingerprint: 'd8b1f44a…12ab', issuer: "Let's Encrypt", san_list: ['auth.hamadryas.online'],                  not_before: '2025-09-26', not_after: '2025-12-25' },
    ],
    geoip: [
      { ip: '185.244.42.91', asn_number: 9009,  asn_name: 'M247 Ltd', country: 'RO', city: 'Bucharest' },
      { ip: '91.219.236.18', asn_number: 49447, asn_name: 'NTL LLC',  country: 'RU', city: 'Moscow' },
      { ip: '45.137.190.222', asn_number: 59729, asn_name: 'NeTerra', country: 'BG', city: 'Sofia' },
    ],
    jarm_hash:    '2ad2ad0002ad2ad22c2ad2ad2ad2ad…',
    favicon_hash: 'ab12c3d4e5f6789a…',
  },

  // Graph queries actually run (Cypher templates)
  graph_paths: [
    { status: 'success', template: 'T1_domain_infrastructure', summary: '1 active IP, 2 historical IPs, 2 certificates' },
    { status: 'success', template: 'T2_domain_to_actor',       summary: 'linked to TA-577 via cluster tag-xyz' },
    { status: 'success', template: 'T3_infrastructure_pivot',  summary: '3 sibling domains share SAN pattern' },
    { status: 'empty',   template: 'T5_certificate_pivot',     summary: 'no further matches' },
    { status: 'success', template: 'T7_temporal_correlation',  summary: 'campaign Storm-1811 active 2025-09 → now' },
  ],

  // RAG retrieval (top chunks)
  rag_chunks: [
    { chunk_id: 'otx-1234',  source: 'otx',   rrf_score: 0.82, snippet: 'TA-577 observed using Njalla-registered domains with M247 hosting for Pikabot delivery in late 2025.' },
    { chunk_id: 'mitre-456', source: 'mitre', rrf_score: 0.71, snippet: 'Storm-1811 campaign targeting financial sector via spearphishing links to credential-harvesting kits.' },
    { chunk_id: 'blog-789',  source: 'blog',  rrf_score: 0.66, snippet: 'Latrodectus loader infrastructure showed overlap with TA-577 in October 2025 reporting.' },
  ],

  // Evidence chain (transparency)
  evidence_chain: [
    'R1 infrastructure: T1 found 1 active IP (M247/RO), T2 linked to TA-577 via cluster tag-xyz',
    'R1 intelligence: 12 RAG chunks retrieved, top 3 (RRF > 0.6) corroborate TA-577 association',
    'graph_probe: validated actor TA-577 exists in graph (5 related domains, 2 active campaigns)',
    'evidence_eval: confidence = 0.85, temporal_confidence = 0.72, high_confidence — no iteration needed',
    'report: synthesized graph + RAG into attribution narrative',
  ],

  // Final narrative (from attribution_report.narrative)
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
    { type: 'rag',   detail: 'otx-1234 (OTX pulse)' },
    { type: 'rag',   detail: 'mitre-456 (MITRE ATT&CK group page)' },
  ],
};

// 6-node LangGraph pipeline
const NODES_RUN = [
  { id: 'supervisor',     label: 'Supervisor 路由',          status: 'done',    ms: 240,  sub: 'query_type → structural' },
  { id: 'infrastructure', label: 'Infrastructure (Cypher×5)', status: 'done',    ms: 1840, sub: '5 templates · 4 success / 1 empty' },
  { id: 'intelligence',   label: 'Intelligence (RAG)',         status: 'done',    ms: 1290, sub: '12 chunks · top 3 RRF > 0.6' },
  { id: 'graph_probe',    label: 'Graph 验证',                 status: 'done',    ms: 480,  sub: '3 candidate actors validated' },
  { id: 'evidence_eval',  label: 'Evidence 评估',              status: 'done',    ms: 620,  sub: 'confidence = 0.85 · no iter.' },
  { id: 'report',         label: 'Report 合成',                status: 'running', ms: 0,    sub: 'rendering markdown…' },
];

const EXAMPLE_PROMPTS = [
  { icon: 'globe',  title: '谁控制这个域名？',      sub: 'Graph + RAG 综合归因' },
  { icon: 'target', title: '这个 IOC 关联到哪个组织？', sub: 'Cypher 模板路径检索' },
  { icon: 'graph',  title: '展示基础设施关联',       sub: 'passive DNS / 证书 / JARM 指纹' },
  { icon: 'doc',    title: '证据链可视化',           sub: '透明的推理轨迹' },
];

// ---------- attribution-result tokens (HIGH/MED/LOW/INSUFFICIENT) ----------

const ATTR_TOKENS = {
  high_confidence:   { label: 'High confidence',   fg: '#0a5d2b', bg: '#dcf5e6', dot: '#10b981' },
  medium_confidence: { label: 'Medium confidence', fg: '#8a5a00', bg: '#fff3d6', dot: '#f59e0b' },
  low_confidence:    { label: 'Low confidence',    fg: '#9c3a1b', bg: '#fde2d6', dot: '#ea580c' },
  insufficient:      { label: 'Insufficient',      fg: '#3a3d44', bg: '#ececea', dot: '#9ca0b0' },
};

function ConfidenceBadge({ kind = 'high_confidence', size = 'sm' }) {
  const t = ATTR_TOKENS[kind] || ATTR_TOKENS.insufficient;
  const pad = size === 'lg' ? '4px 10px' : '2px 8px';
  const fs  = size === 'lg' ? 12 : 11;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      padding: pad, borderRadius: 999, fontSize: fs, fontWeight: 600,
      color: t.fg, background: t.bg, letterSpacing: 0.1,
      fontFamily: 'var(--cti-sans)',
    }}>
      <span style={{ width: 5, height: 5, borderRadius: 99, background: t.dot }}/>
      {t.label}
    </span>
  );
}

const SOURCE_TOKENS = {
  graph: { label: 'GRAPH', fg: '#3b1a8f', bg: '#ede9fc' },
  rag:   { label: 'RAG',   fg: '#0a5078', bg: '#dfecf6' },
  llm:   { label: 'LLM',   fg: '#6b6f78', bg: '#ececea' },
};

function SourceBadge({ kind = 'graph' }) {
  const t = SOURCE_TOKENS[kind] || SOURCE_TOKENS.graph;
  return (
    <span style={{
      fontFamily: 'var(--cti-mono)', fontSize: 9.5, fontWeight: 700,
      letterSpacing: 0.8, padding: '2px 6px', borderRadius: 3,
      color: t.fg, background: t.bg,
    }}>{t.label}</span>
  );
}

// Inline icons — flat 1.5px stroke, lucide-ish, no fills.
function Icon({ name, size = 16, color = 'currentColor', strokeWidth = 1.6 }) {
  const P = {
    width: size, height: size, viewBox: '0 0 24 24', fill: 'none',
    stroke: color, strokeWidth, strokeLinecap: 'round', strokeLinejoin: 'round',
  };
  switch (name) {
    case 'globe':   return <svg {...P}><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 010 18M12 3a14 14 0 000 18"/></svg>;
    case 'hash':    return <svg {...P}><path d="M4 9h16M4 15h16M10 3L8 21M16 3l-2 18"/></svg>;
    case 'shield':  return <svg {...P}><path d="M12 3l8 3v6c0 5-3.5 8.5-8 9-4.5-.5-8-4-8-9V6l8-3z"/></svg>;
    case 'target':  return <svg {...P}><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/></svg>;
    case 'send':    return <svg {...P}><path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/></svg>;
    case 'attach':  return <svg {...P}><path d="M21 11.5l-9 9a5 5 0 01-7-7l9-9a3.5 3.5 0 015 5l-9 9a2 2 0 01-3-3l8-8"/></svg>;
    case 'plus':    return <svg {...P}><path d="M12 5v14M5 12h14"/></svg>;
    case 'check':   return <svg {...P}><path d="M4 12l5 5L20 6"/></svg>;
    case 'x':       return <svg {...P}><path d="M5 5l14 14M19 5L5 19"/></svg>;
    case 'spark':   return <svg {...P}><path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l3 3M15 15l3 3M6 18l3-3M15 9l3-3"/></svg>;
    case 'chevron': return <svg {...P}><path d="M9 18l6-6-6-6"/></svg>;
    case 'down':    return <svg {...P}><path d="M6 9l6 6 6-6"/></svg>;
    case 'ext':     return <svg {...P}><path d="M14 4h6v6M20 4l-8 8M14 12v6H4V8h6"/></svg>;
    case 'copy':    return <svg {...P}><rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V5a2 2 0 012-2h10"/></svg>;
    case 'graph':   return <svg {...P}><circle cx="6" cy="6" r="2.5"/><circle cx="18" cy="7" r="2.5"/><circle cx="17" cy="18" r="2.5"/><circle cx="5" cy="17" r="2.5"/><circle cx="12" cy="12" r="2.5"/><path d="M8 7l2 4M16 8l-3 3M15 17l-2-3M7 16l3-3"/></svg>;
    case 'doc':     return <svg {...P}><path d="M14 3H6a2 2 0 00-2 2v14a2 2 0 002 2h12a2 2 0 002-2V9l-6-6z"/><path d="M14 3v6h6M8 13h8M8 17h5"/></svg>;
    case 'time':    return <svg {...P}><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>;
    case 'cpu':     return <svg {...P}><rect x="5" y="5" width="14" height="14" rx="2"/><rect x="9" y="9" width="6" height="6"/><path d="M9 3v2M15 3v2M9 19v2M15 19v2M3 9h2M3 15h2M19 9h2M19 15h2"/></svg>;
    case 'flame':   return <svg {...P}><path d="M12 3c2 4-1 5-1 8a4 4 0 008 0c0-1-1-2-2-3 1 3-1 4-2 4 0-2-1-3-3-9z"/></svg>;
    case 'menu':    return <svg {...P}><path d="M4 6h16M4 12h16M4 18h16"/></svg>;
    case 'search':  return <svg {...P}><circle cx="11" cy="11" r="7"/><path d="M21 21l-5-5"/></svg>;
    case 'play':    return <svg {...P}><path d="M6 4l14 8-14 8V4z"/></svg>;
    case 'side':    return <svg {...P}><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16"/></svg>;
    case 'flag':    return <svg {...P}><path d="M5 21V4h12l-2 4 2 4H5"/></svg>;
    case 'pin':     return <svg {...P}><path d="M12 2v6l4 3v3H8v-3l4-3V2zM12 14v8"/></svg>;
    case 'spinner': return <svg {...P}><path d="M12 3a9 9 0 019 9" opacity="0.3"/><path d="M12 3a9 9 0 00-9 9"/></svg>;
    case 'bolt':    return <svg {...P}><path d="M13 2L4 14h7l-1 8 9-12h-7l1-8z"/></svg>;
    case 'eye':     return <svg {...P}><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8S1 12 1 12z"/><circle cx="12" cy="12" r="3"/></svg>;
    case 'lock':    return <svg {...P}><rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 018 0v4"/></svg>;
    case 'arrowR':  return <svg {...P}><path d="M5 12h14M13 6l6 6-6 6"/></svg>;
    case 'sort':    return <svg {...P}><path d="M7 4v16M7 4l-3 3M7 4l3 3M17 20V4M17 20l-3-3M17 20l3-3"/></svg>;
    case 'history': return <svg {...P}><path d="M3 12a9 9 0 109-9 9 9 0 00-6.4 2.6L3 8M3 3v5h5M12 7v5l3 2"/></svg>;
    case 'fingerprint': return <svg {...P}><path d="M12 11v3a6 6 0 01-1 3M9 11a3 3 0 016 0v2a8 8 0 01-1 4M6 11a6 6 0 0110-4M18 13v1a10 10 0 01-.5 3M4 14v-3a8 8 0 0114-5"/></svg>;
    default: return null;
  }
}

// Expose to other scripts (Babel files don't share scope).
Object.assign(window, {
  INTEL, NODES_RUN, EXAMPLE_PROMPTS,
  ATTR_TOKENS, SOURCE_TOKENS, ConfidenceBadge, SourceBadge, Icon,
});
