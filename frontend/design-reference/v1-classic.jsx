// V1 — Conservative. Linear/Vercel-feel two-pane.
// Aligned with backend AttributionState: 6-node LangGraph queue, confidence
// (not risk score), candidate actors with source badges, evidence chain.
// `right` prop swaps the artifact panel between tabbed view ('tabs') and
// the V2 pinboard ('pinboard'); the latter is V1.b.

function V1Classic({ right = 'tabs', withGraph = false }) {
  const [tab, setTab] = React.useState('report');
  const [fs, setFs]   = React.useState(null);                  // fullscreen card key
  const [demo, setDemo] = React.useState('done');               // demo state: done | running | error
  const accent = '#3b5bdb';
  const Pinboard = window.PinboardColumn;

  return (
    <div className="v1-root" style={{
      width: '100%', height: '100%', display: 'flex',
      background: '#fafaf8', color: '#0d0f12',
      fontFamily: 'var(--cti-sans)', fontSize: 14, lineHeight: 1.5,
      overflow: 'hidden', position: 'relative',
    }}>
      {/* Rail */}
      <aside style={{
        width: 56, flex: '0 0 56px', borderRight: '1px solid #ececea',
        background: '#fcfcfa', display: 'flex', flexDirection: 'column',
        alignItems: 'center', padding: '14px 0', gap: 4,
      }}>
        <div style={{
          width: 30, height: 30, borderRadius: 8, background: '#0d0f12',
          color: '#fff', display: 'grid', placeItems: 'center', fontWeight: 700,
          fontSize: 14, letterSpacing: -0.5, marginBottom: 14,
        }}>C</div>
        {['plus','history','graph','pin'].map((n, i) => (
          <button key={n} style={railBtn(i === 0)}>
            <Icon name={n} size={18}/>
          </button>
        ))}
        <div style={{ marginTop: 'auto' }}>
          <div style={{
            width: 28, height: 28, borderRadius: 99, background: '#dfe1e6',
            display: 'grid', placeItems: 'center', fontSize: 11, fontWeight: 600,
            color: '#3a3d44',
          }}>SY</div>
        </div>
      </aside>

      {/* Main column */}
      <main style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        {/* Top bar */}
        <header style={{
          height: 48, borderBottom: '1px solid #ececea', display: 'flex',
          alignItems: 'center', padding: '0 18px', gap: 14, background: '#fff',
        }}>
          <div style={{ fontSize: 12.5, color: '#6b6f78', display: 'flex', alignItems: 'center', gap: 6 }}>
            <span>Queries</span>
            <Icon name="chevron" size={12}/>
            <span style={{ color: '#0d0f12', fontWeight: 500, fontFamily: 'var(--cti-mono)' }}>hamadryas.online</span>
            <span style={{ marginLeft: 8, fontSize: 11, color: '#9ea1a9', padding: '2px 7px', borderRadius: 4, background: '#f1f1ec' }}>structural query</span>
          </div>
          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 6 }}>
            <button style={ghostBtn()}><Icon name="copy" size={13}/> Markdown</button>
            <button style={ghostBtn()}><Icon name="doc" size={13}/> JSON</button>
            <button style={ghostBtn()}><Icon name="ext" size={13}/> PDF</button>
            <button style={primaryBtn(accent)}>
              <Icon name="pin" size={13}/> Save
            </button>
          </div>
        </header>

        {/* Split workspace */}
        <div style={{ flex: 1, display: 'flex', minHeight: 0 }}>
          {/* CHAT */}
          <section style={{
            flex: '1 1 56%', display: 'flex', flexDirection: 'column',
            borderRight: '1px solid #ececea', minWidth: 0, background: '#fafaf8',
          }}>
            <div style={{ flex: 1, overflowY: 'auto', overflowX: 'hidden', padding: '20px 36px 12px', display: 'flex', flexDirection: 'column', gap: 18 }}>
              <DemoStatePicker value={demo} onChange={setDemo}/>
              <PreviousTurn/>
              <UserMsg text={INTEL.query}/>
              <AgentIntro accent={accent}/>
              <NodeQueue accent={accent} demo={demo}/>
              <AttributionResultMsg accent={accent} demo={demo}/>
            </div>

            {/* Composer */}
            <div style={{ padding: '0 36px 24px' }}>
              <div style={{
                background: '#fff', borderRadius: 14, border: '1px solid #e4e4e0',
                boxShadow: '0 1px 2px rgba(20,20,30,0.04)', padding: '12px 14px 10px',
              }}>
                <div style={{ minHeight: 40, color: '#a4a8b0', fontSize: 14 }}>
                  追问 / 提供更多 IOC… e.g. "用 SAN 模式查相邻域名"
                </div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div style={{ display: 'flex', gap: 4, color: '#6b6f78' }}>
                    <button style={iconBtn()}><Icon name="attach" size={15}/></button>
                    <span style={{
                      fontSize: 11.5, color: '#7c7f86', alignSelf: 'center',
                      padding: '3px 8px', borderRadius: 6, background: '#f1f1ec',
                      marginLeft: 4,
                    }}>DeepSeek · LangGraph</span>
                  </div>
                  <button style={{
                    width: 30, height: 30, borderRadius: 8, background: '#0d0f12',
                    color: '#fff', border: 0, display: 'grid', placeItems: 'center',
                    cursor: 'pointer',
                  }}><Icon name="arrowR" size={15}/></button>
                </div>
              </div>
              <div style={{ fontSize: 11, color: '#9ea1a9', marginTop: 6, textAlign: 'center' }}>
                归因结果基于 graph + RAG 证据 · 仅供参考
              </div>
            </div>
          </section>

          {/* ARTIFACT */}
          {right === 'pinboard' ? (
            <Pinboard accent={accent} onOpenCard={setFs} withGraph={withGraph}/>
          ) : (
            <aside style={{ flex: '1 1 44%', display: 'flex', flexDirection: 'column', minWidth: 0, background: '#fff' }}>
              <div style={{
                height: 40, borderBottom: '1px solid #ececea',
                display: 'flex', alignItems: 'center', padding: '0 14px', gap: 2,
              }}>
                {[
                  ['report','Report'], ['evidence','Evidence'],
                  ['iocs','Indicators'], ['raw','Raw JSON'],
                ].map(([k, l]) => (
                  <button key={k} onClick={() => setTab(k)} style={tabBtn(tab === k, accent)}>{l}</button>
                ))}
                <div style={{ marginLeft: 'auto', display: 'flex', gap: 6, color: '#6b6f78' }}>
                  <button style={iconBtn()}><Icon name="copy" size={14}/></button>
                  <button style={iconBtn()}><Icon name="ext" size={14}/></button>
                </div>
              </div>
              <div style={{ flex: 1, overflow: 'hidden', padding: '24px 26px' }}>
                {tab === 'report'   && <ReportPanel accent={accent}/>}
                {tab === 'evidence' && <EvidencePanel/>}
                {tab === 'iocs'     && <IndicatorsPanel/>}
                {tab === 'raw'      && <RawPanel/>}
              </div>
            </aside>
          )}
        </div>
      </main>

      {fs && window.FullscreenCard && (
        <window.FullscreenCard cardKey={fs} accent={accent} onClose={() => setFs(null)}/>
      )}
    </div>
  );
}

