import styles from './UserMsg.module.css';

export interface UserMsgProps {
  text: string;
}

export function UserMsg({ text }: UserMsgProps) {
  return (
    <div className={styles.container}>
      <div className={styles.bubble}>
        {text}
      </div>
      <div className={styles.avatar}>
        SY
      </div>
    </div>
  );
}
