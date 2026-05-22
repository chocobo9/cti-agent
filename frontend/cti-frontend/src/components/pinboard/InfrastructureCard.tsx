import { tokens, fonts } from '../../lib/tokens';
import { PinCard } from './PinCard';
import { DnsRow } from '../shared/DnsRow';
import { CertRow } from '../shared/CertRow';
import { FingerprintBadge } from '../shared/FingerprintBadge';
import type { Enrichment } from '../../types/AttributionState';
import styles from './InfrastructureCard.module.css';

export interface InfrastructureCardProps {
  enrichment: Enrichment;
  onOpen?: () => void;
}

export function InfrastructureCard({ enrichment, onOpen }: InfrastructureCardProps) {
  const e = enrichment;

  return (
    <PinCard
      testId="pin-card-infrastructure"
      tag="INFRASTRUCTURE"
      accent={tokens.accent}
      icon="graph"
      title={`${e.passive_dns.length} resolutions · ${e.certificates.length} certs`}
      onOpen={onOpen}
    >
      <div className={styles.rdapGrid} style={{ borderBottom: `1px dashed ${tokens.border}` }}>
        <KvCell k="Registered" v={e.rdap.creation_date} />
        <KvCell k="Registrar" v={e.rdap.registrar} />
        <KvCell k="Expires" v={e.rdap.expiration_date} />
      </div>

      <div className={styles.dnsSection}>
        <div className={styles.sectionLabel} style={{ color: tokens.textGhost, fontFamily: fonts.sans }}>
          PASSIVE DNS
        </div>
        {e.passive_dns.map((p) => (
          <div key={p.ip} style={{ borderTop: `1px dashed ${tokens.border}` }}>
            <DnsRow record={p} geo={e.geoip.find((x) => x.ip === p.ip)} live={e.current_ips.includes(p.ip)} />
          </div>
        ))}
      </div>

      <div className={styles.certsSection}>
        <div className={styles.sectionLabel} style={{ color: tokens.textGhost, fontFamily: fonts.sans }}>
          CERTIFICATES
        </div>
        {e.certificates.map((c) => (
          <div key={c.fingerprint} style={{ borderTop: `1px dashed ${tokens.border}` }}>
            <CertRow cert={c} />
          </div>
        ))}
      </div>

      <div className={styles.fpSection}>
        <FingerprintBadge label="JARM" value={e.jarm_hash} />
        <FingerprintBadge label="favicon" value={e.favicon_hash} />
      </div>
    </PinCard>
  );
}

function KvCell({ k, v }: { k: string; v: string }) {
  return (
    <div>
      <div className={styles.kvLabel} style={{ color: tokens.textGhost, fontFamily: fonts.sans }}>
        {k.toUpperCase()}
      </div>
      <div className={styles.kvValue} style={{ color: tokens.text, fontFamily: fonts.mono }}>
        {v}
      </div>
    </div>
  );
}