// ---------- chat messages ----------

// Demo-state variants for the node queue (lets the user preview
// running/error chrome without backend changes).
const NODE_STATES = {
  done: NODES_RUN.map(n => ({ ...n, status: 'done', ms: n.ms || 380 })),
  running: NODES_RUN.map((n, i) =>
    i < 3   ? { ...n, status: 'done',    ms: n.ms || 380 } :
    i === 3 ? { ...n, status: 'running', ms: 0,            sub: 'validating 3 candidates against graph…' } :
              { ...n, status: 'queued',  ms: 0 }
  ),
  error: NODES_RUN.map((n, i) =>
    i < 2   ? { ...n, status: 'done',  ms: n.ms || 380 } :
    i === 2 ? { ...n, status: 'error', ms: 0,           sub: 'RAG retrieval failed: vector store unreachable' } :
              { ...n, status: 'queued', ms: 0 }
  ),
};

function DemoStatePicker({ value, onChange }) {
  return (
    <div style={{
      alignSelf: 'flex-start', display: 'inline-flex', alignItems: 'center', gap: 8,
      padding: '4px 4px 4px 10px', borderRadius: 8, background: '#fff',
      border: '1px dashed #d8d8d2', fontSize: 11, color: '#9ea1a9',
    }}>
      <span style={{ letterSpacing: 0.4, textTransform: 'uppercase', fontWeight: 600 }}>Demo state</span>
      <div style={{ display: 'flex', gap: 2, background: '#f1f1ec', borderRadius: 6, padding: 2 }}>
        {[['done','Done'],['running','Running'],['error','Error']].map(([k, l]) => (
          <button key={k} onClick={() => onChange(k)} style={{
            border: 0, padding: '3px 9px', borderRadius: 4, cursor: 'pointer',
            background: value === k ? '#fff' : 'transparent',
            color: value === k ? '#0d0f12' : '#6b6f78',
            fontWeight: value === k ? 600 : 500, fontSize: 11,
            fontFamily: 'inherit',
            boxShadow: value === k ? '0 1px 2px rgba(0,0,0,0.06)' : 'none',
          }}>{l}</button>
        ))}
      </div>
    </div>
  );
}

