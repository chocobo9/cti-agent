import { useState } from 'react';
import { tokens, fonts } from '../../lib/tokens';
import { Icon } from '../shared/Icon';
import type { AttributionState } from '../../types/AttributionState';
import styles from './RawJsonPanel.module.css';

export interface RawJsonPanelProps {
  state: AttributionState;
}

export function RawJsonPanel({ state }: RawJsonPanelProps) {
  const text = JSON.stringify(state, null, 2);
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(text).catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 1400);
  };

  return (
    <div data-testid="raw-json-panel" className={styles.panel}>
      <div className={styles.toolbar}>
        <div className={styles.label} style={{ color: tokens.textGhost, fontFamily: fonts.sans }}>
          AttributionState · {text.length} chars
        </div>
        <button
          onClick={handleCopy}
          className={styles.copyBtn}
          style={{
            border: `1px solid #e4e4e0`,
            background: copied ? '#e6f6ee' : tokens.surface,
            color: copied ? '#067a4a' : tokens.text,
            fontFamily: fonts.sans,
          }}
        >
          <Icon name={copied ? 'check' : 'copy'} size={11} />
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>
      <pre
        className={styles.pre}
        style={{
          background: tokens.bg,
          border: `1px solid ${tokens.border}`,
          fontFamily: fonts.mono,
          color: tokens.text,
        }}
      >
        {text}
      </pre>
    </div>
  );
}
