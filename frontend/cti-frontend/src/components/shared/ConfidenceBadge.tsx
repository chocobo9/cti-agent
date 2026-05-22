import { tokens, fonts } from '../../lib/tokens';
import type { AttributionResult } from '../../types/AttributionState';
import styles from './ConfidenceBadge.module.css';

export interface ConfidenceBadgeProps {
  kind: AttributionResult;
  size?: 'sm' | 'lg';
}

const LABELS: Record<AttributionResult, string> = {
  high_confidence: 'High confidence',
  medium_confidence: 'Medium confidence',
  low_confidence: 'Low confidence',
  insufficient: 'Insufficient',
};

export function ConfidenceBadge({ kind, size = 'sm' }: ConfidenceBadgeProps) {
  const t = tokens[kind];
  const sizeClass = size === 'lg' ? styles.badgeLg : styles.badgeSm;

  return (
    <span
      data-testid={`confidence-badge-${kind}`}
      className={`${styles.badge} ${sizeClass}`}
      style={{ color: t.fg, background: t.bg, fontFamily: fonts.sans }}
    >
      <span
        className={styles.dot}
        style={{ background: t.dot }}
      />
      {LABELS[kind]}
    </span>
  );
}