function PreviousTurn() {
  return (
    <button style={{
      alignSelf: 'stretch', display: 'flex', alignItems: 'center', gap: 10,
      padding: '8px 12px', borderRadius: 8, border: '1px solid #ececea',
      background: '#fff', cursor: 'pointer', fontFamily: 'inherit', color: '#0d0f12',
      textAlign: 'left',
    }}>
      <Icon name="time" size={12} color="#9ea1a9"/>
      <span style={{ fontSize: 11, color: '#9ea1a9', fontFamily: 'var(--cti-mono)', flex: '0 0 auto' }}>3h ago</span>
      <span style={{ fontSize: 12.5, color: '#3a3d44', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontFamily: 'var(--cti-mono)' }}>
        auth-microsft365.com　— 谁在用？
      </span>
      <ConfidenceBadge kind="medium_confidence"/>
      <span style={{ fontSize: 11, color: '#6b6f78', fontFamily: 'var(--cti-mono)' }}>TA-577 · 0.62</span>
      <Icon name="chevron" size={12} color="#9ea1a9"/>
    </button>
  );
}

function UserMsg({ text }) {
  return (
    <div style={{ alignSelf: 'flex-end', display: 'flex', gap: 10, alignItems: 'flex-start', maxWidth: '85%' }}>
      <div style={{
        background: '#0d0f12', color: '#fff', padding: '9px 14px', borderRadius: 16,
        borderBottomRightRadius: 6, fontSize: 14, maxWidth: 460,
      }}>{text}</div>
      <div style={{
        width: 26, height: 26, borderRadius: 99, background: '#dfe1e6',
        display: 'grid', placeItems: 'center', fontSize: 10, fontWeight: 600,
        color: '#3a3d44', marginTop: 2,
      }}>SY</div>
    </div>
  );
}

function AgentIntro({ accent }) {
  return (
    <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
      <AgentAvatar/>
      <div style={{ flex: 1, paddingTop: 2 }}>
        <div style={{ fontSize: 13, color: '#3a3d44' }}>
          路由为<b style={{color:'#0d0f12'}}>结构化查询</b>。已运行 6 个 node：infrastructure（5 个 Cypher 模板）→
          intelligence（RAG，12 chunks）→ graph_probe 验证 → evidence_eval 评估 → 合成报告。
        </div>
      </div>
    </div>
  );
}

function NodeQueue({ accent, demo = 'done' }) {
  const nodes = NODE_STATES[demo] || NODE_STATES.done;
  return (
    <div style={{ marginLeft: 38 }}>
      <div style={{
        background: '#fff', border: '1px solid #ececea', borderRadius: 12,
        padding: 4, display: 'flex', flexDirection: 'column', gap: 1,
      }}>
        {nodes.map((n, i) => (
          <NodeRow key={n.id} n={n} idx={i} accent={accent}/>
        ))}
      </div>
      <style>{'@keyframes v1spin{to{transform:rotate(360deg)}}'}</style>
    </div>
  );
}

function NodeRow({ n, idx, accent }) {
  const [open, setOpen] = React.useState(false);
  const canExpand = n.status !== 'queued';
  return (
    <div>
      <div
        onClick={() => canExpand && setOpen(o => !o)}
        style={{
          display: 'grid', gridTemplateColumns: '14px 18px 1fr auto',
          alignItems: 'center', gap: 10, padding: '8px 10px',
          borderRadius: 8,
          background: n.status === 'running' ? '#f7f6f1' : n.status === 'error' ? '#fdf1f1' : 'transparent',
          cursor: canExpand ? 'pointer' : 'default',
        }}>
        <Icon name={open ? 'down' : 'chevron'} size={11} color={canExpand ? '#9ea1a9' : 'transparent'}/>
        {n.status === 'done' ? (
          <div style={{ width: 16, height: 16, borderRadius: 99, background: '#e6f6ee', display: 'grid', placeItems: 'center' }}>
            <Icon name="check" size={11} color="#067a4a"/>
          </div>
        ) : n.status === 'running' ? (
          <div style={{ width: 14, height: 14, borderRadius: 99, border: '1.5px solid #e4e4e0', borderTopColor: accent, animation: 'v1spin .9s linear infinite' }}/>
        ) : n.status === 'error' ? (
          <div style={{ width: 16, height: 16, borderRadius: 99, background: '#fde6e6', display: 'grid', placeItems: 'center' }}>
            <Icon name="x" size={11} color="#a31a1a"/>
          </div>
        ) : (
          <div style={{ width: 14, height: 14, borderRadius: 99, border: '1.5px dashed #d8d8d2' }}/>
        )}
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, minWidth: 0 }}>
          <span style={{
            fontFamily: 'var(--cti-mono)', fontSize: 11, color: '#9ea1a9',
            width: 18, flex: '0 0 18px', textAlign: 'right',
          }}>{idx + 1}.</span>
          <span style={{ fontSize: 13, color: n.status === 'error' ? '#a31a1a' : '#0d0f12', fontWeight: 500, flex: '0 0 auto' }}>{n.label}</span>
          <span style={{
            fontSize: 11.5, color: n.status === 'error' ? '#a31a1a' : '#6b6f78',
            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', minWidth: 0,
          }}>· {n.sub}</span>
        </div>
        <span style={{ fontSize: 11, color: '#9ea1a9', fontFamily: 'var(--cti-mono)' }}>
          {n.status === 'done' ? `${n.ms}ms` : n.status === 'running' ? 'running…' : n.status === 'error' ? 'failed' : 'queued'}
        </span>
      </div>
      {open && <NodeDetails id={n.id}/>}
    </div>
  );
}

