import { tokens, fonts } from '../../lib/tokens';
import { Icon } from '../shared/Icon';
import type { AttributionState } from '../../types/AttributionState';
import styles from './Topbar.module.css';

export interface TopbarProps {
  state: AttributionState;
}

export function Topbar({ state }: TopbarProps) {
  return (
    <header
      data-testid="topbar"
      className={styles.topbar}
      style={{ borderBottom: `1px solid ${tokens.border}`, background: tokens.surface }}
    >
      <div
        className={styles.breadcrumb}
        style={{ color: tokens.textSubtle, fontFamily: fonts.sans }}
      >
        <span>Queries</span>
        <Icon name="chevron" size={12} />
        <span
          className={styles.domain}
          style={{ color: tokens.text, fontFamily: fonts.mono }}
        >
          {state.domain}
        </span>
        <span
          className={styles.queryType}
          style={{ color: tokens.textGhost, background: tokens.divider }}
        >
          {state.query_type} query
        </span>
      </div>

      <div className={styles.actions}>
        <button
          className={styles.ghostBtn}
          style={{ background: tokens.surface, color: tokens.text, fontFamily: fonts.sans }}
        >
          <Icon name="copy" size={13} /> Markdown
        </button>
        <button
          className={styles.ghostBtn}
          style={{ background: tokens.surface, color: tokens.text, fontFamily: fonts.sans }}
        >
          <Icon name="doc" size={13} /> JSON
        </button>
        <button
          className={styles.ghostBtn}
          style={{ background: tokens.surface, color: tokens.text, fontFamily: fonts.sans }}
        >
          <Icon name="ext" size={13} /> PDF
        </button>
        <button
          className={styles.primaryBtn}
          style={{ background: tokens.text, fontFamily: fonts.sans }}
        >
          <Icon name="pin" size={13} /> Save
        </button>
      </div>
    </header>
  );
}
