import type { EnrollmentDto, InvoiceDto, PaymentDto } from '../api/types';

export const INVOICE_ID = '66666666-6666-4666-8666-666666666666';
export const SUB_ID = '77777777-7777-4777-8777-777777777777';

export function makeInvoice(overrides: Partial<InvoiceDto> = {}): InvoiceDto & { id: string } {
  const invoice: InvoiceDto = {
    id: INVOICE_ID,
    invoice_number: 'INV-2026-0001',
    tenant_id: '11111111-1111-4111-8111-111111111111',
    status: 'ISSUED',
    period_start: '2026-10-01',
    period_end: '2026-10-31',
    due_date: '2026-10-15',
    issued_at: '2026-10-01T00:00:00Z',
    currency: 'TZS',
    enrolled_assets: 3,
    billable_assets: 3,
    subtotal: '300000.0000',
    discount_total: '0.0000',
    tax_total: '54000.0000',
    total: '354000.0000',
    amount_paid: '0.0000',
    credits_applied: '0.0000',
    balance: '354000.0000',
    lines: [],
    ...overrides,
  };
  return { ...invoice, id: invoice.id ?? INVOICE_ID };
}

export function makePayment(overrides: Partial<PaymentDto> = {}): PaymentDto {
  return {
    id: '88888888-8888-4888-8888-888888888888',
    invoice_id: INVOICE_ID,
    tenant_id: '11111111-1111-4111-8111-111111111111',
    amount: '100000.0000',
    currency: 'TZS',
    method: 'BANK_TRANSFER',
    reference: 'CRDB-001',
    received_on: '2026-10-10',
    status: 'RECORDED',
    recorded_at: '2026-10-10T09:00:00Z',
    decided_at: null,
    decision_note: null,
    ...overrides,
  };
}

export const ENROLLMENT: EnrollmentDto = {
  id: '99999999-9999-4999-8999-999999999999',
  machine_id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
  asset_label: 'EX-01 Excavator',
  effective_from: '2026-09-01',
  effective_to: null,
  end_reason: null,
};
