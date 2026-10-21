import { describe, expect, it } from 'vitest';
import { makeInvoice, makePayment } from '../../test/billingFixtures';
import { parseResponse } from '../validation';
import {
  chargePreviewSchema,
  dashboardSchema,
  enrollmentResultSchema,
  invoiceSchema,
  pageSchema,
  paymentSchema,
  subscriptionSchema,
} from './billingSchemas';

const rate = {
  id: 'r1',
  version: 2,
  currency: 'TZS',
  cadence: 'YEARLY',
  unit_price: '120000.0000',
  minimum_billable_assets: 1,
  discount_percent: '0.0000',
  tax_name: null,
  tax_rate_percent: '18.0000',
  mid_cycle_add: 'PRORATE_DAILY',
  mid_cycle_remove: 'NO_CREDIT',
  rounding_mode: 'HALF_EVEN',
  effective_from: '2026-10-01',
  reason: 'Renewal',
  created_at: '2026-09-30T10:00:00Z',
};
const subscription = {
  id: 's1',
  tenant_id: 't1',
  agreement_id: 'a1',
  agreement_number: 'AGR-1',
  status: 'PENDING_ACTIVATION',
  start_date: '2026-10-01',
  billing_start_date: '2026-10-01',
  billing_anchor_day: 1,
  payment_terms_days: 14,
  current_period_start: null,
  current_period_end: null,
  cancellation_effective_date: null,
  manually_suspended: false,
  enrolled_assets: 0,
  billable_assets: 1,
  current_rate: null,
};

describe('billing response schemas', () => {
  it('accept contract payloads with nullable fields', () => {
    expect(parseResponse(subscriptionSchema, subscription, 's').current_rate).toBeNull();
    expect(
      parseResponse(subscriptionSchema, { ...subscription, current_rate: rate }, 's').current_rate
        ?.version,
    ).toBe(2);
    const preview = {
      ...makeInvoice(),
      id: null,
      invoice_number: null,
      status: null,
      issued_at: null,
    };
    expect(parseResponse(invoiceSchema, preview, 'i').status).toBeNull();
    expect(
      parseResponse(
        pageSchema(paymentSchema),
        { items: [makePayment()], total: 1, page: 1, page_size: 25 },
        'p',
      ).total,
    ).toBe(1);
    const enrollment = {
      id: 'e',
      machine_id: 'm',
      asset_label: 'EX',
      effective_from: '2026-09-01',
      effective_to: null,
      end_reason: null,
    };
    expect(
      parseResponse(enrollmentResultSchema, { enrollment, charge: null }, 'r').charge,
    ).toBeNull();
    expect(
      parseResponse(
        dashboardSchema,
        {
          as_of: '2026-10-21',
          tenants_by_status: {},
          tenants_by_access: { FULL: 1 },
          subscriptions_by_status: {},
          by_currency: [],
          churn_events_30d: 0,
        },
        'd',
      ).tenants_by_access,
    ).toEqual({ FULL: 1 });
  });

  it('reject drifted payloads as contract mismatches', () => {
    expect(() =>
      parseResponse(subscriptionSchema, { ...subscription, status: 'ON_HOLD' }, 's'),
    ).toThrow(/unexpected/);
    expect(() => parseResponse(chargePreviewSchema, { amount: '1' }, 'c')).toThrow(/unexpected/);
    expect(() =>
      parseResponse(
        dashboardSchema,
        {
          as_of: 'x',
          tenants_by_status: { A: 'one' },
          tenants_by_access: {},
          subscriptions_by_status: {},
          by_currency: [],
          churn_events_30d: 0,
        },
        'd',
      ),
    ).toThrow(/unexpected/);
  });
});
