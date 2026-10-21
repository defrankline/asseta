import type { ContractDto } from '../../../api/types';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { StatusChip } from '../../../components/display/StatusChip';
import { ActionButtons } from '../../../components/lifecycle/ActionButtons';
import { DetailsDrawer } from '../../../components/lifecycle/DetailsDrawer';
import type { RowAction } from '../../../components/lifecycle/rowActions';
import { formatInstantIn } from '../../../utils/time';
import { CONTRACT_TONES } from './customerLifecycle';

interface ContractDetailsDrawerProps {
  contract: ContractDto;
  customerLabel: string;
  siteLabel: (id: string | null) => string;
  timeZone: string;
  actions: readonly RowAction[];
  onClose: () => void;
}

/** Every field of a contract, including why and when it was closed. */
export function ContractDetailsDrawer({
  contract: c,
  customerLabel,
  siteLabel,
  timeZone,
  actions,
  onClose,
}: ContractDetailsDrawerProps) {
  return (
    <DetailsDrawer
      title={`Contract ${c.contract_number}`}
      status={<StatusChip status={c.status} tones={CONTRACT_TONES} />}
      actions={<ActionButtons actions={actions} />}
      onClose={onClose}
    >
      <KeyValueGrid
        columns={2}
        items={[
          { label: 'Customer', value: customerLabel },
          { label: 'Contract number', value: c.contract_number },
          { label: 'Reference', value: c.reference ?? '—' },
          { label: 'Currency', value: c.currency },
          { label: 'Default job site', value: siteLabel(c.job_site_id) },
          { label: 'Starts', value: formatInstantIn(c.starts_on, timeZone) },
          {
            label: 'Ends',
            value: c.ends_on === null ? 'Open-ended' : formatInstantIn(c.ends_on, timeZone),
          },
          { label: 'Notes', value: c.notes ?? '—' },
          {
            label: 'Closed',
            value: c.closed_at == null ? '—' : formatInstantIn(c.closed_at, timeZone),
          },
          { label: 'Close reason', value: c.close_reason ?? '—' },
          { label: 'Version', value: String(c.version) },
        ]}
      />
    </DetailsDrawer>
  );
}
