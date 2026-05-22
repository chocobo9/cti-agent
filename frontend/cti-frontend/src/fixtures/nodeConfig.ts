export const NODE_IDS = ['supervisor', 'infrastructure', 'intelligence', 'graph_probe', 'evidence_eval', 'report'];

export const NODE_LABELS: Record<string, string> = {
  supervisor: 'Supervisor 路由',
  infrastructure: 'Infrastructure (Cypher×5)',
  intelligence: 'Intelligence (RAG)',
  graph_probe: 'Graph 验证',
  evidence_eval: 'Evidence 评估',
  report: 'Report 合成',
};

export const NODE_SUBS: Record<string, string> = {
  supervisor: 'query_type → structural',
  infrastructure: '5 templates · 4 success / 1 empty',
  intelligence: '12 chunks · top 3 RRF > 0.6',
  graph_probe: '3 candidate actors validated',
  evidence_eval: 'confidence = 0.85 · no iter.',
  report: 'rendering markdown…',
};
