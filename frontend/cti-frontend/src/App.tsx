import { useState, useCallback, useRef } from 'react';
import { QueryWorkspace } from './pages/QueryWorkspace';
import { Done } from './components/chat/AttributionResult/Done';
import { Running } from './components/chat/AttributionResult/Running';
import { Error as ErrorCard } from './components/chat/AttributionResult/Error';
import { startQuery } from './lib/api';
import { saveToHistory } from './lib/history';
import { getNodeSub, makePlaceholderState } from './lib/attributionHelpers';
import { NODE_IDS, NODE_LABELS, NODE_SUBS } from './fixtures/nodeConfig';
import type { AttributionState, NodeStatus, NodeEvent } from './types/AttributionState';

interface TurnState {
  query: string;
  state: AttributionState | null;
  nodeStatuses: Record<string, NodeStatus>;
  nodeDurations: Record<string, number>;
  error: string | null;
  errorNode: string | null;
}

function makeInitialNodeStatuses(): Record<string, NodeStatus> {
  const r: Record<string, NodeStatus> = {};
  for (const id of NODE_IDS) r[id] = 'queued';
  return r;
}

function App() {
  const [turns, setTurns] = useState<TurnState[]>([]);
  const cancelRef = useRef<(() => void) | null>(null);

  const currentTurn = turns.length > 0 ? turns[turns.length - 1] : null;
  const previousTurns = turns.slice(0, -1);

  const handleSend = useCallback((text: string) => {
    if (cancelRef.current) cancelRef.current();

    const newTurn: TurnState = {
      query: text,
      state: null,
      nodeStatuses: makeInitialNodeStatuses(),
      nodeDurations: {},
      error: null,
      errorNode: null,
    };

    setTurns((prev) => [...prev, newTurn]);

    const cancel = startQuery(
      text,
      (event: NodeEvent) => {
        setTurns((prev) => {
          const updated = [...prev];
          const last = { ...updated[updated.length - 1] };
          const statuses = { ...last.nodeStatuses };
          const durations = { ...last.nodeDurations };

          if (event.type === 'node_start') {
            statuses[event.node_id] = 'running';
          } else if (event.type === 'node_done') {
            statuses[event.node_id] = 'done';
            if (event.duration_ms) durations[event.node_id] = event.duration_ms;
          } else if (event.type === 'node_error') {
            statuses[event.node_id] = 'error';
            last.error = event.error ?? 'Unknown error';
            last.errorNode = event.node_id;
          }

          last.nodeStatuses = statuses;
          last.nodeDurations = durations;
          updated[updated.length - 1] = last;
          return updated;
        });
      },
      (state: AttributionState) => {
        setTurns((prev) => {
          const updated = [...prev];
          const last = { ...updated[updated.length - 1] };
          last.state = state;
          const statuses = { ...last.nodeStatuses };
          for (const id of NODE_IDS) {
            if (statuses[id] !== 'error') statuses[id] = 'done';
          }
          last.nodeStatuses = statuses;
          updated[updated.length - 1] = last;
          return updated;
        });
        saveToHistory(state);
      },
      (error: string) => {
        setTurns((prev) => {
          const updated = [...prev];
          const last = { ...updated[updated.length - 1] };
          last.error = error;
          updated[updated.length - 1] = last;
          return updated;
        });
      },
    );

    cancelRef.current = cancel;
  }, []);

  const handleRetry = useCallback(() => {
    if (currentTurn) handleSend(currentTurn.query);
  }, [currentTurn, handleSend]);

  if (!currentTurn) {
    return <EmptyState onSend={handleSend} />;
  }

  const isRunning = !currentTurn.state && !currentTurn.error;
  const isError = !!currentTurn.error && !currentTurn.state;
  const isDone = !!currentTurn.state;

  const nodes = NODE_IDS.map((id) => ({
    id,
    label: NODE_LABELS[id],
    status: currentTurn.nodeStatuses[id],
    ms: currentTurn.nodeDurations[id] ?? 0,
    sub: currentTurn.state
      ? getNodeSub(id, currentTurn.state)
      : NODE_SUBS[id],
  }));

  const displayState = currentTurn.state ?? makePlaceholderState(currentTurn.query);
  const completedCount = Object.values(currentTurn.nodeStatuses).filter((s) => s === 'done').length;

  return (
    <QueryWorkspace
      state={displayState}
      nodes={nodes}
      previousTurns={previousTurns}
    >
      {isDone && <Done state={currentTurn.state!} />}
      {isRunning && (
        <Running
          domain={displayState.domain}
          completedNodes={completedCount}
          totalNodes={6}
        />
      )}
      {isError && (
        <ErrorCard
          errorNode={currentTurn.errorNode ?? 'unknown'}
          errorMessage={currentTurn.error!}
          completedNodes={completedCount}
          onRetry={handleRetry}
        />
      )}
    </QueryWorkspace>
  );
}

function EmptyState({ onSend }: { onSend: (text: string) => void }) {
  const placeholderState = makePlaceholderState('');
  const emptyNodes = NODE_IDS.map((id) => ({
    id,
    label: NODE_LABELS[id],
    status: 'queued' as NodeStatus,
    ms: 0,
    sub: NODE_SUBS[id],
  }));

  return (
    <QueryWorkspace state={placeholderState} nodes={emptyNodes} onSend={onSend}>
      <div />
    </QueryWorkspace>
  );
}

export default App;
