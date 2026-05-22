import { tokens, fonts } from '../../lib/tokens';
import type { Source } from '../../types/AttributionState';
import styles from './SourceBadge.module.css';

export interface SourceBadgeProps {
  kind: Source;
}

const LABELS: Record<Source, string> = {
  graph: 'GRAPH',
  rag: 'RAG',
  llm: 'LLM',
};

const TOKEN_MAP: Record<Source, { fg: string; bg: string }> = {
  graph: tokens.src_graph,
  rag: tokens.src_rag,
  llm: tokens.src_llm,
};

export function SourceBadge({ kind }: SourceBadgeProps) {
  const t = TOKEN_MAP[kind];

  return (
    <span
      data-testid={`source-badge-${kind}`}
      className={styles.badge}
      style={{ fontFamily: fonts.mono, color: t.fg, background: t.bg }}
    >
      {LABELS[kind]}
    </span>
  );
}
