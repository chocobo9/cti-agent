import { tokens, fonts } from '../../lib/tokens';
import { Icon } from '../shared/Icon';
import { DnsRow } from '../shared/DnsRow';
import type { Enrichment } from '../../types/AttributionState';
import styles from './InfrastructureFs.module.css';

export interface InfrastructureFsProps {
  domain: string;
  enrichment: Enrichment;
}

function KvCell({ k, v, mono }: { k: string; v: string; mono?: boolean }) {
  return (
    <div className={styles.kvCell} style={{ background: tokens.bg, border: `1px solid ${tokens.border}` }}>
      <div className={styles.kvLabel} style={{ color: tokens.textGhost, fontFamily: fonts.sans }}>{k}</div>
      <div className={styles.kvValue} style={{ color: tokens.text, fontFamily: mono ? fonts.mono : fonts.sans }}>{v}</div>
    </div>
  );
}

export function InfrastructureFs({ domain, enrichment: e }: InfrastructureFsProps) {
  const t0 = Math.min(...e.passive_dns.map((p) => +new Date(p.first_seen)));
  const tN = Math.max(...e.passive_dns.map((p) => +new Date(p.last_seen)));
  const span = tN - t0 || 1;
  const lerp = (t: string) => ((+new Date(t)) - t0) / span * 100;

  return (
    <div className={styles.root}>
      <div className={styles.kvGrid}>
        <KvCell k="Domain" v={domain} mono />
        <KvCell k="Registrar" v={e.rdap.registrar} />
        <KvCell k="Registered" v={e.rdap.creation_date} mono />
        <KvCell k="Expires" v={e.rdap.expiration_date} mono />
        <KvCell k="Active IPs" v={`${e.current_ips.length} live · ${e.passive_dns.length} historical`} />
        <KvCell k="Certificates" v={`${e.certificates.length} · Let's Encrypt`} />
      </div>

      <div>
        <SectionHead>Passive DNS timeline</SectionHead>
        <div className={styles.dnsPanel} style={{ border: `1px solid ${tokens.border}`, background: tokens.bg }}>
          {e.passive_dns.map((p, i) => {
            const g = e.geoip.find((x) => x.ip === p.ip);
            const left = lerp(p.first_seen);
            const right = lerp(p.last_seen);
            const live = e.current_ips.includes(p.ip);
            return (
              <div key={p.ip} style={{ borderTop: i === 0 ? 'none' : `1px dashed ${tokens.border}` }}>
                <div className={styles.dnsRow}>
                  <DnsRow record={p} geo={g} live={live} />
                  <div className={styles.timeBar} style={{ background: tokens.divider }}>
                    <div
                      className={styles.timeBarFill}
                      style={{
                        left: `${left}%`,
                        width: `${Math.max(right - left, 2)}%`,
                        background: live ? tokens.status_success : '#a4a8c2',
                      }}
                    />
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div>
        <SectionHead>Certificates</SectionHead>
        <div className={styles.certList}>
          {e.certificates.map((c) => (
            <div key={c.fingerprint} className={styles.certCard} style={{ border: `1px solid ${tokens.border}` }}>
              <div>
                <div className={styles.certLabel} style={{ color: tokens.textGhost, fontFamily: fonts.sans }}>FINGERPRINT</div>
                <div className={styles.certValue} style={{ fontFamily: fonts.mono, color: tokens.text }}>{c.fingerprint}</div>
              </div>
              <div>
                <div className={styles.certLabel} style={{ color: tokens.textGhost, fontFamily: fonts.sans }}>SAN</div>
                <div className={styles.certSanValue} style={{ fontFamily: fonts.mono, color: tokens.textMute }}>{c.san_list.join('  ·  ')}</div>
              </div>
              <div>
                <div className={styles.certLabel} style={{ color: tokens.textGhost, fontFamily: fonts.sans }}>VALIDITY</div>
                <div className={styles.certSanValue} style={{ fontFamily: fonts.mono, color: tokens.textMute }}>{c.not_before} → {c.not_after}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div>
        <SectionHead>Fingerprints</SectionHead>
        <div className={styles.fpRow}>
          <FingerprintBig label="JARM" value={e.jarm_hash} hint="TLS handshake hash · pivot on identical clients" />
          <FingerprintBig label="favicon" value={e.favicon_hash} hint="mmh3 of favicon · pivot on identical UIs" />
        </div>
      </div>
    </div>
  );
}

function SectionHead({ children }: { children: React.ReactNode }) {
  return (
    <div className={styles.sectionHead} style={{ color: tokens.textSubtle, fontFamily: fonts.sans }}>
      {children}
    </div>
  );
}

function FingerprintBig({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div className={styles.fpCard} style={{ border: `1px solid ${tokens.border}`, background: tokens.bg }}>
      <div className={styles.fpHeader}>
        <Icon name="fingerprint" size={13} color={tokens.textSubtle} />
        <span className={styles.fpLabel} style={{ color: tokens.textSubtle, fontFamily: fonts.sans }}>{label}</span>
        <button className={styles.fpCopyBtn} style={{ color: tokens.textGhost }} title="Copy">
          <Icon name="copy" size={12} />
        </button>
      </div>
      <div className={styles.fpValue} style={{ fontFamily: fonts.mono, color: tokens.text }}>{value}</div>
      <div className={styles.fpHint} style={{ color: tokens.textGhost, fontFamily: fonts.sans }}>{hint}</div>
    </div>
  );
}