function NodeDetails({ id }) {
  // Per-node sub-results derived from INTEL
  const wrap = (children) => (
    <div style={{ padding: '4px 10px 10px 42px', display: 'flex', flexDirection: 'column', gap: 5 }}>{children}</div>
  );
  if (id === 'supervisor') {
    return wrap(
      <KV k="query_type" v="structural"/>,
    );
  }
  if (id === 'infrastructure') {
    return wrap(
      INTEL.graph_paths.map(g => (
        <div key={g.template} style={subRow}>
          <StatusDot status={g.status}/>
          <span style={{ fontFamily: 'var(--cti-mono)', fontSize: 11.5, color: '#0d0f12' }}>{g.template}</span>
          <span style={{ color: '#6b6f78', fontSize: 11, marginLeft: 'auto' }}>{g.summary}</span>
        </div>
      )),
    );
  }
  if (id === 'intelligence') {
    return wrap(
      INTEL.rag_chunks.map(c => (
        <div key={c.chunk_id} style={subRow}>
          <span style={{ fontFamily: 'var(--cti-mono)', fontSize: 10, padding: '1px 5px', borderRadius: 3, background: '#f1f1ec', color: '#3a3d44', fontWeight: 600 }}>{c.source}</span>
          <span style={{ fontSize: 11, color: '#9ea1a9', fontFamily: 'var(--cti-mono)' }}>{c.chunk_id}</span>
          <span style={{ fontSize: 11, color: '#3a3d44', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontStyle: 'italic' }}>"{c.snippet}"</span>
          <span style={{ fontSize: 10.5, color: '#6b6f78', fontFamily: 'var(--cti-mono)' }}>RRF {c.rrf_score.toFixed(2)}</span>
        </div>
      )),
    );
  }
  if (id === 'graph_probe') {
    return wrap(
      INTEL.candidate_actors.map(a => (
        <div key={a.actor_name} style={subRow}>
          <Icon name="check" size={11} color="#10b981"/>
          <span style={{ fontSize: 12, color: '#0d0f12', fontWeight: 500 }}>{a.actor_name}</span>
          <SourceBadge kind={a.source}/>
          <span style={{ marginLeft: 'auto', fontFamily: 'var(--cti-mono)', fontSize: 11, color: '#6b6f78' }}>{a.confidence.toFixed(2)}</span>
        </div>
      )),
    );
  }
  if (id === 'evidence_eval') {
    return wrap(
      <KV k="confidence" v={INTEL.confidence.toFixed(2)}/>,
      <KV k="temporal_confidence" v={INTEL.temporal_confidence.toFixed(2)}/>,
      <KV k="is_shared_infrastructure" v={String(INTEL.is_shared_infrastructure)}/>,
      <KV k="needs_more_evidence" v={String(INTEL.needs_more_evidence)}/>,
      <KV k="attribution_result" v={INTEL.attribution_result}/>,
    );
  }
  if (id === 'report') {
    return wrap(
      <div style={{ fontSize: 11.5, color: '#3a3d44', lineHeight: 1.55 }}>
        Rendering markdown、JSON、可复制 IOC 列表。3 sources · narrative {INTEL.narrative.length} chars.
      </div>,
    );
  }
  return wrap(<div style={{ color: '#9ea1a9', fontSize: 11 }}>No details.</div>);
}

const subRow = {
  display: 'flex', alignItems: 'center', gap: 8,
  padding: '3px 0', fontSize: 11.5, color: '#0d0f12',
};

function KV({ k, v }) {
  return (
    <div style={subRow}>
      <span style={{ fontFamily: 'var(--cti-mono)', color: '#6b6f78' }}>{k}</span>
      <span style={{ marginLeft: 'auto', fontFamily: 'var(--cti-mono)', color: '#0d0f12', fontWeight: 500 }}>{v}</span>
    </div>
  );
}

