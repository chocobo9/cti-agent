import { tokens, fonts } from '../../lib/tokens';
import { SourceBadge } from '../shared/SourceBadge';
import type { AttributionState } from '../../types/AttributionState';
import styles from './AttributionFs.module.css';

export interface AttributionFsProps {
  state: AttributionState;
}

function DetailBlock({ label, value, bar, color, desc }: {
  label: string; value: string; bar: number; color: string; desc: string;
}) {
  return (
    <div className={styles.detailBlock} style={{ border: `1px solid ${tokens.border}`, background: tokens.bg }}>
      <div className={styles.detailHeader}>
        <div className={styles.detailLabel} style={{ color: tokens.textSubtle, fontFamily: fonts.sans }}>{label}</div>
        <div className={styles.detailValue} style={{ fontFamily: fonts.mono, color: tokens.text }}>{value}</div>
      </div>
      <div className={styles.barTrack} style={{ background: tokens.divider }}>
        <div className={styles.barFill} style={{ width: `${Math.round(bar * 100)}%`, background: color }} />
      </div>
      <div className={styles.detailDesc} style={{ color: tokens.textSubtle, fontFamily: fonts.sans }}>{desc}</div>
    </div>
  );
}

function FlagBlock({ label, sub, ok }: { label: string; sub: string; ok: boolean }) {
  const c = ok ? tokens.status_success : tokens.medium_confidence.dot;
  return (
    <div className={styles.flagBlock} style={{ border: `1px solid ${c}33`, background: `${c}0d` }}>
      <span className={styles.flagDot} style={{ background: c }} />
      <div style={{ fontFamily: fonts.sans }}>
        <div className={styles.flagLabel} style={{ color: tokens.text }}>{label}</div>
        <div className={styles.flagSub} style={{ color: tokens.textMute }}>{sub}</div>
      </div>
    </div>
  );
}

const LABELS = {
  high_confidence: 'High confidence',
  medium_confidence: 'Medium confidence',
  low_confidence: 'Low confidence',
  insufficient: 'Insufficient',
} as const;

export function AttributionFs({ state }: AttributionFsProps) {
  const t = tokens[state.attribution_result];

  return (
    <div className={styles.root}>
      <div className={styles.heroBanner} style={{ background: `${t.dot}0d`, borderLeft: `4px solid ${t.dot}` }}>
        <div className={styles.heroLabel} style={{ color: t.fg, fontFamily: fonts.sans }}>
          {LABELS[state.attribution_result]}
        </div>
        <div className={styles.heroScore} style={{ fontFamily: fonts.mono, color: tokens.text }}>
          {state.confidence.toFixed(2)}
        </div>
        <div className={styles.heroNarrative} style={{ color: tokens.textMute, fontFamily: fonts.sans }}>
          {state.narrative}
        </div>
      </div>

      <div className={styles.detailGrid}>
        <DetailBlock label="Attribution confidence" value={state.confidence.toFixed(2)} bar={state.confidence} color={t.dot}
          desc="Composite of graph-path strength and RAG corroboration." />
        <DetailBlock label="Temporal confidence" value={state.temporal_confidence.toFixed(2)} bar={state.temporal_confidence} color={tokens.textSubtle}
          desc="Half-life decay (180d). Older evidence weighted lower." />
      </div>

      <div className={styles.detailGrid}>
        <FlagBlock ok={!state.is_shared_infrastructure} label="Shared infrastructure"
          sub={state.is_shared_infrastructure ? 'CDN / cloud detected — infrastructure is multi-tenant' : 'Dedicated infrastructure — attribution weight unaffected'} />
        <FlagBlock ok={!state.needs_more_evidence} label="Evidence sufficiency"
          sub={state.needs_more_evidence ? 'Pipeline recommends iteration — supply more IOCs or run extra templates' : 'Sufficient evidence — no iteration needed'} />
      </div>

      <div>
        <div className={styles.sectionHead} style={{ color: tokens.textSubtle, fontFamily: fonts.sans }}>
          Sources used
        </div>
        <div className={styles.sourcesList}>
          {state.sources.map((s, i) => (
            <div key={i} className={styles.sourceRow} style={{ border: `1px solid ${tokens.border}` }}>
              <SourceBadge kind={s.type} />
              <span className={styles.sourceDetail} style={{ color: tokens.textMute, fontFamily: fonts.mono }}>{s.detail}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
