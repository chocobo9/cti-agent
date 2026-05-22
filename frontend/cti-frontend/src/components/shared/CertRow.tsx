import { tokens, fonts } from '../../lib/tokens';
import { Icon } from './Icon';
import styles from './CertRow.module.css';
import type { Certificate } from '../../types/AttributionState';

export interface CertRowProps {
  cert: Certificate;
}

export function CertRow({ cert }: CertRowProps) {
  return (
    <div className={styles.row}>
      <Icon name="lock" size={11} color={tokens.textSubtle} />
      <span className={styles.fingerprint} style={{ fontFamily: fonts.mono, color: tokens.text }}>
        {cert.fingerprint}
      </span>
      <span style={{ color: tokens.textSubtle }}>{cert.issuer}</span>
    </div>
  );
}
