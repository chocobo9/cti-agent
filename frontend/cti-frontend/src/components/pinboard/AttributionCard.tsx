import { tokens, fonts } from '../../lib/tokens';
import { PinCard } from './PinCard';
import type { AttributionState } from '../../types/AttributionState';
import styles from './AttributionCard.module.css';

export interface AttributionCardProps {
  state: AttributionState;
  onOpen?: () => void;
}

function ConfidenceBar({ label, value, color }: { label: string; value: number; color: string }) {
  const pct = Math.round(value * 100);
  return (
    <div>
      <div className={styles.barHeader} style={{ color: tokens.textMute }}>
        <span style={{ fontFamily: fonts.sans }}>{label}</span>
        <span style={{ fontFamily: fonts.mono, fontWeight: 600 }}>{value.toFixed(2)}</span>
      </div>
      <div className={styles.barTrack} style={{ background: tokens.divider }}>
        <div className={styles.barFill} style={{ width: `${pct}%`, background: color }} />
      </div>
    </div>
  );
}

function Flag({ label, sub, ok }: { label: string; sub: string; ok: boolean }) {
  const dotColor = ok ? tokens.status_success : tokens.medium_confidence.dot;
  return (
    <div className={styles.flagWrap} style={{ background: tokens.divider }}>
      <span className={styles.flagDot} style={{ background: dotColor }} />
      <div className={styles.flagText} style={{ fontFamily: fonts.sans }}>
        <div style={{ color: tokens.text, fontWeight: 500 }}>{label}</div>
        <div style={{ color: tokens.textSubtle }}>{sub}</div>
      </div>
    </div>
  );
}

export function AttributionCard({ state, onOpen }: AttributionCardProps) {
  const t = tokens[state.attribution_result];
  const LABELS = {
    high_confidence: 'High confidence',
    medium_confidence: 'Medium confidence',
    low_confidence: 'Low confidence',
    insufficient: 'Insufficient',
  } as const;

  return (
    <PinCard
      testId="pin-card-attribution"
      tag="ATTRIBUTION RESULT"
      accent={t.dot}
      icon="target"
      title={`${LABELS[state.attribution_result]}  ·  ${state.confidence.toFixed(2)}`}
      onOpen={onOpen}
    >
      <div className={styles.barsColumn}>
        <ConfidenceBar label="Attribution" value={state.confidence} color={t.dot} />
        <ConfidenceBar label="Temporal (180d HL)" value={state.temporal_confidence} color={tokens.textSubtle} />
      </div>
      <div className={styles.flagsRow}>
        <Flag
          label="Shared infra"
          sub={state.is_shared_infrastructure ? 'CDN/cloud detected' : 'Dedicated'}
          ok={!state.is_shared_infrastructure}
        />
        <Flag
          label="Evidence sufficiency"
          sub={state.needs_more_evidence ? 'iterate' : 'sufficient'}
          ok={!state.needs_more_evidence}
        />
      </div>
    </PinCard>
  );
}
