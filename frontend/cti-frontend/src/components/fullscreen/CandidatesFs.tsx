import { tokens, fonts } from '../../lib/tokens';
import { ActorRow } from '../shared/ActorRow';
import { NodeEdgeGraph } from './NodeEdgeGraph';
import type { CandidateActor } from '../../types/AttributionState';
import styles from './CandidatesFs.module.css';

export interface CandidatesFsProps {
  actors: CandidateActor[];
}

export function CandidatesFs({ actors }: CandidatesFsProps) {
  return (
    <div className={styles.grid}>
      <div>
        <div className={styles.sectionHead} style={{ color: tokens.textSubtle, fontFamily: fonts.sans }}>
          Candidates ranked by confidence
        </div>
        <div className={styles.actorList}>
          {actors.map((a) => (
            <ActorRow key={a.actor_name} actor={a} defaultOpen />
          ))}
        </div>
      </div>

      <div>
        <div className={styles.sectionHead} style={{ color: tokens.textSubtle, fontFamily: fonts.sans }}>
          Attribution path
        </div>
        <div className={styles.pathPanel} style={{ border: `1px solid ${tokens.border}`, background: tokens.bg }}>
          <NodeEdgeGraph />
          <div className={styles.pathFooter} style={{ color: tokens.textSubtle, borderTop: `1px dashed ${tokens.border}`, fontFamily: fonts.sans }}>
            从 graph_paths 提取的真实路径 ·{' '}
            <span style={{ fontFamily: fonts.mono }}>T2_domain_to_actor</span> +{' '}
            <span style={{ fontFamily: fonts.mono }}>T3_infrastructure_pivot</span>
          </div>
        </div>
      </div>
    </div>
  );
}
