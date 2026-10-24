import type { ContractDto, CustomerDto } from '../../../api/types';
import { ACTIVE_RECORD } from '../../../test/lifecycleFixtures';

export const CUSTOMER_ID = 'eeeeeeee-0000-4000-8000-000000000001';
export const CONTRACT_ID = 'cccccccc-0000-4000-8000-000000000009';

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

export function makeContract(overrides: Partial<ContractDto> = {}): ContractDto {
  return {
    id: CONTRACT_ID,
    customer_id: CUSTOMER_ID,
    contract_number: 'K-7',
    job_site_id: null,
    currency: 'TZS',
    status: 'ACTIVE',
    starts_on: '2026-10-01T00:00:00Z',
    ends_on: null,
    reference: 'PO-1',
    notes: null,
    closed_at: null,
    close_reason: null,
    version: 2,
    ...overrides,
  };
}
