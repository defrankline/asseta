import type { ReactNode } from 'react';
import type { RemittanceOverdueDto } from '../../../../api/custodyTypes';
import type { KeyValueItem } from '../../../../components/display/KeyValueGrid';
import { MoneyText } from '../../../../components/display/MoneyText';
import { formatDate } from '../../../../utils/dates';
import { formatInstantIn } from '../../../../utils/time';
import { nameOr } from '../../shared/names';
import type { HistoryEvent } from '../../shared/RecordDetail';

export const overdueCustodian = (o: RemittanceOverdueDto) =>
  nameOr(o.staff_member_name, o.staff_member_id);

/** `HH:00` of the tenant-local cut-off hour in effect when the flag was raised. */
export const cutoffText = (hour: number) => `${String(hour).padStart(2, '0')}:00`;

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
  return [
    { label: 'Custodian', value: overdueCustodian(o) },
    { label: 'Day', value: formatDate(o.local_day) },
    { label: 'Cut-off', value: cutoffText(o.cutoff_hour) },
    { label: 'Cash still held', value: overdueAmounts(o) },
    { label: 'Flagged', value: formatInstantIn(o.flagged_at, timeZone) },
    { label: 'Policy version', value: o.policy_version },
  ];
}

export function overdueHistory(o: RemittanceOverdueDto): HistoryEvent[] {
  return [
    {
      key: 'flagged',
      at: o.flagged_at,
      label: `Still holding cash after the ${cutoffText(o.cutoff_hour)} cut-off`,
      by: 'Daily remittance check',
    },
  ];
}
