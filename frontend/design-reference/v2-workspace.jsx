// V2 — Medium. Case-driven 3-column workspace.
// Aligned with backend AttributionState. Pinboard cards:
//   1) ATTRIBUTION RESULT — confidence / temporal / shared-infra flag
//   2) CANDIDATES — ranked candidate actors with source badges + evidence
//   3) INFRASTRUCTURE — passive DNS, certs, JARM, favicon
//   4) EVIDENCE CHAIN — transparent reasoning trail
// PinboardColumn is also reused inside V1.b via window.

function V2Workspace() {
  const accent = '#4f46e5';
  const [fs, setFs] = React.useState(null);
  return (
    <div style={{
      width: '100%', height: '100%', display: 'flex', flexDirection: 'column',
      background: '#f6f7fb', color: '#0d1124', fontFamily: 'var(--cti-sans)',
      fontSize: 13.5, lineHeight: 1.5, overflow: 'hidden', position: 'relative',
    }}>
      {/* App bar */}
      <header style={{
        height: 46, flex: '0 0 46px', background: '#fff',
        borderBottom: '1px solid #e8eaf0', display: 'flex', alignItems: 'center',
        padding: '0 16px', gap: 14,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 600, letterSpacing: -0.2 }}>
          <div style={{
            width: 22, height: 22, borderRadius: 6, background: accent,
            display: 'grid', placeItems: 'center', color: '#fff',
          }}>
            <Icon name="bolt" size={12} color="#fff"/>
          </div>
          <span style={{ fontSize: 14 }}>Hamadryas</span>
          <span style={{ fontSize: 11, color: '#9ca0b0', background: '#eef0f6', padding: '2px 7px', borderRadius: 4, fontWeight: 500 }}>CTI</span>
        </div>

        <div style={{
          marginLeft: 16, flex: 1, maxWidth: 460, height: 28,
          background: '#f3f4f9', borderRadius: 7, display: 'flex', alignItems: 'center',
          padding: '0 10px', gap: 8, color: '#6b6f7f', fontSize: 12.5,
        }}>
          <Icon name="search" size={13}/>
          <span style={{ flex: 1 }}>询问归因 · 粘贴 IOC · 搜索历史…</span>
          <span style={{ fontFamily: 'var(--cti-mono)', fontSize: 10.5, background: '#fff', padding: '1px 5px', borderRadius: 4, border: '1px solid #e2e4ed' }}>⌘K</span>
        </div>

        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 6 }}>
          <button style={v2GhostBtn()}><Icon name="history" size={13}/> History</button>
          <button style={v2GhostBtn()}><Icon name="doc" size={13}/> Reports</button>
          <button style={{ ...v2GhostBtn(), background: '#0d1124', color: '#fff', borderColor: '#0d1124' }}>
            <Icon name="plus" size={13}/> New query
          </button>
          <div style={{
            marginLeft: 4, width: 26, height: 26, borderRadius: 99,
            background: '#dfe1ec', display: 'grid', placeItems: 'center',
            fontSize: 10.5, fontWeight: 600, color: '#4a4d5a',
          }}>SY</div>
        </div>
      </header>

      {/* 3 columns */}
      <div style={{ flex: 1, display: 'flex', minHeight: 0 }}>
        <HistorySidebar accent={accent}/>
        <ChatColumn accent={accent}/>
        <PinboardColumn accent={accent} onOpenCard={setFs}/>
      </div>

      {fs && window.FullscreenCard && (
        <window.FullscreenCard cardKey={fs} accent={accent} onClose={() => setFs(null)}/>
      )}
    </div>
  );
}

// ---------- left: history ----------

