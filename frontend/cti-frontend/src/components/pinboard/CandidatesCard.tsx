import { PinCard } from './PinCard';
import { ActorRow } from '../shared/ActorRow';
import type { CandidateActor } from '../../types/AttributionState';
import styles from './CandidatesCard.module.css';

export interface CandidatesCardProps {
  actors: CandidateActor[];
  onOpen?: () => void;
}

export function CandidatesCard({ actors, onOpen }: CandidatesCardProps) {
  return (
    <PinCard
      testId="pin-card-candidates"
      tag="CANDIDATE ACTORS"
      accent="#7c3aed"
      icon="target"
      title={`${actors.length} ranked`}
      onOpen={onOpen}
    >
      <div className={styles.cardList}>
        {actors.map((a) => (
          <ActorRow key={a.actor_name} actor={a} />
        ))}
      </div>
    </PinCard>
  );
}
