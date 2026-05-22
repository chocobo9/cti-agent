import { tokens, fonts } from '../../lib/tokens';
import { PinCard } from './PinCard';
import type { AttributionState } from '../../types/AttributionState';
import styles from './EvidenceChainCard.module.css';

export interface EvidenceChainCardProps {
  state: AttributionState;
  onOpen?: () => void;
}

export function EvidenceChainCard({ state, onOpen }: EvidenceChainCardProps) {
  return (
    <PinCard
      testId="pin-card-evidence"
      tag="EVIDENCE CHAIN"
      accent="#10b981"
      icon="cpu"
      title="Reasoning trail · transparent"
      onOpen={onOpen}
    >
      <div className={styles.timeline} style={{ borderLeft: `2px solid ${tokens.border}` }}>
        {state.evidence_chain.map((e, i) => (
          <div
            key={i}
            className={styles.step}
            style={{ color: tokens.textMute, fontFamily: fonts.sans }}
          >
            <span className={styles.stepNum} style={{ fontFamily: fonts.mono, color: tokens.textGhost }}>
              {i + 1}
            </span>
            <span className={styles.stepText}>{e}</span>
          </div>
        ))}
      </div>
      <div className={styles.badgesRow}>
        <span className={styles.badge} style={{ background: tokens.divider, color: tokens.textMute, fontFamily: fonts.sans }}>
          {state.graph_paths.length} Cypher templates
        </span>
        <span className={styles.badge} style={{ background: tokens.divider, color: tokens.textMute, fontFamily: fonts.sans }}>
          {state.rag_chunks.length} RAG chunks
        </span>
      </div>
    </PinCard>
  );
}
