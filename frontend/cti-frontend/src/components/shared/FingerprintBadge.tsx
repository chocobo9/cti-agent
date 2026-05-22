import { tokens, fonts } from '../../lib/tokens';
import { Icon } from './Icon';
import styles from './FingerprintBadge.module.css';

export interface FingerprintBadgeProps {
  label: string;
  value: string;
}

export function FingerprintBadge({ label, value }: FingerprintBadgeProps) {
  return (
    <div className={styles.badge} style={{ background: tokens.divider, fontFamily: fonts.mono }}>
      <Icon name="fingerprint" size={11} color={tokens.textSubtle} />
      <span style={{ color: tokens.textSubtle }} className={styles.label}>{label}</span>
      <span style={{ color: tokens.text }} className={styles.value}>{value}</span>
    </div>
  );
}
