import { useState } from 'react';
import { tokens, fonts } from '../../lib/tokens';
import { AttributionCard } from './AttributionCard';
import { CandidatesCard } from './CandidatesCard';
import { InfrastructureCard } from './InfrastructureCard';
import { EvidenceChainCard } from './EvidenceChainCard';
import { RawJsonPanel } from './RawJsonPanel';
import type { AttributionState } from '../../types/AttributionState';
import styles from './Pinboard.module.css';

export interface PinboardProps {
  state: AttributionState;
  onOpenCard?: (key: string) => void;
}

type PinView = 'pinned' | 'raw';

export function Pinboard({ state, onOpenCard }: PinboardProps) {
  const [view, setView] = useState<PinView>('pinned');
  const open = (key: string) => onOpenCard?.(key);

  return (
    <aside
      data-testid="pinboard"
      className={styles.aside}
      style={{ background: tokens.bg }}
    >
      {/* Header with segmented control */}
      <div
        className={styles.header}
        style={{ borderBottom: `1px solid ${tokens.border}`, background: tokens.rail }}
      >
        <div data-testid="segmented-control" className={styles.segmented}>
          {(['pinned', 'raw'] as const).map((k) => {
            const label = k === 'pinned' ? 'Pinned' : 'Raw JSON';
            return (
              <button
                key={k}
                onClick={() => setView(k)}
                className={styles.segBtn}
                style={{
                  background: view === k ? tokens.surface : 'transparent',
                  color: view === k ? tokens.text : tokens.textSubtle,
                  fontWeight: view === k ? 600 : 500,
                  fontFamily: fonts.sans,
                  boxShadow: view === k ? '0 1px 2px rgba(20,20,40,0.08)' : 'none',
                }}
              >
                {label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Content */}
      {view === 'pinned' && (
        <div className={styles.cardList}>
          <AttributionCard state={state} onOpen={() => open('attribution')} />
          <CandidatesCard actors={state.candidate_actors} onOpen={() => open('candidates')} />
          <InfrastructureCard enrichment={state.enrichment} onOpen={() => open('infrastructure')} />
          <EvidenceChainCard state={state} onOpen={() => open('evidence')} />
        </div>
      )}
      {view === 'raw' && (
        <div className={styles.rawWrap}>
          <RawJsonPanel state={state} />
        </div>
      )}
    </aside>
  );
}
