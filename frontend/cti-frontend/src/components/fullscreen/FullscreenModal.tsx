import { useEffect } from 'react';
import { tokens, fonts } from '../../lib/tokens';
import { Icon } from '../shared/Icon';
import styles from './FullscreenModal.module.css';

export interface FullscreenModalProps {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}

export function FullscreenModal({ title, onClose, children }: FullscreenModalProps) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  return (
    <div
      data-testid="fullscreen-modal"
      onClick={onClose}
      className={styles.overlay}
      style={{ fontFamily: fonts.sans }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className={styles.dialog}
        style={{ background: tokens.surface, color: tokens.text }}
      >
        <div className={styles.headerBar} style={{ borderBottom: `1px solid ${tokens.border}` }}>
          <div className={styles.headerIcon} style={{ background: `${tokens.accent}1a` }}>
            <Icon name="ext" size={13} color={tokens.accent} />
          </div>
          <div className={styles.headerTitleWrap}>
            <div className={styles.headerTag} style={{ color: tokens.textGhost }}>
              Artifact detail
            </div>
            <div className={styles.headerTitle}>{title}</div>
          </div>
          <button
            onClick={onClose}
            className={styles.closeBtn}
            style={{ background: tokens.divider, color: tokens.textMute }}
            title="Close (Esc)"
          >
            <Icon name="x" size={14} />
          </button>
        </div>
        <div className={styles.content}>
          {children}
        </div>
      </div>
    </div>
  );
}
