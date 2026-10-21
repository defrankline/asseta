import type { ContractStatus } from '../../../api/types';
import type { StatusTone } from '../../../components/display/StatusChip';

export const CUSTOMER_ERROR_HINTS: Readonly<Record<string, string>> = {
  CUSTOMER_HAS_OPEN_JOBS: 'Complete or cancel this customer’s open jobs first.',
  ALREADY_INACTIVE: 'The customer is already inactive; reload to see the latest state.',
  ALREADY_ACTIVE: 'The customer is already active; reload to see the latest state.',
  DUPLICATE_CODE: 'Another customer already uses this code.',
};

export const CONTRACT_ERROR_HINTS: Readonly<Record<string, string>> = {
  CONTRACT_HAS_OPEN_JOBS: 'Complete or cancel the open jobs under this contract first.',
  CONTRACT_CLOSED: 'A closed contract cannot be edited; reopen it first.',
  CONTRACT_DATES: 'The end must be after the start.',
  CUSTOMER_INACTIVE: 'Reactivate the customer before reopening its contracts.',
  ALREADY_INACTIVE: 'The contract is already closed; reload to see the latest state.',
  ALREADY_ACTIVE: 'The contract is already open; reload to see the latest state.',
};

export const CONTRACT_TONES: Readonly<Record<ContractStatus, StatusTone>> = {
  DRAFT: 'info',
  ACTIVE: 'success',
  CLOSED: 'default',
};

export const CUSTOMER_DEACTIVATE_CONSEQUENCES =
  'No new contracts or jobs can be created for it. Its balance and statement stay available.';

export const CONTRACT_CLOSE_CONSEQUENCES =
  'No new jobs can be booked under it. Existing jobs, readings and invoices are kept.';
