import { tokens } from '../../lib/tokens';
import { Icon } from '../shared/Icon';
import { ConfidenceBadge } from '../shared/ConfidenceBadge';
import type { AttributionResult } from '../../types/AttributionState';
import styles from './PreviousTurn.module.css';

export interface PreviousTurnProps {
  timeAgo: string;
  domain: string;
  query: string;
  result: AttributionResult;
  topActor: string;
  topConfidence: number;
  onClick?: () => void;
}

export function PreviousTurn({
  timeAgo,
  domain,
  query,
  result,
  topActor,
  topConfidence,
  onClick,
}: PreviousTurnProps) {
  return (
    <button onClick={onClick} className={styles.button}>
      <Icon name="time" size={12} color={tokens.textGhost} />
      <span className={styles.timeLabel}>
        {timeAgo}
      </span>
      <span className={styles.domainQuery}>
        {domain}　— {query}
      </span>
      <ConfidenceBadge kind={result} />
      <span className={styles.actorConfidence}>
        {topActor} · {topConfidence.toFixed(2)}
      </span>
      <Icon name="chevron" size={12} color={tokens.textGhost} />
    </button>
  );
}
