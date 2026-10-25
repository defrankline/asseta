import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type { AccountabilitySummaryDto } from '../api/custodyTypes';
import { buildTiles } from '../pages/tenant/accountability/accountabilityModel';
import { useBillingChoice } from '../pages/tenant/jobs/useBillingChoice';
import { renderWithProviders } from '../test/renderWithProviders';
import { CAPABILITY } from './capabilities';
import { PERMISSIONS as P } from './permissionCodes';
import { RequireCapability } from './RequireCapability';

function BillingProbe() {
  const choice = useBillingChoice();
  return <p>{choice === null ? 'no billing choice' : 'billing choice'}</p>;
}

const SUMMARY = {
  as_of: '2026-10-21T12:00:00Z',
  policy_version: 'v1',
  hidden_tiles: [],
  unavailable_tiles: [],
  customer_hours: { remaining: '10', activated: '20', consumed: '10' },
  hours_awaiting_activation: { hours: '5' },
  engine_hours: null,
  unexplained_hours: null,
  missing_daily_reports: null,
  investigations: null,
  cash: {
    custodians: [],
    transfers_awaiting_acknowledgement: [],
    floats_awaiting_acknowledgement: [],
    remittances_awaiting_confirmation: [],
    partial_remittances_in_window: 0,
    remittance_cutoff_hour: 18,
    remittances_overdue_today: 3,
  },
  payments: null,
  discrepancies: null,
  unauthorized_attempts: null,
  outstanding_approvals: null,
} as unknown as AccountabilitySummaryDto;

describe('capability gating (G1)', () => {
  it('shows a plain "not enabled" state on a direct URL when the tenant switched it off', () => {
    renderWithProviders(
      <RequireCapability capability={CAPABILITY.customerHours} feature="Customer hours">
        <p>hours page</p>
      </RequireCapability>,
      {
        tenantPermissions: [P.tenantHoursRead],
        disabledCapabilities: [CAPABILITY.customerHours],
      },
    );
    expect(screen.getByText('Customer hours is not enabled for your company')).toBeInTheDocument();
    expect(screen.queryByText('hours page')).not.toBeInTheDocument();
  });

  it('renders the page while the capability is on', () => {
    renderWithProviders(
      <RequireCapability capability={CAPABILITY.customerHours} feature="Customer hours">
        <p>hours page</p>
      </RequireCapability>,
      { tenantPermissions: [P.tenantHoursRead] },
    );
    expect(screen.getByText('hours page')).toBeInTheDocument();
  });

  it('offers no job billing mode when customer hours is switched off', () => {
    renderWithProviders(<BillingProbe />, {
      tenantPermissions: [P.tenantPolicyRead],
      disabledCapabilities: [CAPABILITY.customerHours],
    });
    expect(screen.getByText('no billing choice')).toBeInTheDocument();
  });

  it('drops the customer-hours tiles when switched off and keeps the rest', () => {
    const can = () => true;
    const on = buildTiles(SUMMARY, can).map((t) => t.key);
    const off = buildTiles(SUMMARY, can, { customerHours: false }).map((t) => t.key);
    expect(on).toEqual(expect.arrayContaining(['customer_hours', 'hours_awaiting_activation']));
    expect(off).not.toContain('customer_hours');
    expect(off).not.toContain('hours_awaiting_activation');
    expect(off).toContain('cash_pending');
  });
});

describe('remittance cut-off on the cash tile (G4)', () => {
  it('counts today’s overdue remittances and links to their list when a cut-off is set', () => {
    const pending = buildTiles(SUMMARY, () => true).find((t) => t.key === 'cash_pending');
    const row = pending?.rows?.find((r) => r.key === 'overdue');
    expect(row?.label).toBe('Remittances overdue today (cut-off 18:00)');
    expect(row?.value).toBe(3);
    expect(row?.to).toBe('/tenant/finance/cash/remittance-overdue');
  });

  it('has no overdue row when the tenant set no cut-off', () => {
    const off = {
      ...SUMMARY,
      cash: { ...SUMMARY.cash, remittance_cutoff_hour: null, remittances_overdue_today: null },
    } as AccountabilitySummaryDto;
    const pending = buildTiles(off, () => true).find((t) => t.key === 'cash_pending');
    expect(pending?.rows?.some((r) => r.key === 'overdue')).toBe(false);
  });
});