function HistorySidebar({ accent }) {
  const items = [
    { id: 1, q: 'hamadryas.online',                      result: 'high_confidence',    when: 'now',     active: true },
    { id: 2, q: 'auth-microsft365.com',                  result: 'medium_confidence',  when: '2h ago' },
    { id: 3, q: '185.244.42.91 关联组织？',              result: 'high_confidence',    when: 'Today' },
    { id: 4, q: 'login-portal-update.shop',              result: 'low_confidence',     when: 'Yesterday' },
    { id: 5, q: 'TA-577 近期基础设施',                   result: 'medium_confidence',  when: '2d' },
    { id: 6, q: 'JARM 2ad2ad0002 谁在用？',              result: 'medium_confidence',  when: '3d' },
    { id: 7, q: 'cdn-static-host.online',                result: 'insufficient',       when: '5d' },
  ];
  const dot = (r) => ({
    background: ATTR_TOKENS[r].dot,
    width: 6, height: 6, borderRadius: 99, flex: '0 0 6px',
  });
  return (
    <aside style={{
      width: 240, flex: '0 0 240px', borderRight: '1px solid #e8eaf0',
      background: '#fbfbfd', padding: '14px 10px', display: 'flex',
      flexDirection: 'column', gap: 18, overflow: 'hidden',
    }}>
      <div>
        <SidebarLabel>Quick lookup</SidebarLabel>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, marginTop: 6 }}>
          {[
            ['globe','Domain'], ['target','IP'], ['fingerprint','JARM'], ['shield','SAN'],
          ].map(([n, l]) => (
            <button key={l} style={{
              padding: '8px 10px', borderRadius: 8, border: '1px solid #e8eaf0',
              background: '#fff', display: 'flex', alignItems: 'center', gap: 6,
              fontSize: 12, color: '#0d1124', cursor: 'pointer', fontFamily: 'inherit',
            }}>
              <Icon name={n} size={13}/> {l}
            </button>
          ))}
        </div>
      </div>

      <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <SidebarLabel>History</SidebarLabel>
          <button style={{ border: 0, background: 'transparent', color: '#6b6f7f', cursor: 'pointer' }} title="Clear">
            <Icon name="x" size={12}/>
          </button>
        </div>
        <div style={{ marginTop: 4, display: 'flex', flexDirection: 'column', gap: 1, overflow: 'hidden' }}>
          {items.map(c => (
            <button key={c.id} style={{
              display: 'flex', alignItems: 'center', gap: 8,
              padding: '7px 8px', borderRadius: 7, border: 0, cursor: 'pointer',
              background: c.active ? '#eef0fb' : 'transparent',
              fontFamily: 'inherit', textAlign: 'left', width: '100%',
              color: '#0d1124',
            }}>
              <span style={dot(c.result)}/>
              <span style={{
                flex: 1, fontSize: 12.5, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                fontWeight: c.active ? 600 : 500,
                color: c.active ? '#0d1124' : '#3a3f55',
              }}>{c.q}</span>
              <span style={{ fontSize: 10.5, color: '#9ca0b0', flex: '0 0 auto' }}>{c.when}</span>
            </button>
          ))}
        </div>
      </div>

      <div>
        <SidebarLabel>Saved queries</SidebarLabel>
        <div style={{ marginTop: 4, fontSize: 12.5, color: '#3a3f55', display: 'flex', flexDirection: 'column', gap: 2 }}>
          {['TA-577 近 30 天关联域', 'Njalla 注册 + M247 hosting', 'Pikabot delivery JARM'].map(s => (
            <div key={s} style={{ padding: '5px 8px', borderRadius: 6, display: 'flex', alignItems: 'center', gap: 6 }}>
              <Icon name="pin" size={11} color="#9ca0b0"/>{s}
            </div>
          ))}
        </div>
      </div>
    </aside>
  );
}

function SidebarLabel({ children }) {
  return <div style={{
    fontSize: 10.5, color: '#9ca0b0', textTransform: 'uppercase', letterSpacing: 0.6,
    fontWeight: 600, padding: '0 6px',
  }}>{children}</div>;
}

// ---------- middle: chat ----------

