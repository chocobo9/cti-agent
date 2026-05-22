import { useState, useCallback } from 'react';
import { tokens, fonts } from '../lib/tokens';
import { Rail } from '../components/rail/Rail';
import { Topbar } from '../components/topbar/Topbar';
import { ChatColumn } from '../components/chat/ChatColumn';
import { Pinboard } from '../components/pinboard/Pinboard';
import { FullscreenModal } from '../components/fullscreen/FullscreenModal';
import { AttributionFs } from '../components/fullscreen/AttributionFs';
import { CandidatesFs } from '../components/fullscreen/CandidatesFs';
import { InfrastructureFs } from '../components/fullscreen/InfrastructureFs';
import { EvidenceFs } from '../components/fullscreen/EvidenceFs';
import type { AttributionState } from '../types/AttributionState';
import type { NodeRun } from '../components/chat/NodeQueue';
import styles from './QueryWorkspace.module.css';

interface PreviousTurnData {
  query: string;
  state: AttributionState | null;
}

export interface QueryWorkspaceProps {
  state: AttributionState;
  nodes: NodeRun[];
  children?: React.ReactNode;
  previousTurns?: PreviousTurnData[];
  onSend?: (text: string) => void;
}

const MODAL_TITLES: Record<string, string> = {
  attribution: 'Attribution result · full detail',
  candidates: 'Candidate actors · ranked evidence',
  infrastructure: 'Infrastructure · resolutions, certs, fingerprints',
  evidence: 'Evidence chain · sources & reasoning',
};

export function QueryWorkspace({ state, nodes, children, previousTurns, onSend }: QueryWorkspaceProps) {
  const [activeModal, setActiveModal] = useState<string | null>(null);
  const closeModal = useCallback(() => setActiveModal(null), []);

  return (
    <div
      className={styles.workspace}
      style={{ background: tokens.bg, color: tokens.text, fontFamily: fonts.sans }}
    >
      <Rail />

      <main className={styles.main}>
        <Topbar state={state} />

        <div className={styles.body}>
          <ChatColumn state={state} nodes={nodes} onSend={onSend} previousTurns={previousTurns}>
            {children}
          </ChatColumn>

          <Pinboard state={state} onOpenCard={setActiveModal} />
        </div>
      </main>

      {activeModal && (
        <FullscreenModal title={MODAL_TITLES[activeModal] ?? ''} onClose={closeModal}>
          {activeModal === 'attribution' && <AttributionFs state={state} />}
          {activeModal === 'candidates' && <CandidatesFs actors={state.candidate_actors} />}
          {activeModal === 'infrastructure' && <InfrastructureFs domain={state.domain} enrichment={state.enrichment} />}
          {activeModal === 'evidence' && <EvidenceFs state={state} />}
        </FullscreenModal>
      )}
    </div>
  );
}
