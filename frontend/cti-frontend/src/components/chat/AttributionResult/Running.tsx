import { tokens } from '../../../lib/tokens';
import { Icon } from '../../shared/Icon';
import styles from './Running.module.css';

export interface RunningProps {
  domain: string;
  completedNodes: number;
  totalNodes: number;
}

export function Running({ domain, completedNodes, totalNodes }: RunningProps) {
  return (
    <div className={styles.container}>
      <div className={styles.avatar}>
        <Icon name="spark" size={14} color="#fff" />
      </div>
      <div className={styles.body}>
        <div data-testid="attribution-result-running" className={styles.card}>
          <div className={styles.shimmerBar} />

          <div className={styles.headerRow}>
            <div className={styles.spinner} />
            <div className={styles.domainName}>
              {domain}
            </div>
            <span className={styles.analyzingPill}>
              Analyzing…
            </span>
          </div>

          <div className={styles.metricsGrid}>
            {['Top actor', 'Confidence', 'Temporal', 'Shared infra'].map((k) => (
              <div key={k}>
                <div className={styles.metricLabel}>
                  {k}
                </div>
                <div className={styles.skeletonBar} />
              </div>
            ))}
          </div>

          <div className={styles.narrativeSkeleton}>
            <div className={`${styles.skeletonLine} ${styles.skeletonLine1}`} />
            <div className={`${styles.skeletonLine} ${styles.skeletonLine2}`} />
            <div className={`${styles.skeletonLine} ${styles.skeletonLine3}`} />
          </div>

          <div className={styles.progressText}>
            已完成 <b style={{ color: tokens.text }}>{completedNodes}</b> / {totalNodes} 个 node · 预计 2–3s
            后完成
          </div>
        </div>
      </div>
    </div>
  );
}
