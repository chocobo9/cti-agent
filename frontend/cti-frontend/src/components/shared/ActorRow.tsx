import { useState } from 'react';
import { tokens, fonts } from '../../lib/tokens';
import { Icon } from './Icon';
import { SourceBadge } from './SourceBadge';
import styles from './ActorRow.module.css';
import type { CandidateActor } from '../../types/AttributionState';

export interface ActorRowProps {
  actor: CandidateActor;
  defaultOpen?: boolean;
}

export function ActorRow({ actor, defaultOpen = false }: ActorRowProps) {
  const [open, setOpen] = useState(defaultOpen);
  const pct = Math.round(actor.confidence * 100);

  return (
    <div className={styles.row} style={{ border: `1px solid ${tokens.border}`, background: tokens.surface }}>
      <div className={styles.header} onClick={() => setOpen((o) => !o)}>
        <Icon name={open ? 'down' : 'chevron'} size={11} color={tokens.textGhost} />
        <span className={styles.name} style={{ color: tokens.text, fontFamily: fonts.sans }}>
          {actor.actor_name}
        </span>
        <SourceBadge kind={actor.source} />
        <span className={styles.confidence} style={{ fontFamily: fonts.mono, color: tokens.text }}>
          {actor.confidence.toFixed(2)}
        </span>
      </div>
      <div className={styles.barTrack} style={{ background: tokens.divider }}>
        <div className={styles.barFill} style={{ width: `${pct}%`, background: tokens.text }} />
      </div>
      {open && (
        <div className={styles.evidenceList}>
          {actor.supporting_evidence.map((e, i) => (
            <div
              key={i}
              className={styles.evidenceItem}
              style={{ color: tokens.textMute, borderLeft: `2px solid ${tokens.border}` }}
            >
              <span>•</span>
              <span style={{ fontFamily: fonts.mono }}>{e}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