function ChatColumn({ accent }) {
  return (
    <section style={{
      flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0,
      borderRight: '1px solid #e8eaf0', background: '#f6f7fb',
    }}>
      {/* Query header */}
      <div style={{
        padding: '14px 24px', borderBottom: '1px solid #e8eaf0',
        background: '#fff', display: 'flex', alignItems: 'center', gap: 12,
      }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{
            fontSize: 11, color: '#6b6f7f', letterSpacing: 0.4, textTransform: 'uppercase',
          }}>Query · Q-2025-1042 · structural</div>
          <div style={{
            display: 'flex', alignItems: 'center', gap: 8, marginTop: 2,
            fontSize: 15.5, fontWeight: 600, letterSpacing: -0.2,
          }}>
            {INTEL.query}
            <ConfidenceBadge kind={INTEL.attribution_result}/>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11.5, color: '#6b6f7f' }}>
          <Icon name="time" size={12}/> 5.0s · 6 nodes · 3 candidates
        </div>
      </div>

      <div style={{ flex: 1, overflow: 'hidden', padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: 16 }}>
        {/* User */}
        <div style={{ alignSelf: 'flex-end', maxWidth: '80%' }}>
          <div style={{
            background: '#fff', border: '1px solid #e8eaf0', borderRadius: 12,
            padding: '10px 14px', fontSize: 13.5,
          }}>{INTEL.query}</div>
        </div>

        {/* Node queue */}
        <V2NodeQueue accent={accent}/>

        {/* Result narrative */}
        <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
          <div style={{ width: 24, height: 24, borderRadius: 6, background: '#0d1124', display: 'grid', placeItems: 'center', flex: '0 0 24px' }}>
            <Icon name="spark" size={12} color="#fff"/>
          </div>
          <div style={{ flex: 1, fontSize: 13, color: '#3a3f55', lineHeight: 1.6 }}>
            {INTEL.narrative}
            <div style={{ marginTop: 10, display: 'flex', flexWrap: 'wrap', gap: 5 }}>
              {[
                ['📄', '查看证据链'], ['👥', '展开候选演员'],
                ['📤', '复制 Markdown'], ['💾', '导出 JSON'],
              ].map(([e, t]) => (
                <button key={t} style={{
                  padding: '5px 10px', borderRadius: 999, border: '1px solid #e2e4ed',
                  background: '#fff', fontSize: 11.5, cursor: 'pointer', fontFamily: 'inherit', color: '#0d1124',
                  display: 'inline-flex', alignItems: 'center', gap: 5,
                }}><span style={{ fontSize: 11 }}>{e}</span>{t}</button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Composer */}
      <div style={{ padding: '0 24px 18px' }}>
        <div style={{
          background: '#fff', borderRadius: 12, border: '1px solid #e2e4ed',
          padding: '12px 14px 8px', boxShadow: '0 1px 0 rgba(20,20,40,0.04)',
        }}>
          <div style={{ color: '#9ca0b0', fontSize: 13, minHeight: 32 }}>追问 · e.g. "用 T3 模板查 SAN 相邻域"</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <button style={v2IconBtn()}><Icon name="attach" size={14}/></button>
            <span style={v2Pill()}>🔁 iterate</span>
            <span style={v2Pill()}>🧪 graph only</span>
            <span style={v2Pill()}>📚 RAG only</span>
            <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 11, color: '#9ca0b0' }}>⌘↵ to send</span>
              <button style={{
                width: 28, height: 28, borderRadius: 7, background: accent, border: 0,
                display: 'grid', placeItems: 'center', cursor: 'pointer', color: '#fff',
              }}><Icon name="arrowR" size={14} color="#fff"/></button>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function V2NodeQueue({ accent }) {
  const running = NODES_RUN.filter(n => n.status === 'running').length;
  const done    = NODES_RUN.filter(n => n.status === 'done').length;
  return (
    <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
      <div style={{ width: 24, height: 24, borderRadius: 6, background: '#0d1124', display: 'grid', placeItems: 'center', flex: '0 0 24px' }}>
        <Icon name="spark" size={12} color="#fff"/>
      </div>
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: 11.5, color: '#6b6f7f', marginBottom: 6, display: 'flex', alignItems: 'center', gap: 6 }}>
          <span>LangGraph · {done}/{NODES_RUN.length} nodes</span>
          {running > 0 && <>
            <span style={{ width: 2, height: 2, borderRadius: 99, background: '#9ca0b0' }}/>
            <span style={{ color: accent, fontWeight: 600 }}>{running} 进行中</span>
          </>}
        </div>
        <div style={{
          display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 6,
        }}>
          {NODES_RUN.map(n => (
            <NodeCardCompact key={n.id} n={n} accent={accent}/>
          ))}
        </div>
      </div>
    </div>
  );
}

