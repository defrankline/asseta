import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { formatInstantIn } from '../../../utils/time';
import type { ContractFormValues } from './contractForm';

interface ContractReviewProps {
  values: ContractFormValues;
  customerLabel: string;
  siteLabel: (id: string) => string;
  timeZone: string;
}

/** Review step content for a contract form. */
export function ContractReview({
  values: v,
  customerLabel,
  siteLabel,
  timeZone,
}: ContractReviewProps) {
  return (
    <KeyValueGrid
      columns={2}
      items={[
        { label: 'Customer', value: customerLabel },
        { label: 'Contract number', value: v.contract_number.trim() },
        { label: 'Reference', value: v.reference.trim() || '—' },
        { label: 'Default job site', value: siteLabel(v.job_site_id) },
        { label: 'Starts', value: formatInstantIn(v.starts_on, timeZone) },
        {
          label: 'Ends',
          value: v.ends_on === '' ? 'Open-ended' : formatInstantIn(v.ends_on, timeZone),
        },
        { label: 'Notes', value: v.notes.trim() || '—' },
      ]}
    />
  );
}
