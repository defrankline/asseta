import type { ReactNode } from 'react';
import type { OverdueReason, RemittanceOverdueDto } from '../../../../api/custodyTypes';
import type { KeyValueItem } from '../../../../components/display/KeyValueGrid';
import { MoneyText } from '../../../../components/display/MoneyText';
import { formatDate } from '../../../../utils/dates';
import { formatDateIn, formatInstantIn } from '../../../../utils/time';
import { nameOr } from '../../shared/names';
import type { HistoryEvent } from '../../shared/RecordDetail';

export const overdueCustodian = (o: RemittanceOverdueDto) =>
  nameOr(o.staff_member_name, o.staff_member_id);

/** `HH:00` of the tenant-local cut-off hour in effect when the flag was raised. */
export const cutoffText = (hour: number) => `${String(hour).padStart(2, '0')}:00`;

/** Why the custodian was flagged: the daily cut-off, or holding cash past their allowance (DEC-031 D3). */
export const OVERDUE_REASON_LABELS: Readonly<Record<OverdueReason, string>> = {
  CUTOFF: 'Not remitted by the cut-off',
  HELD_TOO_LONG: 'Held longer than allowed',
};

export const OVERDUE_REASON_OPTIONS: readonly { value: OverdueReason; label: string }[] = [
  { value: 'CUTOFF', label: OVERDUE_REASON_LABELS.CUTOFF },
  { value: 'HELD_TOO_LONG', label: OVERDUE_REASON_LABELS.HELD_TOO_LONG },
];

const allowanceText = (days: number | null | undefined) =>
  days == null ? null : `${String(days)} day${days === 1 ? '' : 's'}`;

/** "Held longer than allowed since 21 Oct 2026" or "Not remitted by the 18:00 cut-off". */
export function overdueReasonText(o: RemittanceOverdueDto, timeZone: string): string {
  if (o.reason === 'HELD_TOO_LONG') {
    return o.held_since == null
      ? OVERDUE_REASON_LABELS.HELD_TOO_LONG
      : `Held longer than allowed since ${formatDateIn(o.held_since, timeZone)}`;
  }
  return `Not remitted by the ${cutoffText(o.cutoff_hour)} cut-off`;
}

/** The unremitted amounts, one per currency (never summed across currencies). */
export function overdueAmounts(o: RemittanceOverdueDto): ReactNode {
  if (o.amounts.length === 0) return '—';
  return (
    <span className="inline-flex flex-col items-end">
      {o.amounts.map((a) => (
        <MoneyText key={a.currency} amount={a.amount} currency={a.currency} />
      ))}
    </span>
  );
}

export function overdueItems(o: RemittanceOverdueDto, timeZone: string): KeyValueItem[] {
  // cutoff_hour is the flagging hour on a holding-allowance flag, never shown as a cut-off there.
  const why: KeyValueItem[] =
    o.reason === 'HELD_TOO_LONG'
      ? [
          { label: 'Held since', value: formatInstantIn(o.held_since, timeZone) },
          { label: 'Allowed holding', value: allowanceText(o.max_holding_days) ?? '—' },
        ]
      : [{ label: 'Cut-off', value: cutoffText(o.cutoff_hour) }];
  return [
    { label: 'Custodian', value: overdueCustodian(o) },
    { label: 'Reason', value: overdueReasonText(o, timeZone) },
    { label: 'Day', value: formatDate(o.local_day) },
    ...why,
    { label: 'Cash still held', value: overdueAmounts(o) },
    { label: 'Flagged', value: formatInstantIn(o.flagged_at, timeZone) },
    { label: 'Policy version', value: o.policy_version },
  ];
}

export function overdueHistory(o: RemittanceOverdueDto, timeZone: string): HistoryEvent[] {
  const allowance = allowanceText(o.max_holding_days);
  return [
    ...(o.reason === 'HELD_TOO_LONG' && o.held_since != null
      ? [
          {
            key: 'held',
            at: o.held_since,
            label: 'Oldest unremitted cash received',
          },
        ]
      : []),
    {
      key: 'flagged',
      at: o.flagged_at,
      label:
        o.reason === 'HELD_TOO_LONG'
          ? `${overdueReasonText(o, timeZone)}${allowance === null ? '' : ` (allowed ${allowance})`}`
          : `Still holding cash after the ${cutoffText(o.cutoff_hour)} cut-off`,
      by: o.reason === 'HELD_TOO_LONG' ? 'Cash holding check' : 'Daily remittance check',
    },
  ];
}
