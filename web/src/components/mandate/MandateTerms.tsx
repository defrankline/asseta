import type { MandateDto } from '../../api/types';
import { mandateScopeLabel } from '../../session/mandateDisplay';
import { formatDate, formatInstant } from '../../utils/dates';
import { KeyValueGrid, type KeyValueItem } from '../display/KeyValueGrid';
import { StatusChip } from '../display/StatusChip';
import { MANDATE_TONES } from './mandateUi';

/** The terms of a managed-service mandate: who granted what, on whose consent, until when. */
export function MandateTerms({ mandate }: { mandate: MandateDto }) {
  const items: KeyValueItem[] = [
    { label: 'Reference', value: mandate.reference },
    { label: 'Status', value: <StatusChip status={mandate.status} tones={MANDATE_TONES} /> },
    { label: 'Client', value: mandate.tenant_name },
    { label: 'Scope', value: mandateScopeLabel(mandate.scope) },
    { label: 'From', value: formatDate(mandate.starts_on) },
    {
      label: 'Until',
      value: mandate.ends_on === null ? 'Until ended' : formatDate(mandate.ends_on),
    },
    { label: 'Consent reference', value: mandate.consent_reference },
    { label: 'Granted', value: `${mandate.granted_by} · ${formatInstant(mandate.granted_at)}` },
  ];
  if (mandate.notes !== '') items.push({ label: 'Notes', value: mandate.notes });
  if (mandate.closed_at !== null) {
    items.push({
      label: 'Closed',
      value: `${mandate.closed_by ?? '—'} · ${formatInstant(mandate.closed_at)}`,
    });
    items.push({ label: 'Reason', value: mandate.close_reason ?? '—' });
  }
  return <KeyValueGrid columns={3} items={items} />;
}
