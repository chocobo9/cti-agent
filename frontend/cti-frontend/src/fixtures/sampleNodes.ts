import type { NodeRun } from '../components/chat/NodeQueue';

export const sampleNodes: NodeRun[] = [
  { id: 'supervisor', label: 'Supervisor 路由', status: 'done', ms: 240, sub: 'query_type → structural' },
  { id: 'infrastructure', label: 'Infrastructure (Cypher×5)', status: 'done', ms: 1840, sub: '5 templates · 4 success / 1 empty' },
  { id: 'intelligence', label: 'Intelligence (RAG)', status: 'done', ms: 1290, sub: '12 chunks · top 3 RRF > 0.6' },
  { id: 'graph_probe', label: 'Graph 验证', status: 'running', ms: 0, sub: '3 candidate actors validated' },
  { id: 'evidence_eval', label: 'Evidence 评估', status: 'queued', ms: 0, sub: 'confidence = 0.85 · no iter.' },
  { id: 'report', label: 'Report 合成', status: 'queued', ms: 0, sub: 'rendering markdown…' },
];
