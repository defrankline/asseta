import { Box, Link } from '@mui/material';
import { Link as RouterLink } from 'react-router';
import type { CustomerPaymentDto } from '../../../../api/types';
import { type KeyValueItem } from '../../../../components/display/KeyValueGrid';
import { MoneyText } from '../../../../components/display/MoneyText';
import { hoursPurchasePath } from '../../../../navigation/hoursRoutes';
import { formatInstantIn } from '../../../../utils/time';
import { PAYMENT_METHOD_LABELS } from '../../shared/financeDisplay';
import { PersonName } from '../../shared/PersonName';
import { unallocatedOf } from './paymentForm';
import { VerificationText } from './PaymentParts';
import { waitsForHandover } from './paymentVerification';

/** The hours purchases a collection pays for (linked up to their open amounts). */
function purchaseLinkItems(p: CustomerPaymentDto) {
  const links = p.purchase_links ?? [];
  if (links.length === 0) return [];
  return [
    {
      label: 'Pays for',
      value: (
        <Box component="span" className="inline-flex flex-wrap gap-2">
          {links.map((l) => (
            <Link key={l.purchase_id} component={RouterLink} to={hoursPurchasePath(l.purchase_id)}>
              {l.purchase_number}
            </Link>
          ))}
        </Box>
      ),
    },
  ];
}

function verificationItems(p: CustomerPaymentDto): KeyValueItem[] {
  if (p.verified_automatically == null && !waitsForHandover(p)) return [];
  return [{ label: 'Verification', value: <VerificationText payment={p} /> }];
}

/** The fields of one payment, shared by its drawer and its own page. */
export function paymentItems(
  p: CustomerPaymentDto,
  timeZone: string,
  customerLabel: (id: string) => string,
  staffLabel: (id: string | null) => string,
): KeyValueItem[] {
  return [
    { label: 'Customer', value: p.customer_name ?? customerLabel(p.customer_id) },
    { label: 'Amount', value: <MoneyText amount={p.amount} currency={p.currency} strong /> },
    {
      label: 'Unallocated',
      value: <MoneyText amount={unallocatedOf(p)} currency={p.currency} />,
    },
    { label: 'Method', value: PAYMENT_METHOD_LABELS[p.method] },
    { label: 'Number', value: p.collection_number ?? '—' },
    { label: 'Reference', value: p.reference ?? '—' },
    ...purchaseLinkItems(p),
    { label: 'Received at', value: formatInstantIn(p.received_at, timeZone) },
    { label: 'Received by', value: p.received_by_staff_name ?? staffLabel(p.received_by_staff_id) },
    { label: 'Source', value: p.source },
    {
      label: 'Recorded by',
      value: <PersonName userId={p.recorded_by} name={p.recorded_by_name} />,
    },
    { label: 'Recorded at', value: formatInstantIn(p.recorded_at, timeZone) },
    ...verificationItems(p),
    {
      label: 'Decided by',
      value: (
        <PersonName
          userId={p.verified_by ?? null}
          name={p.verified_by_name}
          empty={p.verified_automatically == null ? '—' : 'Verified automatically'}
        />
      ),
    },
    {
      label: 'Decided at',
      value: p.verified_at == null ? '—' : formatInstantIn(p.verified_at, timeZone),
    },
    { label: 'Decision note', value: p.decision_note ?? '—' },
    { label: 'Note', value: p.note ?? '—' },
  ];
}
