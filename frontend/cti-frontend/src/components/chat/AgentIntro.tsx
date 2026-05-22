import { tokens } from '../../lib/tokens';
import { Icon } from '../shared/Icon';
import styles from './AgentIntro.module.css';

export function AgentIntro() {
  return (
    <div className={styles.container}>
      <div className={styles.avatar}>
        <Icon name="spark" size={14} color="#fff" />
      </div>
      <div className={styles.body}>
        <div className={styles.text}>
          路由为<b style={{ color: tokens.text }}>结构化查询</b>。已运行 6 个 node：infrastructure（5 个 Cypher
          模板）→ intelligence（RAG，12 chunks）→ graph_probe 验证 → evidence_eval 评估 → 合成报告。
        </div>
      </div>
    </div>
  );
}