function NodeCardCompact({ n, accent }) {
  const state = n.status;
  return (
    <div style={{
      background: '#fff', border: '1px solid #e8eaf0', borderRadius: 8,
      padding: '8px 10px', display: 'flex', flexDirection: 'column', gap: 4,
      borderLeft: state === 'done' ? '3px solid #10b981' : state === 'running' ? `3px solid ${accent}` : '3px solid #e2e4ed',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        {state === 'done' && <Icon name="check" size={11} color="#10b981"/>}
        {state === 'running' && <div style={{ width: 10, height: 10, borderRadius: 99, border: `1.5px solid ${accent}`, borderTopColor: 'transparent', animation: 'v2spin .9s linear infinite' }}/>}
        {state === 'queued' && <Icon name="time" size={11} color="#9ca0b0"/>}
        <span style={{ fontSize: 11.5, fontWeight: 500, color: '#0d1124', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{n.label}</span>
      </div>
      <div style={{ fontSize: 10, color: '#9ca0b0', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {n.sub}
      </div>
      <div style={{ fontSize: 10.5, fontFamily: 'var(--cti-mono)', color: '#9ca0b0' }}>
        {state === 'done' && `✓ ${n.ms}ms`}
        {state === 'running' && 'running…'}
        {state === 'queued' && 'queued'}
      </div>
      <style>{'@keyframes v2spin{to{transform:rotate(360deg)}}'}</style>
    </div>
  );
}

// ---------- right: pinboard ----------

function PinboardColumn({ accent, onOpenCard, withGraph }) {
  const [view, setView] = React.useState('pinned');
  const Raw  = window.RawPanel;
  const open = (k) => onOpenCard && onOpenCard(k);
  return (
    <aside style={{
      width: 420, flex: '0 0 420px', display: 'flex', flexDirection: 'column',
      background: '#f6f7fb', minWidth: 0, overflow: 'hidden',
      borderLeft: '1px solid #e8eaf0',
    }}>
      <div style={{
        padding: '10px 12px', borderBottom: '1px solid #e8eaf0', background: '#fbfbfd',
        display: 'flex', alignItems: 'center', gap: 6,
      }}>
        <div style={{
          flex: 1, display: 'flex', background: '#eef0f6', borderRadius: 7, padding: 2, gap: 2,
        }}>
          {[
            ['pinned', 'Pinned'],
            ['raw',    'Raw JSON'],
          ].map(([k, l]) => (
            <button key={k} onClick={() => setView(k)} style={{
              flex: 1, height: 24, border: 0, borderRadius: 5, cursor: 'pointer',
              background: view === k ? '#fff' : 'transparent',
              color: view === k ? '#0d1124' : '#6b6f7f',
              fontWeight: view === k ? 600 : 500, fontSize: 11.5,
              fontFamily: 'inherit',
              boxShadow: view === k ? '0 1px 2px rgba(20,20,40,0.08)' : 'none',
            }}>{l}</button>
          ))}
        </div>
        <button style={v2IconBtn()} title="Open in new tab"><Icon name="ext" size={13}/></button>
      </div>

      {view === 'pinned' && (
        <div style={{ flex: 1, overflowY: 'auto', overflowX: 'hidden', padding: '14px', display: 'flex', flexDirection: 'column', gap: 12 }}>
          <AttributionResultCard accent={accent} onOpen={() => open('attribution')}/>
          <CandidatesCard onOpen={() => open('candidates')} withGraph={withGraph}/>
          <InfrastructureCard accent={accent} onOpen={() => open('infrastructure')}/>
          <EvidenceChainCard onOpen={() => open('evidence')}/>
        </div>
      )}
      {view === 'raw' && (
        <div style={{ flex: 1, overflowY: 'auto', overflowX: 'hidden', padding: '14px' }}>
          {Raw && <Raw/>}
        </div>
      )}
    </aside>
  );
}

function AttributionResultCard({ accent, onOpen }) {
  const t = ATTR_TOKENS[INTEL.attribution_result];
  return (
    <PinCard tag="ATTRIBUTION RESULT" accent={t.dot} icon="target" title={`${t.label}  ·  ${INTEL.confidence.toFixed(2)}`} onOpen={onOpen}>
      {/* Confidence bars */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <ConfidenceBar label="Attribution"        value={INTEL.confidence}          color={t.dot}/>
        <ConfidenceBar label="Temporal (180d HL)" value={INTEL.temporal_confidence} color="#6b6f7f"/>
      </div>
      <div style={{ marginTop: 12, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <Flag kind={INTEL.is_shared_infrastructure ? 'warn' : 'ok'} label="Shared infra" sub={INTEL.is_shared_infrastructure ? 'CDN/cloud detected' : 'Dedicated'}/>
        <Flag kind={INTEL.needs_more_evidence    ? 'warn' : 'ok'} label="Evidence sufficiency" sub={INTEL.needs_more_evidence ? 'iterate' : 'sufficient'}/>
      </div>
    </PinCard>
  );
}

function ConfidenceBar({ label, value, color }) {
  const pct = Math.round(value * 100);
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: '#3a3f55', marginBottom: 3 }}>
        <span>{label}</span>
        <span style={{ fontFamily: 'var(--cti-mono)', fontWeight: 600 }}>{value.toFixed(2)}</span>
      </div>
      <div style={{ height: 6, background: '#eef0f6', borderRadius: 99, overflow: 'hidden' }}>
        <div style={{ height: '100%', width: `${pct}%`, background: color }}/>
      </div>
    </div>
  );
}

function Flag({ kind, label, sub }) {
  const c = kind === 'ok' ? '#10b981' : kind === 'warn' ? '#f59e0b' : '#dc2626';
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 8,
      padding: '5px 9px', borderRadius: 7, background: '#f3f4f9',
    }}>
      <span style={{ width: 6, height: 6, borderRadius: 99, background: c }}/>
      <div style={{ fontSize: 11 }}>
        <div style={{ color: '#0d1124', fontWeight: 500 }}>{label}</div>
        <div style={{ color: '#6b6f7f' }}>{sub}</div>
      </div>
    </div>
  );
}

function CandidatesCard({ onOpen, withGraph }) {
  return (
    <PinCard tag="CANDIDATE ACTORS" accent="#7c3aed" icon="target" title={`${INTEL.candidate_actors.length} ranked`} onOpen={onOpen}>
      {withGraph && (
        <div style={{
          background: '#fbfbfd', border: '1px solid #eef0f6', borderRadius: 8,
          padding: '6px 8px 2px', marginBottom: 10,
        }}>
          {window.MiniNodeGraph && <window.MiniNodeGraph accent="#7c3aed"/>}
          <div style={{ fontSize: 9.5, color: '#9ca0b0', fontFamily: 'var(--cti-mono)', textAlign: 'center', marginTop: -2, paddingBottom: 4 }}>
            T2_domain_to_actor · T3_infrastructure_pivot
          </div>
        </div>
      )}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {INTEL.candidate_actors.map(a => (
          <CandidateRowV2 key={a.actor_name} a={a}/>
        ))}
      </div>
    </PinCard>
  );
}

function CandidateRowV2({ a }) {
  const [open, setOpen] = React.useState(false);
  const pct = Math.round(a.confidence * 100);
  return (
    <div style={{
      border: '1px solid #e8eaf0', borderRadius: 8, padding: '8px 10px',
      background: '#fff',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }} onClick={() => setOpen(o => !o)}>
        <Icon name={open ? 'down' : 'chevron'} size={11} color="#9ca0b0"/>
        <span style={{ fontSize: 13, fontWeight: 600, color: '#0d1124' }}>{a.actor_name}</span>
        <SourceBadge kind={a.source}/>
        <span style={{ marginLeft: 'auto', fontSize: 11.5, fontFamily: 'var(--cti-mono)', color: '#0d1124', fontWeight: 600 }}>{a.confidence.toFixed(2)}</span>
      </div>
      <div style={{ height: 3, background: '#eef0f6', borderRadius: 99, marginTop: 6, overflow: 'hidden' }}>
        <div style={{ height: '100%', width: `${pct}%`, background: '#0d1124' }}/>
      </div>
      {open && (
        <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 4 }}>
          {a.supporting_evidence.map((e, i) => (
            <div key={i} style={{ fontSize: 11, color: '#3a3f55', display: 'flex', gap: 6, paddingLeft: 6, borderLeft: '2px solid #e8eaf0' }}>
              <span>•</span><span style={{ fontFamily: 'var(--cti-mono)' }}>{e}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function InfrastructureCard({ accent, onOpen }) {
  const e = INTEL.enrichment;
  return (
    <PinCard tag="INFRASTRUCTURE" accent={accent} icon="graph" title={`${e.passive_dns.length} resolutions · ${e.certificates.length} certs`} onOpen={onOpen}>
      {/* RDAP */}
      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10,
        padding: '6px 0 10px', borderBottom: '1px dashed #e8eaf0',
      }}>
        <Kv k="Registered" v={e.rdap.creation_date}/>
        <Kv k="Registrar"  v={e.rdap.registrar}/>
        <Kv k="Expires"    v={e.rdap.expiration_date}/>
      </div>

      {/* Passive DNS rows */}
      <div style={{ marginTop: 8 }}>
        <div style={{ fontSize: 9.5, color: '#9ca0b0', fontWeight: 700, letterSpacing: 0.6, marginBottom: 4 }}>PASSIVE DNS</div>
        {e.passive_dns.map(p => {
          const g = e.geoip.find(x => x.ip === p.ip);
          return (
            <div key={p.ip} style={{
              display: 'grid', gridTemplateColumns: '1fr 70px 110px',
              alignItems: 'center', fontSize: 11.5, padding: '5px 0',
              borderTop: '1px dashed #e8eaf0',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ fontFamily: 'var(--cti-mono)', color: '#0d1124' }}>{p.ip}</span>
                {e.current_ips.includes(p.ip) && <span style={{ fontSize: 9, fontWeight: 700, color: '#0a5d2b', background: '#dcf5e6', padding: '1px 4px', borderRadius: 3 }}>LIVE</span>}
              </div>
              <span style={{ color: '#6b6f7f', fontSize: 11 }}>{g ? `${g.country}·AS${g.asn_number}` : '—'}</span>
              <span style={{ color: '#9ca0b0', fontSize: 10.5, fontFamily: 'var(--cti-mono)', textAlign: 'right' }}>
                {p.first_seen.slice(5)} → {p.last_seen.slice(5)}
              </span>
            </div>
          );
        })}
      </div>

      {/* Certs */}
      <div style={{ marginTop: 10 }}>
        <div style={{ fontSize: 9.5, color: '#9ca0b0', fontWeight: 700, letterSpacing: 0.6, marginBottom: 4 }}>CERTIFICATES</div>
        {e.certificates.map(c => (
          <div key={c.fingerprint} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 0', fontSize: 11.5, borderTop: '1px dashed #e8eaf0' }}>
            <Icon name="lock" size={11} color="#6b6f7f"/>
            <span style={{ fontFamily: 'var(--cti-mono)', color: '#0d1124', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis' }}>{c.fingerprint}</span>
            <span style={{ color: '#6b6f7f', fontSize: 10.5 }}>{c.issuer}</span>
          </div>
        ))}
      </div>

      {/* JARM + favicon */}
      <div style={{ marginTop: 10, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
        <Fingerprint label="JARM"    value={e.jarm_hash}/>
        <Fingerprint label="favicon" value={e.favicon_hash}/>
      </div>
    </PinCard>
  );
}

function Kv({ k, v }) {
  return (
    <div>
      <div style={{ fontSize: 9.5, color: '#9ca0b0', fontWeight: 700, letterSpacing: 0.6 }}>{k.toUpperCase()}</div>
      <div style={{ fontSize: 12, color: '#0d1124', fontFamily: 'var(--cti-mono)', marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{v}</div>
    </div>
  );
}

function Fingerprint({ label, value }) {
  return (
    <div style={{
      display: 'inline-flex', alignItems: 'center', gap: 6,
      padding: '4px 8px', borderRadius: 6, background: '#f3f4f9',
      fontSize: 10.5, fontFamily: 'var(--cti-mono)',
    }}>
      <Icon name="fingerprint" size={11} color="#6b6f7f"/>
      <span style={{ color: '#6b6f7f', fontWeight: 600 }}>{label}</span>
      <span style={{ color: '#0d1124', maxWidth: 130, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{value}</span>
    </div>
  );
}

function EvidenceChainCard({ onOpen }) {
  return (
    <PinCard tag="EVIDENCE CHAIN" accent="#10b981" icon="cpu" title="Reasoning trail · transparent" onOpen={onOpen}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4, paddingLeft: 6, borderLeft: '2px solid #e8eaf0' }}>
        {INTEL.evidence_chain.map((e, i) => (
          <div key={i} style={{ display: 'flex', gap: 8, fontSize: 11.5, color: '#3a3f55', alignItems: 'flex-start' }}>
            <span style={{ fontFamily: 'var(--cti-mono)', fontSize: 10, color: '#9ca0b0', flex: '0 0 14px', marginTop: 1 }}>{i + 1}</span>
            <span style={{ flex: 1 }}>{e}</span>
          </div>
        ))}
      </div>
      <div style={{ marginTop: 10, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
        <span style={{ fontSize: 10.5, padding: '3px 7px', borderRadius: 4, background: '#eef0f6', color: '#3a3f55' }}>
          {INTEL.graph_paths.length} Cypher templates
        </span>
        <span style={{ fontSize: 10.5, padding: '3px 7px', borderRadius: 4, background: '#eef0f6', color: '#3a3f55' }}>
          {INTEL.rag_chunks.length} RAG chunks
        </span>
      </div>
    </PinCard>
  );
}

function PinCard({ tag, accent, icon, title, children, onOpen }) {
  return (
    <div style={{
      background: '#fff', borderRadius: 11, border: '1px solid #e8eaf0',
      boxShadow: '0 1px 0 rgba(20,20,40,0.04)',
    }}>
      <div style={{ padding: '11px 14px 8px', display: 'flex', alignItems: 'center', gap: 8 }}>
        <div style={{
          width: 22, height: 22, borderRadius: 6,
          background: `${accent}14`, display: 'grid', placeItems: 'center',
        }}>
          <Icon name={icon} size={12} color={accent}/>
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 9.5, fontWeight: 700, letterSpacing: 0.8, color: accent, textTransform: 'uppercase' }}>{tag}</div>
          <div style={{ fontSize: 13.5, fontWeight: 600, color: '#0d1124', marginTop: -1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{title}</div>
        </div>
        <button onClick={onOpen} style={v2IconBtn()} title="Open fullscreen"><Icon name="ext" size={12}/></button>
      </div>
      <div style={{ padding: '4px 14px 14px' }}>{children}</div>
    </div>
  );
}

// ---------- styles ----------

const v2GhostBtn = () => ({
  height: 28, padding: '0 10px', borderRadius: 7, border: '1px solid #e2e4ed',
  background: '#fff', color: '#0d1124', fontSize: 12, cursor: 'pointer',
  display: 'flex', alignItems: 'center', gap: 5, fontFamily: 'inherit', fontWeight: 500,
});
const v2IconBtn = () => ({
  width: 26, height: 26, border: 0, background: 'transparent', borderRadius: 6,
  display: 'grid', placeItems: 'center', cursor: 'pointer', color: '#6b6f7f',
});
const v2Pill = () => ({
  display: 'inline-flex', alignItems: 'center', gap: 4, height: 22,
  padding: '0 8px', borderRadius: 6, background: '#f3f4f9', color: '#6b6f7f',
  fontSize: 11, cursor: 'pointer',
});

Object.assign(window, { V2Workspace, PinboardColumn, PinCard });
