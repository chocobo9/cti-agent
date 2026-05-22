import { tokens, fonts } from '../../lib/tokens';
import styles from './NodeEdgeGraph.module.css';

interface GraphNode {
  id: string;
  x: number;
  y: number;
  r: number;
  label: string;
  kind: string;
  mono?: boolean;
}

interface GraphEdge {
  a: string;
  b: string;
  label: string;
}

const NODES: GraphNode[] = [
  { id: 'd', x: 80, y: 180, r: 30, label: 'hamadryas.online', kind: 'domain', mono: true },
  { id: 'c', x: 240, y: 180, r: 22, label: 'tag-xyz', kind: 'cluster' },
  { id: 'a', x: 410, y: 180, r: 28, label: 'TA-577', kind: 'actor' },
  { id: 's1', x: 240, y: 60, r: 16, label: 'sibling-a.online', kind: 'sibling', mono: true },
  { id: 's2', x: 320, y: 30, r: 14, label: 'sibling-b.com', kind: 'sibling', mono: true },
  { id: 's3', x: 160, y: 50, r: 14, label: 'sibling-c.shop', kind: 'sibling', mono: true },
  { id: 'i1', x: 80, y: 310, r: 16, label: '185.244.42.91', kind: 'ip', mono: true },
  { id: 'i2', x: 160, y: 340, r: 14, label: '91.219.236.18', kind: 'ip', mono: true },
  { id: 'cam', x: 530, y: 80, r: 18, label: 'Storm-1811', kind: 'campaign' },
];

const EDGES: GraphEdge[] = [
  { a: 'd', b: 'c', label: 'in_cluster' },
  { a: 'c', b: 'a', label: 'attributed_to' },
  { a: 'c', b: 's1', label: 'sibling' },
  { a: 'c', b: 's2', label: 'sibling' },
  { a: 'c', b: 's3', label: 'sibling' },
  { a: 'd', b: 'i1', label: 'resolves_to' },
  { a: 'd', b: 'i2', label: 'resolves_to' },
  { a: 'a', b: 'cam', label: 'runs_campaign' },
];

function kindColor(kind: string): string {
  const map: Record<string, string> = {
    domain: tokens.text,
    cluster: '#a4a8c2',
    actor: tokens.accent,
    sibling: '#9ca0b0',
    ip: tokens.status_success,
    campaign: tokens.medium_confidence.dot,
  };
  return map[kind] ?? tokens.textSubtle;
}

const nodeMap = Object.fromEntries(NODES.map((n) => [n.id, n]));

export function NodeEdgeGraph() {
  return (
    <svg data-testid="node-edge-graph" viewBox="0 0 590 380" className={styles.svg}>
      <defs>
        <marker id="grarrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" markerHeight="6" orient="auto">
          <path d="M0,0 L8,4 L0,8 z" fill="#9ca0b0" />
        </marker>
      </defs>

      {EDGES.map((e, i) => {
        const a = nodeMap[e.a];
        const b = nodeMap[e.b];
        const isDashed = e.label === 'sibling' || e.label === 'resolves_to';
        return (
          <line
            key={i}
            x1={a.x}
            y1={a.y}
            x2={b.x}
            y2={b.y}
            stroke="#cdd1de"
            strokeWidth="1.2"
            strokeDasharray={isDashed ? '3 4' : 'none'}
            markerEnd={isDashed ? undefined : 'url(#grarrow)'}
          />
        );
      })}

      {NODES.map((n) => (
        <g key={n.id}>
          <circle
            cx={n.x}
            cy={n.y}
            r={n.r}
            fill="#fff"
            stroke={kindColor(n.kind)}
            strokeWidth={n.kind === 'domain' || n.kind === 'actor' ? 2 : 1.4}
          />
          <text
            x={n.x}
            y={n.y + 4}
            textAnchor="middle"
            fontSize={n.kind === 'domain' || n.kind === 'actor' ? 10.5 : 9}
            fontFamily={n.mono ? fonts.mono : fonts.sans}
            fontWeight={n.kind === 'domain' || n.kind === 'actor' ? 600 : 500}
            fill={kindColor(n.kind)}
          >
            {n.label.length > 14 ? n.label.slice(0, 12) + '...' : n.label}
          </text>
        </g>
      ))}

      {/* Legend */}
      <g transform="translate(10, 360)">
        {([
          ['domain', tokens.text],
          ['cluster', '#a4a8c2'],
          ['actor', tokens.accent],
          ['ip', tokens.status_success],
          ['sibling', '#9ca0b0'],
        ] as const).map(([label, color], i) => (
          <g key={label} transform={`translate(${i * 92}, 0)`}>
            <circle cx="5" cy="6" r="4" fill="#fff" stroke={color} strokeWidth="1.2" />
            <text x="14" y="9" fontSize="9.5" fill={tokens.textSubtle} fontFamily={fonts.sans}>
              {label}
            </text>
          </g>
        ))}
      </g>
    </svg>
  );
}
