import { tokens, fonts } from '../../lib/tokens';
import { Icon } from '../shared/Icon';
import styles from './PinCard.module.css';

export interface PinCardProps {
  tag: string;
  accent: string;
  icon: string;
  title: string;
  testId?: string;
  children: React.ReactNode;
  onOpen?: () => void;
}

export function PinCard({ tag, accent, icon, title, testId, children, onOpen }: PinCardProps) {
  return (
    <div data-testid={testId} className={styles.card}>
      <div className={styles.header}>
        <div className={styles.iconWrap} style={{ background: `${accent}14` }}>
          <Icon name={icon} size={12} color={accent} />
        </div>
        <div className={styles.titleWrap}>
          <div className={styles.tag} style={{ color: accent, fontFamily: fonts.sans }}>
            {tag}
          </div>
          <div className={styles.title} style={{ color: tokens.text, fontFamily: fonts.sans }}>
            {title}
          </div>
        </div>
        <button
          onClick={onOpen}
          className={styles.openBtn}
          style={{ color: tokens.textSubtle }}
          title="Open fullscreen"
        >
          <Icon name="ext" size={12} />
        </button>
      </div>
      <div className={styles.body}>{children}</div>
    </div>
  );
}
