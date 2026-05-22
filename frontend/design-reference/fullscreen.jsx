// Fullscreen card modal — opened by ⤢ button on each pinboard card.
// Renders a different fullscreen view per card kind. Includes a small
// node-edge graph component used inside the Candidates fullscreen.

function FullscreenCard({ cardKey, accent = '#4f46e5', onClose }) {
  if (!cardKey) return null;
  const titles = {
    attribution:    'Attribution result · full detail',
    candidates:     'Candidate actors · ranked evidence',
    infrastructure: 'Infrastructure · resolutions, certs, fingerprints',
    evidence:       'Evidence chain · sources & reasoning',
  };
  return (
    <div onClick={onClose} style={{
      position: 'absolute', inset: 0, zIndex: 100,
      background: 'rgba(13,17,36,0.45)',
      backdropFilter: 'blur(3px)',
      display: 'grid', placeItems: 'center',
      animation: 'fcfade .12s ease-out',
      fontFamily: 'var(--cti-sans)',
    }}>
      <style>{'@keyframes fcfade{from{opacity:0}to{opacity:1}}'}</style>
      <div onClick={(e) => e.stopPropagation()} style={{
        width: 'min(1100px, 92%)', maxHeight: '88%',
        background: '#fff', borderRadius: 14,
        boxShadow: '0 30px 80px rgba(0,0,0,0.3), 0 0 0 1px rgba(0,0,0,0.06)',
        display: 'flex', flexDirection: 'column', overflow: 'hidden',
        color: '#0d1124',
      }}>
        <div style={{
          padding: '14px 20px', borderBottom: '1px solid #e8eaf0',
          display: 'flex', alignItems: 'center', gap: 12,
        }}>
          <div style={{
            width: 26, height: 26, borderRadius: 7, background: `${accent}1a`,
            display: 'grid', placeItems: 'center',
          }}>
            <Icon name="ext" size={13} color={accent}/>
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 10.5, color: '#9ca0b0', fontWeight: 700, letterSpacing: 0.8, textTransform: 'uppercase' }}>Artifact detail</div>
            <div style={{ fontSize: 15, fontWeight: 600, marginTop: -1 }}>{titles[cardKey]}</div>
          </div>
          <button style={{
            width: 30, height: 30, border: 0, background: '#f3f4f9', borderRadius: 8,
            display: 'grid', placeItems: 'center', cursor: 'pointer', color: '#3a3f55',
          }} onClick={onClose} title="Close (Esc)">
            <Icon name="x" size={14}/>
          </button>
        </div>
        <div style={{ flex: 1, overflowY: 'auto', overflowX: 'hidden', padding: '20px 28px 28px' }}>
          {cardKey === 'attribution'    && <AttributionFullscreen/>}
          {cardKey === 'candidates'     && <CandidatesFullscreen accent={accent}/>}
          {cardKey === 'infrastructure' && <InfrastructureFullscreen accent={accent}/>}
          {cardKey === 'evidence'       && <EvidenceFullscreen/>}
        </div>
      </div>
    </div>
  );
}

// ---------- attribution fullscreen ----------