function AttributionResultMsg({ accent, demo = 'done' }) {
  if (demo === 'running') return <AttributionLoadingMsg accent={accent}/>;
  if (demo === 'error')   return <AttributionErrorMsg/>;
  const top = INTEL.candidate_actors[0];
  return (
    <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
      <AgentAvatar/>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{
          background: '#fff', border: '1px solid #ececea', borderRadius: 14,
          padding: 18, display: 'flex', flexDirection: 'column', gap: 14,
        }}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, flexWrap: 'wrap' }}>
            <div style={{
              fontFamily: 'var(--cti-mono)', fontSize: 18, fontWeight: 600,
              color: '#0d0f12', letterSpacing: -0.3,
            }}>{INTEL.domain}</div>
            <ConfidenceBadge kind={INTEL.attribution_result} size="lg"/>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14 }}>
            {[
              ['Top actor',     top.actor_name],
              ['Confidence',    INTEL.confidence.toFixed(2)],
              ['Temporal',      INTEL.temporal_confidence.toFixed(2)],
              ['Shared infra',  INTEL.is_shared_infrastructure ? 'Yes' : 'No'],
            ].map(([k, v]) => (
              <div key={k}>
                <div style={{ fontSize: 10.5, color: '#9ea1a9', textTransform: 'uppercase', letterSpacing: 0.4 }}>{k}</div>
                <div style={{ fontSize: 13.5, fontFamily: 'var(--cti-mono)', color: '#0d0f12', marginTop: 2, fontWeight: 600 }}>{v}</div>
              </div>
            ))}
          </div>

          <div style={{ borderTop: '1px solid #ececea', paddingTop: 12, fontSize: 13, color: '#3a3d44', lineHeight: 1.55 }}>
            {INTEL.narrative}
          </div>

          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            <button style={chipBtn(true, accent)}>查看证据链</button>
            <button style={chipBtn()}>展开候选演员</button>
            <button style={chipBtn()}>复制 Markdown</button>
            <button style={chipBtn()}>导出 JSON</button>
          </div>
        </div>
      </div>
    </div>
  );
}

function AttributionLoadingMsg({ accent }) {
  return (
    <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
      <AgentAvatar/>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{
          background: '#fff', border: '1px solid #ececea', borderRadius: 14,
          padding: 18, display: 'flex', flexDirection: 'column', gap: 14,
          position: 'relative', overflow: 'hidden',
        }}>
          {/* Subtle moving shimmer line */}
          <div style={{
            position: 'absolute', left: 0, top: 0, height: 2, width: '40%',
            background: `linear-gradient(90deg, transparent, ${accent}, transparent)`,
            animation: 'v1shim 1.6s linear infinite',
          }}/>
          <style>{'@keyframes v1shim{from{transform:translateX(-100%)}to{transform:translateX(350%)}}'}</style>

          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ width: 14, height: 14, borderRadius: 99, border: '2px solid #e4e4e0', borderTopColor: accent, animation: 'v1spin .9s linear infinite' }}/>
            <div style={{
              fontFamily: 'var(--cti-mono)', fontSize: 18, fontWeight: 600,
              color: '#0d0f12', letterSpacing: -0.3,
            }}>{INTEL.domain}</div>
            <span style={{
              fontSize: 11.5, fontWeight: 600, color: accent,
              padding: '2px 8px', borderRadius: 99, background: `${accent}14`,
              letterSpacing: 0.2,
            }}>Analyzing…</span>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14 }}>
            {['Top actor','Confidence','Temporal','Shared infra'].map(k => (
              <div key={k}>
                <div style={{ fontSize: 10.5, color: '#9ea1a9', textTransform: 'uppercase', letterSpacing: 0.4 }}>{k}</div>
                <div style={{ height: 14, width: '70%', background: '#f1f1ec', borderRadius: 4, marginTop: 4 }}/>
              </div>
            ))}
          </div>

          <div style={{ borderTop: '1px solid #ececea', paddingTop: 12, display: 'flex', flexDirection: 'column', gap: 6 }}>
            <div style={{ height: 10, width: '95%', background: '#f1f1ec', borderRadius: 3 }}/>
            <div style={{ height: 10, width: '88%', background: '#f1f1ec', borderRadius: 3 }}/>
            <div style={{ height: 10, width: '60%', background: '#f1f1ec', borderRadius: 3 }}/>
          </div>

          <div style={{ fontSize: 11.5, color: '#6b6f78' }}>
            已完成 <b style={{ color: '#0d0f12' }}>3</b> / 6 个 node · 预计 2–3s 后完成
          </div>
        </div>
      </div>
    </div>
  );
}

