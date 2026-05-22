import { Icon } from '../../shared/Icon';
import styles from './Error.module.css';

export interface ErrorProps {
  errorNode: string;
  errorMessage: string;
  completedNodes: number;
  onRetry?: () => void;
  onGraphOnly?: () => void;
  onViewLogs?: () => void;
}

export function Error({ errorNode, errorMessage, completedNodes, onRetry, onGraphOnly, onViewLogs }: ErrorProps) {
  return (
    <div className={styles.container}>
      <div className={styles.avatar}>
        <Icon name="spark" size={14} color="#fff" />
      </div>
      <div className={styles.body}>
        <div data-testid="attribution-result-error" className={styles.card}>
          <div className={styles.headerRow}>
            <Icon name="flame" size={14} color="#a31a1a" />
            <span className={styles.headerText}>
              Pipeline halted
            </span>
          </div>
          <div className={styles.message}>
            <code className={styles.errorCode}>
              {errorNode}
            </code>{' '}
            node 失败：{errorMessage}。前 {completedNodes} 个 node 的结果仍可看，但未能完成归因。
          </div>
          <div className={styles.actions}>
            <button className={styles.chipPrimary} onClick={onRetry}>重试 pipeline</button>
            <button className={styles.chipSecondary} onClick={onGraphOnly}>仅跑 graph (跳过 RAG)</button>
            <button className={styles.chipSecondary} onClick={onViewLogs}>查看错误日志</button>
          </div>
        </div>
      </div>
    </div>
  );
}
