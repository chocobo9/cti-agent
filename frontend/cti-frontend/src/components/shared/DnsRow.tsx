import { tokens, fonts } from '../../lib/tokens';
import styles from './DnsRow.module.css';
import type { PassiveDnsRecord, GeoIpRecord } from '../../types/AttributionState';

export interface DnsRowProps {
  record: PassiveDnsRecord;
  geo: GeoIpRecord | undefined;
  live: boolean;
}

export function DnsRow({ record, geo, live }: DnsRowProps) {
  return (
    <div className={styles.row}>
      <div className={styles.ipWrap}>
        <span style={{ fontFamily: fonts.mono, color: tokens.text }}>{record.ip}</span>
        {live && (
          <span
            className={styles.liveBadge}
            style={{ color: tokens.high_confidence.fg, background: tokens.high_confidence.bg }}
          >
            LIVE
          </span>
        )}
      </div>
      <span className={styles.geoText} style={{ color: tokens.textSubtle }}>
        {geo ? `${geo.country}·AS${geo.asn_number}` : '—'}
      </span>
      <span className={styles.dateRange} style={{ fontFamily: fonts.mono, color: tokens.textGhost }}>
        {record.first_seen.slice(5)} → {record.last_seen.slice(5)}
      </span>
    </div>
  );
}