function AttributionErrorMsg() {
  return (
    <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
      <AgentAvatar/>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{
          background: '#fff', border: '1px solid #f3c2c2', borderRadius: 14,
          padding: 18, display: 'flex', flexDirection: 'column', gap: 10,
          borderLeft: '3px solid #a31a1a',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Icon name="flame" size={14} color="#a31a1a"/>
            <span style={{ fontSize: 13, fontWeight: 600, color: '#a31a1a' }}>Pipeline halted</span>
          </div>
          <div style={{ fontSize: 13, color: '#3a3d44', lineHeight: 1.55 }}>
            <code style={{ fontFamily: 'var(--cti-mono)', background: '#fde6e6', padding: '1px 6px', borderRadius: 4, color: '#a31a1a' }}>intelligence</code>
            {' '}node 失败：RAG retrieval timeout (vector store unreachable after 30s)。前 2 个 node 的结果仍可看，但未能完成归因。
          </div>
          <div style={{ display: 'flex', gap: 6, marginTop: 4 }}>
            <button style={chipBtn(true, '#a31a1a')}>重试 pipeline</button>
            <button style={chipBtn()}>仅跑 graph (跳过 RAG)</button>
            <button style={chipBtn()}>查看错误日志</button>
          </div>
        </div>
      </div>
    </div>
  );
}

function AgentAvatar() {
  return (
    <div style={{
      width: 26, height: 26, borderRadius: 8, background: '#0d0f12',
      display: 'grid', placeItems: 'center', color: '#fff', flex: '0 0 26px',
    }}>
      <Icon name="spark" size={14} color="#fff"/>
    </div>
  );
}

// ---------- artifact tabs ----------

function ReportPanel({ accent }) {
  const top = INTEL.candidate_actors[0];
  return (
    <div style={{ height: '100%', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
      <div style={{
        borderLeft: `3px solid ${ATTR_TOKENS[INTEL.attribution_result].dot}`, paddingLeft: 12, marginBottom: 18,
      }}>
        <div style={{ fontSize: 10.5, color: '#9ea1a9', textTransform: 'uppercase', letterSpacing: 0.5 }}>Attribution report · auto-generated</div>
        <h2 style={{ margin: '4px 0 0', fontSize: 19, fontWeight: 600, letterSpacing: -0.3, fontFamily: 'var(--cti-mono)' }}>
          {INTEL.domain} → {top.actor_name}
        </h2>
        <div style={{ fontSize: 12, color: '#6b6f78', marginTop: 4 }}>
          {ATTR_TOKENS[INTEL.attribution_result].label} · confidence {INTEL.confidence} · temporal {INTEL.temporal_confidence}
        </div>
      </div>

      <Section label="Narrative">
        <div style={{ fontSize: 13.5, color: '#3a3d44', lineHeight: 1.6 }}>
          {INTEL.narrative}
        </div>
      </Section>

      <Section label="Candidate actors">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {INTEL.candidate_actors.map(a => (
            <CandidateRow key={a.actor_name} a={a}/>
          ))}
        </div>
      </Section>

      <Section label="Sources">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          {INTEL.sources.map((s, i) => (
            <div key={i} style={{ display: 'flex', gap: 8, fontSize: 12.5, alignItems: 'center' }}>
              <SourceBadge kind={s.type}/>
              <span style={{ color: '#3a3d44', fontFamily: 'var(--cti-mono)', fontSize: 11.5 }}>{s.detail}</span>
            </div>
          ))}
        </div>
      </Section>
    </div>
  );
}

function CandidateRow({ a }) {
  const pct = Math.round(a.confidence * 100);
  return (
    <div style={{
      border: '1px solid #ececea', borderRadius: 8, padding: '10px 12px',
      display: 'flex', flexDirection: 'column', gap: 6,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ fontSize: 13.5, fontWeight: 600, color: '#0d0f12' }}>{a.actor_name}</span>
        <SourceBadge kind={a.source}/>
        <span style={{ marginLeft: 'auto', fontSize: 12, fontFamily: 'var(--cti-mono)', color: '#0d0f12', fontWeight: 600 }}>{a.confidence.toFixed(2)}</span>
      </div>
      <div style={{ height: 4, background: '#f1f1ec', borderRadius: 99, overflow: 'hidden' }}>
        <div style={{ height: '100%', width: `${pct}%`, background: '#0d0f12' }}/>
      </div>
    </div>
  );
}

function Section({ label, children }) {
  return (
    <div style={{ marginBottom: 18 }}>
      <div style={{
        fontSize: 10.5, color: '#9ea1a9', textTransform: 'uppercase',
        letterSpacing: 0.6, marginBottom: 8, fontWeight: 600,
      }}>{label}</div>
      {children}
    </div>
  );
}

function EvidencePanel() {
  return (
    <div style={{ height: '100%', overflow: 'hidden', display: 'flex', flexDirection: 'column', gap: 18 }}>
      <Section label="Evidence chain">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {INTEL.evidence_chain.map((e, i) => (
            <div key={i} style={{ display: 'flex', gap: 10, fontSize: 12.5, color: '#3a3d44', alignItems: 'flex-start' }}>
              <span style={{
                fontFamily: 'var(--cti-mono)', fontSize: 11, color: '#9ea1a9',
                background: '#f1f1ec', padding: '1px 6px', borderRadius: 4,
                flex: '0 0 auto', marginTop: 1,
              }}>{i + 1}</span>
              <span style={{ flex: 1 }}>{e}</span>
            </div>
          ))}
        </div>
      </Section>

      <Section label="Graph paths (Cypher)">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          {INTEL.graph_paths.map(g => (
            <div key={g.template} style={{
              display: 'flex', alignItems: 'center', gap: 10,
              padding: '6px 10px', border: '1px solid #ececea', borderRadius: 6,
              fontSize: 12,
            }}>
              <StatusDot status={g.status}/>
              <span style={{ fontFamily: 'var(--cti-mono)', fontSize: 11.5, color: '#0d0f12' }}>{g.template}</span>
              <span style={{ marginLeft: 'auto', color: '#6b6f78', fontSize: 11.5 }}>{g.summary}</span>
            </div>
          ))}
        </div>
      </Section>

      <Section label="RAG chunks">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {INTEL.rag_chunks.map(c => (
            <div key={c.chunk_id} style={{ border: '1px solid #ececea', borderRadius: 6, padding: '8px 10px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                <span style={{
                  fontFamily: 'var(--cti-mono)', fontSize: 10.5, padding: '1px 6px',
                  borderRadius: 3, background: '#f1f1ec', color: '#3a3d44',
                }}>{c.source}</span>
                <span style={{ fontSize: 10.5, color: '#9ea1a9', fontFamily: 'var(--cti-mono)' }}>{c.chunk_id}</span>
                <span style={{ marginLeft: 'auto', fontSize: 11, color: '#6b6f78', fontFamily: 'var(--cti-mono)' }}>RRF {c.rrf_score.toFixed(2)}</span>
              </div>
              <div style={{ fontSize: 12, color: '#3a3d44', fontStyle: 'italic' }}>"{c.snippet}"</div>
            </div>
          ))}
        </div>
      </Section>
    </div>
  );
}

function StatusDot({ status }) {
  const c = status === 'success' ? '#10b981' : status === 'empty' ? '#9ca0b0' : status === 'error' ? '#dc2626' : '#f59e0b';
  return <span style={{ width: 6, height: 6, borderRadius: 99, background: c, flex: '0 0 6px' }}/>;
}

function IndicatorsPanel() {
  const rows = [
    { type: 'DOMAIN', value: INTEL.domain, ctx: `${INTEL.enrichment.rdap.registrar} · ${INTEL.enrichment.rdap.creation_date}` },
    ...INTEL.enrichment.passive_dns.map(p => {
      const geo = INTEL.enrichment.geoip.find(g => g.ip === p.ip);
      return { type: 'IPv4', value: p.ip, ctx: geo ? `${geo.country} · AS${geo.asn_number} ${geo.asn_name}` : '', first: p.first_seen, last: p.last_seen };
    }),
    ...INTEL.enrichment.certificates.map(c => ({ type: 'CERT', value: c.fingerprint, ctx: `${c.issuer} · ${c.san_list.length} SAN` })),
    { type: 'JARM',    value: INTEL.enrichment.jarm_hash,    ctx: 'TLS fingerprint' },
    { type: 'FAVICON', value: INTEL.enrichment.favicon_hash, ctx: 'mmh3 hash' },
  ];
  return (
    <div style={{ height: '100%', overflow: 'hidden' }}>
      <table style={{ width: '100%', fontSize: 12.5, borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ textAlign: 'left', color: '#9ea1a9', fontSize: 10.5, textTransform: 'uppercase', letterSpacing: 0.5 }}>
            <th style={{ padding: '8px 8px 8px 0', fontWeight: 600 }}>Type</th>
            <th style={{ padding: 8, fontWeight: 600 }}>Value</th>
            <th style={{ padding: 8, fontWeight: 600 }}>Context</th>
            <th style={{ padding: 8, fontWeight: 600, textAlign: 'right' }}>Seen</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} style={{ borderTop: '1px solid #f1f1ec' }}>
              <td style={{ padding: '9px 8px 9px 0', color: '#6b6f78', fontFamily: 'var(--cti-mono)', fontSize: 11 }}>{r.type}</td>
              <td style={{ padding: 9, fontFamily: 'var(--cti-mono)', color: '#0d0f12', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 160 }}>{r.value}</td>
              <td style={{ padding: 9, color: '#6b6f78' }}>{r.ctx}</td>
              <td style={{ padding: 9, textAlign: 'right', color: '#9ea1a9', fontFamily: 'var(--cti-mono)', fontSize: 11 }}>
                {r.first ? `${r.first.slice(5)} → ${r.last.slice(5)}` : '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function RawPanel() {
  const json = {
    query: INTEL.query,
    domain: INTEL.domain,
    query_type: INTEL.query_type,
    attribution_result: INTEL.attribution_result,
    confidence: INTEL.confidence,
    temporal_confidence: INTEL.temporal_confidence,
    is_shared_infrastructure: INTEL.is_shared_infrastructure,
    needs_more_evidence: INTEL.needs_more_evidence,
    candidate_actors: INTEL.candidate_actors.map(a => ({
      actor_name: a.actor_name, confidence: a.confidence, source: a.source,
      supporting_evidence: a.supporting_evidence,
    })),
    sources: INTEL.sources,
  };
  const text = JSON.stringify(json, null, 2);
  const [copied, setCopied] = React.useState(false);
  const copy = () => {
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text);
      }
    } catch (e) {}
    setCopied(true);
    setTimeout(() => setCopied(false), 1400);
  };
  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        marginBottom: 8,
      }}>
        <div style={{ fontSize: 10.5, color: '#9ea1a9', fontWeight: 700, letterSpacing: 0.6, textTransform: 'uppercase' }}>
          AttributionState · {text.length} chars
        </div>
        <button onClick={copy} style={{
          height: 24, padding: '0 9px', borderRadius: 6, border: '1px solid #e4e4e0',
          background: copied ? '#e6f6ee' : '#fff', color: copied ? '#067a4a' : '#0d0f12',
          fontSize: 11, cursor: 'pointer', display: 'inline-flex',
          alignItems: 'center', gap: 5, fontFamily: 'inherit', fontWeight: 500,
        }}>
          <Icon name={copied ? 'check' : 'copy'} size={11}/>
          {copied ? 'Copied' : '复制全文'}
        </button>
      </div>
      <pre style={{
        margin: 0, padding: 14, background: '#fafaf8', borderRadius: 10,
        border: '1px solid #ececea', fontFamily: 'var(--cti-mono)', fontSize: 11,
        color: '#0d0f12', whiteSpace: 'pre-wrap', overflow: 'auto', flex: 1,
        lineHeight: 1.55,
      }}>{text}</pre>
    </div>
  );
}

