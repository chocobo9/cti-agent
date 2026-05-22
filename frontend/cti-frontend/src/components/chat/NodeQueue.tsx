import { useState } from 'react';
import { tokens } from '../../lib/tokens';
import { Icon } from '../shared/Icon';
import { SourceBadge } from '../shared/SourceBadge';
import { StatusPill } from '../shared/StatusPill';
import type { NodeStatus, AttributionState, CypherStatus } from '../../types/AttributionState';
import styles from './NodeQueue.module.css';

export interface NodeRun {
  id: string;
  label: string;
  status: NodeStatus;
  ms: number;
  sub: string;
}

export interface NodeQueueProps {
  nodes: NodeRun[];
  state: AttributionState;
}

export function NodeQueue({ nodes, state }: NodeQueueProps) {
  return (
    <div data-testid="node-queue" className={styles.container}>
      <div className={styles.card}>
        {nodes.map((n, i) => (
          <NodeRow key={n.id} node={n} idx={i} state={state} />
        ))}
      </div>
    </div>
  );
}

interface NodeRowProps {
  node: NodeRun;
  idx: number;
  state: AttributionState;
}

function rowBackground(status: NodeStatus): string {
  if (status === 'running') return '#f7f6f1';
  if (status === 'error') return '#fdf1f1';
  return 'transparent';
}

function NodeRow({ node, idx, state }: NodeRowProps) {
  const [open, setOpen] = useState(false);
  const canExpand = node.status !== 'queued';
  const isError = node.status === 'error';

  return (
    <div data-testid={`node-row-${node.id}`}>
      <div
        onClick={() => canExpand && setOpen((o) => !o)}
        className={styles.rowGrid}
        style={{
          background: rowBackground(node.status),
          cursor: canExpand ? 'pointer' : 'default',
        }}
      >
        <Icon
          name={open ? 'down' : 'chevron'}
          size={11}
          color={canExpand ? tokens.textGhost : 'transparent'}
        />
        <StatusIndicator status={node.status} />
        <div className={styles.labelGroup}>
          <span className={styles.rowIndex}>
            {idx + 1}.
          </span>
          <span
            className={styles.rowLabel}
            style={{ color: isError ? '#a31a1a' : tokens.text }}
          >
            {node.label}
          </span>
          <span
            className={styles.rowSub}
            style={{ color: isError ? '#a31a1a' : tokens.textSubtle }}
          >
            · {node.sub}
          </span>
        </div>
        <span className={styles.rowMs}>
          {node.status === 'done'
            ? `${node.ms}ms`
            : node.status === 'running'
              ? 'running…'
              : node.status === 'error'
                ? 'failed'
                : 'queued'}
        </span>
      </div>
      {open && (
        <div data-testid={`node-row-${node.id}-expanded`}>
          <NodeDetails id={node.id} state={state} />
        </div>
      )}
    </div>
  );
}

function StatusIndicator({ status }: { status: NodeStatus }) {
  if (status === 'done') {
    return (
      <div className={styles.statusDone}>
        <Icon name="check" size={11} color="#067a4a" />
      </div>
    );
  }
  if (status === 'running') {
    return <div className={styles.statusRunning} />;
  }
  if (status === 'error') {
    return (
      <div className={styles.statusError}>
        <Icon name="x" size={11} color="#a31a1a" />
      </div>
    );
  }
  return <div className={styles.statusQueued} />;
}

function KV({ k, v }: { k: string; v: string }) {
  return (
    <div className={styles.subRow}>
      <span className={styles.kvKey}>{k}</span>
      <span className={styles.kvValue}>{v}</span>
    </div>
  );
}

function NodeDetails({ id, state }: { id: string; state: AttributionState }) {
  const wrap = (children: React.ReactNode) => (
    <div className={styles.detailsWrap}>
      {children}
    </div>
  );

  if (id === 'supervisor') {
    return wrap(<KV k="query_type" v={state.query_type} />);
  }

  if (id === 'infrastructure') {
    return wrap(
      <>
        {state.graph_paths.map((g) => (
          <div key={g.template} className={styles.subRow}>
            <StatusPill status={g.status as CypherStatus} />
            <span className={styles.infraTemplate}>{g.template}</span>
            <span className={styles.infraSummary}>{g.summary}</span>
          </div>
        ))}
      </>,
    );
  }

  if (id === 'intelligence') {
    return wrap(
      <>
        {state.rag_chunks.map((c) => (
          <div key={c.chunk_id} className={styles.subRow}>
            <span className={styles.ragSourceTag}>
              {c.source}
            </span>
            <span className={styles.ragChunkId}>{c.chunk_id}</span>
            <span className={styles.ragSnippet}>
              &quot;{c.snippet}&quot;
            </span>
            <span className={styles.ragScore}>
              RRF {c.rrf_score.toFixed(2)}
            </span>
          </div>
        ))}
      </>,
    );
  }

  if (id === 'graph_probe') {
    return wrap(
      <>
        {state.candidate_actors.map((a) => (
          <div key={a.actor_name} className={styles.subRow}>
            <Icon name="check" size={11} color={tokens.status_success} />
            <span className={styles.probeActorName}>{a.actor_name}</span>
            <SourceBadge kind={a.source} />
            <span className={styles.probeConfidence}>
              {a.confidence.toFixed(2)}
            </span>
          </div>
        ))}
      </>,
    );
  }

  if (id === 'evidence_eval') {
    return wrap(
      <>
        <KV k="confidence" v={state.confidence.toFixed(2)} />
        <KV k="temporal_confidence" v={state.temporal_confidence.toFixed(2)} />
        <KV k="is_shared_infrastructure" v={String(state.is_shared_infrastructure)} />
        <KV k="needs_more_evidence" v={String(state.needs_more_evidence)} />
        <KV k="attribution_result" v={state.attribution_result} />
      </>,
    );
  }

  if (id === 'report') {
    return wrap(
      <div className={styles.reportText}>
        Rendering markdown、JSON、可复制 IOC 列表。{state.sources.length} sources · narrative{' '}
        {state.narrative.length} chars.
      </div>,
    );
  }

  return wrap(
    <div className={styles.noDetails}>No details.</div>,
  );
}
