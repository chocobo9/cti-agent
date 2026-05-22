import { PreviousTurn } from './PreviousTurn';
import { UserMsg } from './UserMsg';
import { AgentIntro } from './AgentIntro';
import { NodeQueue } from './NodeQueue';
import { Composer } from './Composer';
import type { AttributionState } from '../../types/AttributionState';
import type { NodeRun } from './NodeQueue';
import styles from './ChatColumn.module.css';

interface PreviousTurnData {
  query: string;
  state: AttributionState | null;
}

export interface ChatColumnProps {
  state: AttributionState;
  nodes: NodeRun[];
  children?: React.ReactNode;
  onSend?: (text: string) => void;
  previousTurns?: PreviousTurnData[];
}

function timeAgo(ts: number): string {
  const diff = Date.now() - ts;
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export function ChatColumn({ state, nodes, children, onSend, previousTurns }: ChatColumnProps) {
  return (
    <section data-testid="chat-column" className={styles.section}>
      <div className={styles.scrollArea}>
        {previousTurns?.map((turn, i) =>
          turn.state ? (
            <PreviousTurn
              key={i}
              timeAgo={timeAgo(Date.now() - (previousTurns.length - i) * 3600000)}
              domain={turn.state.domain}
              query={turn.query}
              result={turn.state.attribution_result}
              topActor={turn.state.candidate_actors[0]?.actor_name ?? '—'}
              topConfidence={turn.state.candidate_actors[0]?.confidence ?? 0}
            />
          ) : null,
        )}
        {state.query && <UserMsg text={state.query} />}
        {state.query && <AgentIntro />}
        {state.query && <NodeQueue nodes={nodes} state={state} />}
        {children}
      </div>
      <Composer onSend={onSend} />
    </section>
  );
}
