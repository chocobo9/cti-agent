import { tokens, fonts } from '../../lib/tokens';
import { Icon } from '../shared/Icon';
import styles from './Rail.module.css';

export function Rail() {
  return (
    <aside
      data-testid="rail"
      className={styles.rail}
      style={{ borderRight: `1px solid ${tokens.border}`, background: tokens.rail }}
    >
      <div
        className={styles.logo}
        style={{ background: tokens.text, fontFamily: fonts.sans }}
      >
        C
      </div>

      {(['plus', 'history', 'graph', 'pin'] as const).map((name, i) => (
        <button
          key={name}
          className={styles.railBtn}
          style={{
            background: i === 0 ? tokens.border : 'transparent',
            color: i === 0 ? tokens.text : tokens.textSubtle,
            fontFamily: fonts.sans,
          }}
        >
          <Icon name={name} size={18} />
        </button>
      ))}

      <div className={styles.avatarWrap}>
        <div
          className={styles.avatar}
          style={{ color: tokens.textMute, fontFamily: fonts.sans }}
        >
          SY
        </div>
      </div>
    </aside>
  );
}