// ---------- styles ----------

const railBtn = (active) => ({
  width: 38, height: 38, border: 0, borderRadius: 8, cursor: 'pointer',
  background: active ? '#ececea' : 'transparent',
  color: active ? '#0d0f12' : '#6b6f78',
  display: 'grid', placeItems: 'center',
});
const ghostBtn = () => ({
  height: 28, padding: '0 10px', borderRadius: 7, border: '1px solid #e4e4e0',
  background: '#fff', color: '#0d0f12', fontSize: 12, cursor: 'pointer',
  display: 'flex', alignItems: 'center', gap: 5, fontFamily: 'inherit',
});
const primaryBtn = (c) => ({
  height: 28, padding: '0 12px', borderRadius: 7, border: 0,
  background: '#0d0f12', color: '#fff', fontSize: 12, cursor: 'pointer',
  display: 'flex', alignItems: 'center', gap: 5, fontFamily: 'inherit', fontWeight: 500,
});
const tabBtn = (active, accent) => ({
  height: 30, padding: '0 12px', border: 0, background: 'transparent',
  color: active ? '#0d0f12' : '#6b6f78', fontSize: 12.5, cursor: 'pointer',
  fontWeight: active ? 600 : 500, fontFamily: 'inherit',
  borderBottom: active ? `2px solid ${accent}` : '2px solid transparent',
  marginBottom: -1,
});
const iconBtn = () => ({
  width: 28, height: 28, border: 0, background: 'transparent', borderRadius: 6,
  display: 'grid', placeItems: 'center', cursor: 'pointer', color: '#6b6f78',
});
const chipBtn = (primary, accent) => ({
  height: 28, padding: '0 12px', borderRadius: 7,
  border: primary ? 0 : '1px solid #e4e4e0',
  background: primary ? accent : '#fff',
  color: primary ? '#fff' : '#0d0f12',
  fontSize: 12, cursor: 'pointer', fontFamily: 'inherit', fontWeight: 500,
});

window.V1Classic = V1Classic;
Object.assign(window, { V1Classic, IndicatorsPanel, EvidencePanel, RawPanel });
