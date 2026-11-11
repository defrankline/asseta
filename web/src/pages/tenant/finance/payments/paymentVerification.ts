import type { CustomerPaymentDto } from '../../../../api/types';

/** Cash of an hours sale the tenant verifies when the custodian's handover is confirmed. */
export const VERIFIES_ON_HANDOVER_TEXT = 'Verified when the cash handover is confirmed';

/** True when no one verifies this payment by hand: it waits for the cash handover. */
export const waitsForHandover = (p: CustomerPaymentDto): boolean =>
  p.verifies_on_handover && p.status === 'CLAIMED';
