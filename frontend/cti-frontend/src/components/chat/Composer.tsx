import { Icon } from '../shared/Icon';
import styles from './Composer.module.css';

export interface ComposerProps {
  onSend?: (text: string) => void;
}

export function Composer({ onSend }: ComposerProps) {
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault();
      const value = e.currentTarget.value.trim();
      if (value && onSend) {
        onSend(value);
        e.currentTarget.value = '';
      }
    }
  };

  const handleSend = () => {
    const textarea = document.querySelector<HTMLTextAreaElement>('[data-testid="composer"] textarea');
    if (textarea) {
      const value = textarea.value.trim();
      if (value && onSend) {
        onSend(value);
        textarea.value = '';
      }
    }
  };

  return (
    <div data-testid="composer" className={styles.wrapper}>
      <div className={styles.card}>
        <textarea
          onKeyDown={handleKeyDown}
          placeholder='追问 / 提供更多 IOC… e.g. "用 SAN 模式查相邻域名"'
          className={styles.textarea}
        />
        <div className={styles.toolbar}>
          <div className={styles.leftGroup}>
            <button className={styles.attachBtn}>
              <Icon name="attach" size={15} />
            </button>
            <span className={styles.modelLabel}>
              DeepSeek · LangGraph
            </span>
          </div>
          <button onClick={handleSend} className={styles.sendBtn}>
            <Icon name="arrowR" size={15} />
          </button>
        </div>
      </div>
      <div className={styles.disclaimer}>
        归因结果基于 graph + RAG 证据 · 仅供参考
      </div>
    </div>
  );
}
