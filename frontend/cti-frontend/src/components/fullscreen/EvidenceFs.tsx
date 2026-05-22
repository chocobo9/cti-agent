import { tokens, fonts } from '../../lib/tokens';
import { StatusPill } from '../shared/StatusPill';
import type { AttributionState, CypherStatus } from '../../types/AttributionState';
import styles from './EvidenceFs.module.css';

export interface EvidenceFsProps {
  state: AttributionState;
}

export function EvidenceFs({ state }: EvidenceFsProps) {
  return (
    <div className={styles.root}>
      <div>
        <SectionHead>Evidence chain</SectionHead>
        <ol className={styles.evidenceOl}>
          {state.evidence_chain.map((e, i) => (
            <li key={i} className={styles.evidenceLi} style={{ border: `1px solid ${tokens.border}`, background: tokens.bg }}>
              <span className={styles.stepNumber} style={{ background: tokens.text, color: '#fff', fontFamily: fonts.mono }}>
                {i + 1}
              </span>
              <span className={styles.stepText} style={{ color: tokens.textMute, fontFamily: fonts.sans }}>{e}</span>
            </li>
          ))}
        </ol>
      </div>

      <div className={styles.columnsGrid}>
        <div>
          <SectionHead>Graph paths (Cypher)</SectionHead>
          <div className={styles.pathList}>
            {state.graph_paths.map((g) => (
              <div key={g.template} className={styles.pathCard} style={{ border: `1px solid ${tokens.border}`, background: tokens.bg }}>
                <div className={styles.pathHeader}>
                  <StatusPill status={g.status as CypherStatus} />
                  <span className={styles.pathTemplate} style={{ fontFamily: fonts.mono, color: tokens.text }}>{g.template}</span>
                </div>
                <div className={styles.pathSummary} style={{ color: tokens.textSubtle, fontFamily: fonts.sans }}>{g.summary}</div>
              </div>
            ))}
          </div>
        </div>

        <div>
          <SectionHead>RAG chunks (top by RRF)</SectionHead>
          <div className={styles.pathList}>
            {state.rag_chunks.map((c) => (
              <div key={c.chunk_id} className={styles.chunkCard} style={{ border: `1px solid ${tokens.border}`, background: tokens.bg }}>
                <div className={styles.chunkHeader}>
                  <span className={styles.chunkSource} style={{ fontFamily: fonts.mono, background: tokens.divider, color: tokens.textMute }}>
                    {c.source}
                  </span>
                  <span className={styles.chunkId} style={{ color: tokens.textGhost, fontFamily: fonts.mono }}>{c.chunk_id}</span>
                  <span className={styles.chunkScore} style={{ fontFamily: fonts.mono, color: tokens.text }}>
                    RRF {c.rrf_score.toFixed(2)}
                  </span>
                </div>
                <div className={styles.chunkSnippet} style={{ color: tokens.textMute, fontFamily: fonts.sans }}>
                  &quot;{c.snippet}&quot;
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function SectionHead({ children }: { children: React.ReactNode }) {
  return (
    <div className={styles.sectionHead} style={{ color: tokens.textSubtle, fontFamily: fonts.sans }}>
      {children}
    </div>
  );
}
