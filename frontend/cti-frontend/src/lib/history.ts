import type { AttributionResult, AttributionState } from '../types/AttributionState';

export interface HistoryEntry {
  id: string;
  ts: number;
  query: string;
  domain: string;
  result: AttributionResult;
  top_actor: string;
  top_confidence: number;
  state: AttributionState;
}

const STORAGE_KEY = 'cti.history.v1';
const MAX_ENTRIES = 50;

export function loadHistory(): HistoryEntry[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    return JSON.parse(raw) as HistoryEntry[];
  } catch {
    return [];
  }
}

export function saveToHistory(state: AttributionState): HistoryEntry {
  const entries = loadHistory();
  const top = state.candidate_actors[0];
  const entry: HistoryEntry = {
    id: `q-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    ts: Date.now(),
    query: state.query,
    domain: state.domain,
    result: state.attribution_result,
    top_actor: top?.actor_name ?? '—',
    top_confidence: top?.confidence ?? 0,
    state,
  };

  entries.push(entry);
  while (entries.length > MAX_ENTRIES) {
    entries.shift();
  }

  localStorage.setItem(STORAGE_KEY, JSON.stringify(entries));
  return entry;
}

export function clearHistory(): void {
  localStorage.removeItem(STORAGE_KEY);
}