function AttributionFullscreen() {
  const t = ATTR_TOKENS[INTEL.attribution_result];
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <div style={{
        padding: 24, borderRadius: 12, background: `${t.dot}0d`,
        borderLeft: `4px solid ${t.dot}`,
      }}>
        <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: 0.8, color: t.fg, textTransform: 'uppercase' }}>
          {t.label}
        </div>
        <div style={{ fontSize: 32, fontWeight: 700, fontFamily: 'var(--cti-mono)', color: '#0d1124', marginTop: 6, letterSpacing: -0.5 }}>
          {INTEL.confidence.toFixed(2)}
        </div>
        <div style={{ fontSize: 13.5, color: '#3a3f55', marginTop: 8, maxWidth: 720, lineHeight: 1.6 }}>
          {INTEL.narrative}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 16 }}>
        <DetailBlock label="Attribution confidence" value={INTEL.confidence.toFixed(2)} bar={INTEL.confidence} color={t.dot}
          desc="Composite of graph-path strength and RAG corroboration."/>
        <DetailBlock label="Temporal confidence" value={INTEL.temporal_confidence.toFixed(2)} bar={INTEL.temporal_confidence} color="#6b6f7f"
          desc="Half-life decay (180d). Older evidence weighted lower."/>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 16 }}>
        <FlagBlock kind={INTEL.is_shared_infrastructure ? 'warn' : 'ok'}
          label="Shared infrastructure"
          sub={INTEL.is_shared_infrastructure ? 'CDN / cloud detected — infrastructure is multi-tenant' : 'Dedicated infrastructure — attribution weight unaffected'}/>
        <FlagBlock kind={INTEL.needs_more_evidence ? 'warn' : 'ok'}
          label="Evidence sufficiency"
          sub={INTEL.needs_more_evidence ? 'Pipeline recommends iteration — supply more IOCs or run extra templates' : 'Sufficient evidence — no iteration needed'}/>
      </div>

      <div>
        <SectionHead2>Sources used</SectionHead2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {INTEL.sources.map((s, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 12px', border: '1px solid #e8eaf0', borderRadius: 8 }}>
              <SourceBadge kind={s.type}/>
              <span style={{ fontSize: 12.5, color: '#3a3f55', fontFamily: 'var(--cti-mono)' }}>{s.detail}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function DetailBlock({ label, value, bar, color, desc }) {
  return (
    <div style={{ padding: 16, border: '1px solid #e8eaf0', borderRadius: 10, background: '#fbfbfd' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 8 }}>
        <div style={{ fontSize: 12, color: '#6b6f7f', fontWeight: 500 }}>{label}</div>
        <div style={{ fontSize: 22, fontWeight: 700, fontFamily: 'var(--cti-mono)', color: '#0d1124' }}>{value}</div>
      </div>
      <div style={{ height: 6, background: '#eef0f6', borderRadius: 99, overflow: 'hidden' }}>
        <div style={{ height: '100%', width: `${Math.round(bar * 100)}%`, background: color }}/>
      </div>
      <div style={{ fontSize: 12, color: '#6b6f7f', marginTop: 8 }}>{desc}</div>
    </div>
  );
}

function FlagBlock({ kind, label, sub }) {
  const c = kind === 'ok' ? '#10b981' : '#f59e0b';
  return (
    <div style={{
      padding: 14, border: `1px solid ${c}33`, borderRadius: 10, background: `${c}0d`,
      display: 'flex', alignItems: 'flex-start', gap: 10,
    }}>
      <span style={{ width: 8, height: 8, borderRadius: 99, background: c, marginTop: 6, flex: '0 0 8px' }}/>
      <div>
        <div style={{ fontSize: 13, fontWeight: 600, color: '#0d1124' }}>{label}</div>
        <div style={{ fontSize: 12, color: '#3a3f55', marginTop: 2, lineHeight: 1.5 }}>{sub}</div>
      </div>
    </div>
  );
}

// ---------- candidates fullscreen (with node-edge graph) ----------

function CandidatesFullscreen({ accent }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1.1fr 0.9fr', gap: 24 }}>
      <div>
        <SectionHead2>Candidates ranked by confidence</SectionHead2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {INTEL.candidate_actors.map(a => (
            <div key={a.actor_name} style={{
              padding: 14, border: '1px solid #e8eaf0', borderRadius: 10, background: '#fbfbfd',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <span style={{ fontSize: 16, fontWeight: 700, color: '#0d1124' }}>{a.actor_name}</span>
                <SourceBadge kind={a.source}/>
                <span style={{ marginLeft: 'auto', fontSize: 14, fontFamily: 'var(--cti-mono)', color: '#0d1124', fontWeight: 700 }}>{a.confidence.toFixed(2)}</span>
              </div>
              <div style={{ height: 4, background: '#eef0f6', borderRadius: 99, marginTop: 8, overflow: 'hidden' }}>
                <div style={{ height: '100%', width: `${Math.round(a.confidence * 100)}%`, background: '#0d1124' }}/>
              </div>
              <div style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 5 }}>
                {a.supporting_evidence.map((e, i) => (
                  <div key={i} style={{ fontSize: 12, color: '#3a3f55', display: 'flex', gap: 8, paddingLeft: 8, borderLeft: '2px solid #e8eaf0' }}>
                    <span style={{ color: '#9ca0b0' }}>•</span>
                    <span style={{ flex: 1, fontFamily: 'var(--cti-mono)' }}>{e}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div>
        <SectionHead2>Attribution path</SectionHead2>
        <div style={{
          padding: 16, border: '1px solid #e8eaf0', borderRadius: 10,
          background: '#fbfbfd', minHeight: 380,
        }}>
          <NodeEdgeGraph accent={accent}/>
          <div style={{ fontSize: 11.5, color: '#6b6f7f', marginTop: 8, paddingTop: 8, borderTop: '1px dashed #e8eaf0' }}>
            从 graph_paths 提取的真实路径 ·{' '}
            <span style={{ fontFamily: 'var(--cti-mono)' }}>T2_domain_to_actor</span> +{' '}
            <span style={{ fontFamily: 'var(--cti-mono)' }}>T3_infrastructure_pivot</span>
          </div>
        </div>
      </div>
    </div>
  );
}

function NodeEdgeGraph({ accent = '#4f46e5' }) {
  // Layout: domain (center-left) → cluster (center) → actor (right)
  //         siblings (top) ← infrastructure_pivot
  //         IPs (bottom) ← infrastructure
  const nodes = [
    { id: 'd',   x: 80,  y: 180, r: 30, label: 'hamadryas.online',  kind: 'domain',  mono: true },
    { id: 'c',   x: 240, y: 180, r: 22, label: 'tag-xyz',           kind: 'cluster' },
    { id: 'a',   x: 410, y: 180, r: 28, label: 'TA-577',            kind: 'actor' },

    { id: 's1',  x: 240, y: 60,  r: 16, label: 'sibling-a.online',  kind: 'sibling', mono: true },
    { id: 's2',  x: 320, y: 30,  r: 14, label: 'sibling-b.com',     kind: 'sibling', mono: true },
    { id: 's3',  x: 160, y: 50,  r: 14, label: 'sibling-c.shop',    kind: 'sibling', mono: true },

    { id: 'i1',  x: 80,  y: 310, r: 16, label: '185.244.42.91',     kind: 'ip',      mono: true },
    { id: 'i2',  x: 160, y: 340, r: 14, label: '91.219.236.18',     kind: 'ip',      mono: true },

    { id: 'cam', x: 530, y: 80,  r: 18, label: 'Storm-1811',        kind: 'campaign' },
  ];
  const edges = [
    { a: 'd', b: 'c',  label: 'in_cluster' },
    { a: 'c', b: 'a',  label: 'attributed_to' },
    { a: 'c', b: 's1', label: 'sibling' },
    { a: 'c', b: 's2', label: 'sibling' },
    { a: 'c', b: 's3', label: 'sibling' },
    { a: 'd', b: 'i1', label: 'resolves_to' },
    { a: 'd', b: 'i2', label: 'resolves_to' },
    { a: 'a', b: 'cam', label: 'runs_campaign' },
  ];

  const color = (k) => ({
    domain: '#0d1124', cluster: '#a4a8c2', actor: accent,
    sibling: '#9ca0b0', ip: '#10b981', campaign: '#f59e0b',
  }[k] || '#6b6f7f');

  const N = Object.fromEntries(nodes.map(n => [n.id, n]));

  return (
    <svg viewBox="0 0 590 380" style={{ width: '100%', height: 'auto', display: 'block' }}>
      <defs>
        <marker id="grarrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" markerHeight="6" orient="auto">
          <path d="M0,0 L8,4 L0,8 z" fill="#9ca0b0"/>
        </marker>
      </defs>

      {edges.map((e, i) => {
        const a = N[e.a], b = N[e.b];
        return (
          <g key={i}>
            <line x1={a.x} y1={a.y} x2={b.x} y2={b.y}
              stroke="#cdd1de" strokeWidth="1.2"
              strokeDasharray={e.label === 'sibling' ? '3 4' : 'none'}
              markerEnd={e.label === 'sibling' ? null : 'url(#grarrow)'}/>
          </g>
        );
      })}

      {nodes.map(n => (
        <g key={n.id}>
          <circle cx={n.x} cy={n.y} r={n.r}
            fill="#fff" stroke={color(n.kind)}
            strokeWidth={n.kind === 'domain' || n.kind === 'actor' ? 2 : 1.4}/>
          <text x={n.x} y={n.y + 4}
            textAnchor="middle"
            fontSize={n.kind === 'domain' || n.kind === 'actor' ? 10.5 : 9}
            fontFamily={n.mono ? 'var(--cti-mono)' : 'var(--cti-sans)'}
            fontWeight={n.kind === 'domain' || n.kind === 'actor' ? 600 : 500}
            fill={color(n.kind)}>
            {n.label.length > 14 ? n.label.slice(0, 12) + '…' : n.label}
          </text>
        </g>
      ))}

      {/* Legend */}
      <g transform="translate(10, 360)">
        {[['domain','#0d1124'], ['cluster','#a4a8c2'], ['actor', accent], ['ip','#10b981'], ['sibling','#9ca0b0']].map(([l, c], i) => (
          <g key={l} transform={`translate(${i * 92}, 0)`}>
            <circle cx="5" cy="6" r="4" fill="#fff" stroke={c} strokeWidth="1.2"/>
            <text x="14" y="9" fontSize="9.5" fill="#6b6f7f" fontFamily="var(--cti-sans)">{l}</text>
          </g>
        ))}
      </g>
    </svg>
  );
}

// ---------- infrastructure fullscreen ----------

function InfrastructureFullscreen({ accent }) {
  const e = INTEL.enrichment;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 14 }}>
        {[
          ['Domain',         INTEL.domain,                'mono'],
          ['Registrar',      e.rdap.registrar],
          ['Registered',     e.rdap.creation_date,        'mono'],
          ['Expires',        e.rdap.expiration_date,      'mono'],
          ['Active IPs',     `${e.current_ips.length} live · ${e.passive_dns.length} historical`],
          ['Certificates',   `${e.certificates.length} · Let's Encrypt`],
        ].map(([k, v, m]) => (
          <div key={k} style={{ padding: 12, background: '#fbfbfd', borderRadius: 8, border: '1px solid #e8eaf0' }}>
            <div style={{ fontSize: 10, color: '#9ca0b0', fontWeight: 700, letterSpacing: 0.6, textTransform: 'uppercase' }}>{k}</div>
            <div style={{ fontSize: 13.5, color: '#0d1124', fontFamily: m === 'mono' ? 'var(--cti-mono)' : 'inherit', marginTop: 3, fontWeight: 500 }}>{v}</div>
          </div>
        ))}
      </div>

      <div>
        <SectionHead2>Passive DNS timeline</SectionHead2>
        <PassiveDnsTimeline data={e.passive_dns} geoip={e.geoip} current={e.current_ips}/>
      </div>

      <div>
        <SectionHead2>Certificates</SectionHead2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {e.certificates.map(c => (
            <div key={c.fingerprint} style={{
              padding: 12, border: '1px solid #e8eaf0', borderRadius: 8,
              display: 'grid', gridTemplateColumns: '1.4fr 1fr 1fr', gap: 12, alignItems: 'center',
            }}>
              <div>
                <div style={{ fontSize: 10, color: '#9ca0b0', fontWeight: 700, letterSpacing: 0.6 }}>FINGERPRINT</div>
                <div style={{ fontSize: 12, fontFamily: 'var(--cti-mono)', color: '#0d1124', marginTop: 2 }}>{c.fingerprint}</div>
              </div>
              <div>
                <div style={{ fontSize: 10, color: '#9ca0b0', fontWeight: 700, letterSpacing: 0.6 }}>SAN</div>
                <div style={{ fontSize: 11.5, fontFamily: 'var(--cti-mono)', color: '#3a3f55', marginTop: 2 }}>
                  {c.san_list.join('  ·  ')}
                </div>
              </div>
              <div>
                <div style={{ fontSize: 10, color: '#9ca0b0', fontWeight: 700, letterSpacing: 0.6 }}>VALIDITY</div>
                <div style={{ fontSize: 11.5, fontFamily: 'var(--cti-mono)', color: '#3a3f55', marginTop: 2 }}>
                  {c.not_before} → {c.not_after}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div>
        <SectionHead2>Fingerprints</SectionHead2>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          <FingerprintBig label="JARM" value={e.jarm_hash} hint="TLS handshake hash · pivot on identical clients"/>
          <FingerprintBig label="favicon" value={e.favicon_hash} hint="mmh3 of favicon · pivot on identical UIs"/>
        </div>
      </div>
    </div>
  );
}

function PassiveDnsTimeline({ data, geoip, current }) {
  const t0 = Math.min(...data.map(p => +new Date(p.first_seen)));
  const tN = Math.max(...data.map(p => +new Date(p.last_seen)));
  const span = tN - t0 || 1;
  const lerp = (t) => ((+new Date(t)) - t0) / span * 100;
  return (
    <div style={{ border: '1px solid #e8eaf0', borderRadius: 8, padding: '14px 16px', background: '#fbfbfd' }}>
      {data.map((p, i) => {
        const g = geoip.find(x => x.ip === p.ip);
        const left = lerp(p.first_seen), right = lerp(p.last_seen);
        const live = current.includes(p.ip);
        return (
          <div key={p.ip} style={{
            display: 'grid', gridTemplateColumns: '170px 130px 1fr 100px',
            gap: 12, alignItems: 'center', padding: '8px 0',
            borderTop: i === 0 ? 0 : '1px dashed #e8eaf0',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ fontFamily: 'var(--cti-mono)', fontSize: 12, color: '#0d1124' }}>{p.ip}</span>
              {live && <span style={{ fontSize: 9, fontWeight: 700, color: '#0a5d2b', background: '#dcf5e6', padding: '1px 5px', borderRadius: 3 }}>LIVE</span>}
            </div>
            <div style={{ fontSize: 11.5, color: '#6b6f7f' }}>{g ? `${g.country} · AS${g.asn_number}` : '—'}</div>
            <div style={{ position: 'relative', height: 8, background: '#eef0f6', borderRadius: 99 }}>
              <div style={{
                position: 'absolute', top: 0, bottom: 0,
                left: `${left}%`, width: `${Math.max(right - left, 2)}%`,
                background: live ? '#10b981' : '#a4a8c2', borderRadius: 99,
              }}/>
            </div>
            <div style={{ fontSize: 10.5, fontFamily: 'var(--cti-mono)', color: '#9ca0b0', textAlign: 'right' }}>
              {p.first_seen.slice(5)} → {p.last_seen.slice(5)}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function FingerprintBig({ label, value, hint }) {
  return (
    <div style={{
      flex: '1 1 320px', padding: '12px 14px', border: '1px solid #e8eaf0',
      borderRadius: 8, background: '#fbfbfd',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <Icon name="fingerprint" size={13} color="#6b6f7f"/>
        <span style={{ fontSize: 11, fontWeight: 700, color: '#6b6f7f', letterSpacing: 0.4, textTransform: 'uppercase' }}>{label}</span>
        <button style={{ marginLeft: 'auto', border: 0, background: 'transparent', color: '#9ca0b0', cursor: 'pointer', display: 'grid', placeItems: 'center', padding: 2 }} title="Copy">
          <Icon name="copy" size={12}/>
        </button>
      </div>
      <div style={{ fontFamily: 'var(--cti-mono)', fontSize: 12, color: '#0d1124', marginTop: 6, wordBreak: 'break-all' }}>{value}</div>
      <div style={{ fontSize: 11, color: '#9ca0b0', marginTop: 6 }}>{hint}</div>
    </div>
  );
}

// ---------- evidence fullscreen ----------

function EvidenceFullscreen() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
      <div>
        <SectionHead2>Evidence chain</SectionHead2>
        <ol style={{ margin: 0, padding: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 10 }}>
          {INTEL.evidence_chain.map((e, i) => (
            <li key={i} style={{
              padding: '10px 14px', border: '1px solid #e8eaf0', borderRadius: 8,
              background: '#fbfbfd', display: 'flex', gap: 12, alignItems: 'flex-start',
            }}>
              <span style={{
                width: 22, height: 22, borderRadius: 99, background: '#0d1124', color: '#fff',
                fontFamily: 'var(--cti-mono)', fontSize: 11, fontWeight: 600,
                display: 'grid', placeItems: 'center', flex: '0 0 22px',
              }}>{i + 1}</span>
              <span style={{ fontSize: 13, color: '#3a3f55', lineHeight: 1.55 }}>{e}</span>
            </li>
          ))}
        </ol>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 22 }}>
        <div>
          <SectionHead2>Graph paths (Cypher)</SectionHead2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {INTEL.graph_paths.map(g => (
              <div key={g.template} style={{
                padding: '10px 12px', border: '1px solid #e8eaf0', borderRadius: 8,
                background: '#fbfbfd',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <StatusPill status={g.status}/>
                  <span style={{ fontFamily: 'var(--cti-mono)', fontSize: 12, color: '#0d1124', fontWeight: 500 }}>{g.template}</span>
                </div>
                <div style={{ fontSize: 12, color: '#6b6f7f', marginTop: 4 }}>{g.summary}</div>
              </div>
            ))}
          </div>
        </div>

        <div>
          <SectionHead2>RAG chunks (top by RRF)</SectionHead2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {INTEL.rag_chunks.map(c => (
              <div key={c.chunk_id} style={{
                padding: '10px 12px', border: '1px solid #e8eaf0', borderRadius: 8, background: '#fbfbfd',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 5 }}>
                  <span style={{
                    fontFamily: 'var(--cti-mono)', fontSize: 10.5,
                    padding: '2px 6px', borderRadius: 3,
                    background: '#eef0f6', color: '#3a3f55',
                    fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.5,
                  }}>{c.source}</span>
                  <span style={{ fontSize: 10.5, color: '#9ca0b0', fontFamily: 'var(--cti-mono)' }}>{c.chunk_id}</span>
                  <span style={{ marginLeft: 'auto', fontSize: 11, fontFamily: 'var(--cti-mono)', color: '#0d1124', fontWeight: 600 }}>RRF {c.rrf_score.toFixed(2)}</span>
                </div>
                <div style={{ fontSize: 12, color: '#3a3f55', fontStyle: 'italic', lineHeight: 1.55 }}>"{c.snippet}"</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function StatusPill({ status }) {
  const tok = {
    success: { c: '#10b981', l: 'SUCCESS' },
    empty:   { c: '#9ca0b0', l: 'EMPTY' },
    error:   { c: '#dc2626', l: 'ERROR' },
    no_match:{ c: '#f59e0b', l: 'NO MATCH' },
  }[status] || { c: '#9ca0b0', l: status.toUpperCase() };
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 4,
      padding: '2px 7px', borderRadius: 99, background: `${tok.c}1f`,
      fontSize: 9.5, fontWeight: 700, letterSpacing: 0.6, color: tok.c,
      fontFamily: 'var(--cti-mono)',
    }}>
      <span style={{ width: 5, height: 5, borderRadius: 99, background: tok.c }}/>
      {tok.l}
    </span>
  );
}

function SectionHead2({ children }) {
  return (
    <div style={{
      fontSize: 11, fontWeight: 700, color: '#6b6f7f', letterSpacing: 0.8,
      textTransform: 'uppercase', marginBottom: 10,
    }}>{children}</div>
  );
}

Object.assign(window, { FullscreenCard, NodeEdgeGraph, MiniNodeGraph, StatusPill });

// ---------- compact inline graph (used in Candidates pinned card) ----------

function MiniNodeGraph({ accent = '#7c3aed' }) {
  // Horizontal flow: domain → cluster → actor, with small satellites
  const nodes = [
    { id: 'd',  x: 28,  y: 70, r: 18, label: 'hamadryas',  kind: 'domain', mono: true },
    { id: 'c',  x: 160, y: 70, r: 14, label: 'tag-xyz',    kind: 'cluster' },
    { id: 'a',  x: 290, y: 70, r: 18, label: 'TA-577',     kind: 'actor' },
    { id: 's1', x: 130, y: 18, r: 8,  label: 'sib·a',      kind: 'sibling', mono: true },
    { id: 's2', x: 190, y: 18, r: 7,  label: 'sib·b',      kind: 'sibling', mono: true },
    { id: 'cam', x: 320, y: 22, r: 10, label: 'Storm-1811', kind: 'campaign' },
    { id: 'i1', x: 35,  y: 122, r: 7, label: '185.244…',  kind: 'ip',     mono: true },
  ];
  const edges = [
    { a: 'd', b: 'c', dir: true },
    { a: 'c', b: 'a', dir: true },
    { a: 'c', b: 's1', dashed: true },
    { a: 'c', b: 's2', dashed: true },
    { a: 'a', b: 'cam' },
    { a: 'd', b: 'i1', dashed: true },
  ];
  const color = (k) => ({
    domain: '#0d1124', cluster: '#a4a8c2', actor: accent,
    sibling: '#9ca0b0', ip: '#10b981', campaign: '#f59e0b',
  }[k] || '#6b6f7f');
  const N = Object.fromEntries(nodes.map(n => [n.id, n]));
  return (
    <svg viewBox="0 0 360 150" style={{ width: '100%', height: 'auto', display: 'block' }}>
      <defs>
        <marker id="mngArr" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="5" markerHeight="5" orient="auto">
          <path d="M0,0 L8,4 L0,8 z" fill="#9ca0b0"/>
        </marker>
      </defs>
      {edges.map((e, i) => {
        const a = N[e.a], b = N[e.b];
        return (
          <line key={i} x1={a.x} y1={a.y} x2={b.x} y2={b.y}
            stroke="#cdd1de" strokeWidth="1.1"
            strokeDasharray={e.dashed ? '3 4' : 'none'}
            markerEnd={e.dir ? 'url(#mngArr)' : null}/>
        );
      })}
      {nodes.map(n => (
        <g key={n.id}>
          <circle cx={n.x} cy={n.y} r={n.r}
            fill="#fff" stroke={color(n.kind)}
            strokeWidth={n.kind === 'domain' || n.kind === 'actor' ? 1.8 : 1.2}/>
          <text x={n.x} y={n.y + 3.5}
            textAnchor="middle"
            fontSize={n.kind === 'domain' || n.kind === 'actor' ? 9.5 : 8}
            fontFamily={n.mono ? 'var(--cti-mono)' : 'var(--cti-sans)'}
            fontWeight={n.kind === 'domain' || n.kind === 'actor' ? 600 : 500}
            fill={color(n.kind)}>{n.label}</text>
        </g>
      ))}
    </svg>
  );
}
