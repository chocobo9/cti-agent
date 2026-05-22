import type { AttributionState, NodeEvent } from '../types/AttributionState';
import { sampleState } from '../fixtures/sampleState';
import { parseNodeEvent, parseAttributionState } from './validate';

export type StreamCallback = (event: NodeEvent) => void;
export type DoneCallback = (state: AttributionState) => void;
export type ErrorCallback = (error: string) => void;

const MOCK_ENABLED = import.meta.env.VITE_MOCK === 'true' || !import.meta.env.VITE_API_URL;

const NODE_IDS = ['supervisor', 'infrastructure', 'intelligence', 'graph_probe', 'evidence_eval', 'report'];
const NODE_DURATIONS = [240, 1840, 1290, 480, 620, 350];

function mockStream(
  _query: string,
  onEvent: StreamCallback,
  onDone: DoneCallback,
  onError: ErrorCallback,
): () => void {
  let cancelled = false;
  let timeoutId: ReturnType<typeof setTimeout>;

  const run = async () => {
    let elapsed = 0;
    for (let i = 0; i < NODE_IDS.length; i++) {
      if (cancelled) return;

      onEvent({
        type: 'node_start',
        node_id: NODE_IDS[i],
        ts: Date.now(),
      });

      const dur = NODE_DURATIONS[i];
      await new Promise<void>((resolve) => {
        timeoutId = setTimeout(resolve, Math.min(dur, 400));
      });
      if (cancelled) return;

      elapsed += dur;
      onEvent({
        type: 'node_done',
        node_id: NODE_IDS[i],
        ts: Date.now(),
        duration_ms: dur,
      });
    }

    onDone(sampleState);
  };

  run().catch((err) => {
    if (!cancelled) onError(String(err));
  });

  return () => {
    cancelled = true;
    clearTimeout(timeoutId);
  };
}

function sseStream(
  query: string,
  onEvent: StreamCallback,
  onDone: DoneCallback,
  onError: ErrorCallback,
): () => void {
  const controller = new AbortController();
  const apiUrl = import.meta.env.VITE_API_URL as string;

  fetch(`${apiUrl}/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query }),
    signal: controller.signal,
  })
    .then(async (res) => {
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      if (!res.body) throw new Error('No response body');

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6).trim();
            if (data === '[DONE]') return;
            try {
              const parsed = JSON.parse(data);
              const nodeEvt = parseNodeEvent(parsed);
              if (nodeEvt) {
                onEvent(nodeEvt);
                continue;
              }
              const state = parseAttributionState(parsed);
              if (state) {
                onDone(state);
              }
            } catch {
              // skip malformed lines
            }
          }
        }
      }
    })
    .catch((err) => {
      if (!controller.signal.aborted) {
        onError(err instanceof Error ? err.message : String(err));
      }
    });

  return () => controller.abort();
}

export function startQuery(
  query: string,
  onEvent: StreamCallback,
  onDone: DoneCallback,
  onError: ErrorCallback,
): () => void {
  if (MOCK_ENABLED) {
    return mockStream(query, onEvent, onDone, onError);
  }
  return sseStream(query, onEvent, onDone, onError);
}
