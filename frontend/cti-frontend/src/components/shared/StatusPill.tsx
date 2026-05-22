import { tokens, fonts } from '../../lib/tokens';
import type { CypherStatus } from '../../types/AttributionState';
import styles from './StatusPill.module.css';

export interface StatusPillProps {
  status: CypherStatus;
}

const COLOR_MAP: Record<CypherStatus, string> = {
  success: tokens.status_success,
  empty: tokens.status_empty,
  error: tokens.status_error,
  no_match: tokens.status_no_match,
};

const LABELS: Record<CypherStatus, string> = {
  success: 'success',
  empty: 'empty',
  error: 'error',
  no_match: 'no match',
};

export function StatusPill({ status }: StatusPillProps) {
  const color = COLOR_MAP[status];

  return (
    <span
      data-testid={`status-pill-${status}`}
      className={styles.pill}
      style={{ fontFamily: fonts.mono, color }}
    >
      <span
        className={styles.dot}
        style={{ background: color }}
      />
      {LABELS[status]}
    </span>
  );
}
