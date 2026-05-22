import { tokens } from '../../../lib/tokens';
import { Icon } from '../../shared/Icon';
import { ConfidenceBadge } from '../../shared/ConfidenceBadge';
import type { AttributionState } from '../../../types/AttributionState';
import styles from './Done.module.css';

export interface DoneProps {
  state: AttributionState;
  onViewEvidence?: () => void;
  onExpandCandidates?: () => void;
  onCopyMarkdown?: () => void;
  onExportJson?: () => void;
}

export function Done({ state, onViewEvidence, onExpandCandidates, onCopyMarkdown, onExportJson }: DoneProps) {
  const top = state.candidate_actors[0];

  return (
    <div className={styles.container}>
      <div className={styles.avatar}>
        <Icon name="spark" size={14} color="#fff" />
      </div>
      <div className={styles.body}>
        <div data-testid="attribution-result-done" className={styles.card}>
          <div className={styles.headerRow}>
            <div className={styles.domainName}>
              {state.domain}
            </div>
            <ConfidenceBadge kind={state.attribution_result} size="lg" />
          </div>

          <div className={styles.metricsGrid}>
            {([
              ['Top actor', top?.actor_name ?? '—'],
              ['Confidence', state.confidence.toFixed(2)],
              ['Temporal', state.temporal_confidence.toFixed(2)],
              ['Shared infra', state.is_shared_infrastructure ? 'Yes' : 'No'],
            ] as const).map(([k, v]) => (
              <div key={k}>
                <div className={styles.metricLabel}>
                  {k}
                </div>
                <div className={styles.metricValue}>
                  {v}
                </div>
              </div>
            ))}
          </div>

          {state.needs_more_evidence && (
            <div className={styles.evidenceWarning}>
              证据不足 — 建议提供更多 IOC 或运行额外模板
            </div>
          )}

          <div className={styles.narrative}>
            {state.narrative}
          </div>

          <div className={styles.actions}>
            <button className={styles.chipPrimary} onClick={onViewEvidence}>查看证据链</button>
            <button className={styles.chipSecondary} onClick={onExpandCandidates}>展开候选演员</button>
            <button className={styles.chipSecondary} onClick={onCopyMarkdown}>复制 Markdown</button>
            <button className={styles.chipSecondary} onClick={onExportJson}>导出 JSON</button>
          </div>
        </div>
      </div>
    </div>
  );
}
