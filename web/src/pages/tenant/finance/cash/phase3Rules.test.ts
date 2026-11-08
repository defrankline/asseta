import { describe, expect, it } from 'vitest';
import { varianceSchema } from '../../../../api/services/custodySchemas';
import { handoverSchema } from '../../../../api/services/financeSchemas';
import { fieldCollectionSchemaFor } from '../../field/fieldCash';
import { paymentFormSchemaFor } from '../payments/paymentForm';
import { withPolicyErrorCode } from '../../policies/policyErrors';
import { ApiError } from '../../../../api/ApiError';
import { makeHandover } from '../../../../test/financeFixtures';
import { isPartialRemittance } from './cashForms';
import type { CashCustodyBalanceDto } from '../../../../api/types';

const BALANCE: CashCustodyBalanceDto = {
  staff_member_id: 's1',
  currency: 'TZS',
  outstanding: '100000.0000',
  claimed_unverified_handovers: '10000.0000',
  pending_spending: '0',
  in_transit_out: '5000.0000',
  in_transit_in: '0',
  pending_floats: '0',
  approved_retention: '5000.0000',
  as_of: '2026-10-21T10:00:00Z',
};

describe('partial remittance', () => {
  it('is short only when cash is left over after what is accounted for', () => {
    expect(isPartialRemittance(BALANCE, '80000')).toBe(false);
    expect(isPartialRemittance(BALANCE, '79999')).toBe(true);
    expect(isPartialRemittance(BALANCE, 'not-a-number')).toBe(false);
  });
});

describe('collection link policy', () => {
  const field = {
    job_id: '',
    customer_id: 'c1',
    staff_member_id: '',
    amount: '100',
    currency: '',
    reference: '',
    received_at: '2026-10-21T10:00:00.000Z',
    note: '',
    purchase_id: '',
    invoice_id: '',
  };

  it('needs a purchase or an invoice on a field collection when the policy is on', () => {
    expect(fieldCollectionSchemaFor(false).isValidSync(field)).toBe(true);
    expect(fieldCollectionSchemaFor(true).isValidSync(field)).toBe(false);
    expect(fieldCollectionSchemaFor(true).isValidSync({ ...field, purchase_id: 'p1' })).toBe(true);
    expect(fieldCollectionSchemaFor(true).isValidSync({ ...field, invoice_id: 'i1' })).toBe(true);
  });

  it('needs a link on an office collection when the policy is on', () => {
    const v = {
      customer_id: 'c1',
      method: 'CASH',
      amount: '100',
      currency: '',
      reference: '',
      received_at: '2026-10-21T10:00:00.000Z',
      received_by_staff_id: '',
      note: '',
      allocations: [],
      purchase_id: '',
    };
    expect(paymentFormSchemaFor(false).isValidSync(v)).toBe(true);
    expect(paymentFormSchemaFor(true).isValidSync(v)).toBe(false);
    expect(paymentFormSchemaFor(true).isValidSync({ ...v, purchase_id: 'p1' })).toBe(true);
  });
});

describe('Phase 3 response schemas', () => {
  it('reads the remittance evidence status and defaults older records', () => {
    const parsed = handoverSchema.validateSync({
      ...makeHandover(),
      remittance_number: 'RMT-2026-000001',
      evidence_status: 'SUPPORTED',
      evidence_attachment_ids: [],
    });
    expect(parsed.evidence_status).toBe('SUPPORTED');
    expect(handoverSchema.validateSync(makeHandover()).evidence_status).toBeNull();
    expect(() =>
      handoverSchema.validateSync({ ...makeHandover(), evidence_status: 'DONE' }),
    ).toThrow();
  });

  it('reads a customer-hour variance', () => {
    const parsed = varianceSchema.validateSync({
      id: 'v1',
      source_type: 'CUSTOMER_HOUR',
      source_id: 's1',
      staff_member_id: null,
      counterparty_staff_id: null,
      currency: 'TZS',
      declared_amount: '1',
      received_amount: '2',
      amount: '-1',
      case_id: null,
      opened_at: '2026-10-21T10:00:00Z',
      opened_by: null,
      status: 'CLOSURE_PROPOSED',
      reason_id: null,
      proposed_by: null,
      proposed_at: null,
      proposal_note: null,
      outcome: null,
      resolved_by: null,
      resolved_at: null,
      resolution_note: null,
      unit: 'HOURS',
    });
    expect(parsed.unit).toBe('HOURS');
    expect(parsed.assignee_user_id).toBeNull();
  });
});

describe('managed-service switch refusals', () => {
  const refused = (code: string) =>
    withPolicyErrorCode(
      new ApiError({
        status: 422,
        code,
        message: 'raw',
        correlationId: null,
        details: [],
      }),
    ).message;

  it('explains both refusals in plain words', () => {
    expect(refused('MANAGED_SERVICE_MANDATE_ACTIVE')).toContain('mandate is open');
    expect(refused('MANAGED_SERVICE_SWITCH_LOCKED')).toContain('cannot change this switch');
  });
});
