import type { CustomerDto } from '../../../api/types';
import { ACTIVE_RECORD } from '../../../test/lifecycleFixtures';

export const CUSTOMER_ID = 'eeeeeeee-0000-4000-8000-000000000001';

export function makeCustomer(overrides: Partial<CustomerDto> = {}): CustomerDto {
  return {
    id: CUSTOMER_ID,
    code: 'C-01',
    name: 'Acme Roads',
    tax_id: null,
    contact_name: 'Jane',
    contact_phone: '+255700000001',
    contact_email: null,
    payment_terms_days: 30,
    kind: 'REGISTERED',
    ...ACTIVE_RECORD,
    version: 4,
    ...overrides,
  };
}
