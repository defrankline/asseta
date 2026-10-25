import { screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { AccountabilitySummaryDto } from '../api/custodyTypes';
import { notificationTargetPath } from '../notifications/center/display';
import { buildTiles } from '../pages/tenant/accountability/accountabilityModel';
import { tileOfDisabledCapability } from '../pages/tenant/accountability/tileCapabilities';
import { FieldCashPage } from '../pages/tenant/field/FieldCashPage';
import { FieldReadingsPage } from '../pages/tenant/field/FieldReadingsPage';
import { CashCustodyPage } from '../pages/tenant/finance/cash/CashCustodyPage';
import { FloatsTab } from '../pages/tenant/finance/cash/FloatsTab';
import { toRemittanceDecisionPayload } from '../pages/tenant/finance/cash/custodyForms';
import { FormulaCard } from '../pages/tenant/finance/cash/ReconciliationTab';
import { remittanceItems } from '../pages/tenant/finance/cash/remittanceRecord';
import { makeDay, makeHandover } from '../test/financeFixtures';
import { renderWithProviders } from '../test/renderWithProviders';
import { CAPABILITY } from './capabilities';
import { PERMISSIONS as P } from './permissionCodes';
import { RequireCapability } from './RequireCapability';

const empty = { items: [], total: 0, page: 1, page_size: 25 };
const svc = vi.hoisted(() => ({
  emptyPage: vi.fn(),
  emptyList: vi.fn(),
  refuse: vi.fn(),
}));
vi.mock('../api/services/cashService', () => ({
  cashService: {
    supervisorSummary: svc.emptyList,
    myCustody: svc.emptyList,
    myReconciliation: svc.emptyList,
    myCollections: svc.emptyPage,
    myHandovers: svc.emptyPage,
  },
}));
vi.mock('../api/services/custodyService', () => ({
  custodyService: { custodians: svc.emptyPage, floats: svc.emptyPage },
}));
vi.mock('../api/services/staffService', () => ({
  staffService: { list: svc.emptyPage, get: svc.refuse },
}));
vi.mock('../api/services/policyService', () => ({ policyService: { effective: svc.refuse } }));
vi.mock('../api/services/meterService', () => ({
  meterService: { listAllCaptures: svc.emptyPage, listExceptions: svc.emptyPage },
}));
vi.mock('../api/services/jobService', () => ({ jobService: { list: svc.emptyPage } }));
vi.mock('../api/services/machineService', () => ({
  machineService: {
    list: svc.emptyPage,
    fieldMachines: svc.emptyList,
    fieldContracts: svc.emptyList,
  },
}));

beforeEach(() => {
  svc.emptyPage.mockResolvedValue(empty);
  svc.emptyList.mockResolvedValue([]);
  svc.refuse.mockRejectedValue(new Error('not in this test'));
});

const SUMMARY = {
  as_of: '2026-10-21T12:00:00Z',
  policy_version: 'v1',
  hidden_tiles: [],
  unavailable_tiles: [],
  disabled_capabilities: [],
  customer_hours: null,
  hours_awaiting_activation: null,
  engine_hours: { machines: 2, by_status: { BALANCED: 2 } },
  unexplained_hours: { hours: '3', machines: 1, items: [] },
  missing_daily_reports: { count: 1, items: [] },
  investigations: null,
  cash: {
    custodians: [],
    transfers_awaiting_acknowledgement: [{ currency: 'TZS', count: 1, amount: '100' }],
    floats_awaiting_acknowledgement: [{ currency: 'TZS', count: 2, amount: '200' }],
    remittances_awaiting_confirmation: [{ currency: 'TZS', count: 3, amount: '300' }],
    partial_remittances_in_window: 1,
    remittance_cutoff_hour: 18,
    remittances_overdue_today: 1,
  },
  payments: null,
  discrepancies: {
    open_variances: [{ currency: 'TZS', count: 1, amount: '10' }],
    write_offs_proposed: 1,
    sync_conflicts_unresolved: 2,
  },
  unauthorized_attempts: null,
  outstanding_approvals: {
    total: 4,
    approval_requests: 1,
    payments_to_verify: 1,
    remittances_to_verify: 1,
    cash_retentions: 1,
    custody_adjustments: 1,
    write_offs: 1,
  },
} as unknown as AccountabilitySummaryDto;

const off = (...codes: string[]) =>
  ({ ...SUMMARY, disabled_capabilities: codes }) as AccountabilitySummaryDto;
const rowKeys = (s: AccountabilitySummaryDto, tile: string) =>
  (buildTiles(s, () => true).find((t) => t.key === tile)?.rows ?? []).map((r) => r.key);

describe('ENGINE_HOURS switched off', () => {
  it('shows the "not enabled" state on engine-hour pages', () => {
    renderWithProviders(
      <RequireCapability capability={CAPABILITY.engineHours} feature="Engine hours">
        <p>engine page</p>
      </RequireCapability>,
      { tenantPermissions: [P.tenantMeterRead], disabledCapabilities: [CAPABILITY.engineHours] },
    );
    expect(screen.getByText('Engine hours is not enabled for your company')).toBeInTheDocument();
    expect(screen.queryByText('engine page')).not.toBeInTheDocument();
  });

  it('hides daily reading, baseline and correction actions in Field work readings', async () => {
    renderWithProviders(<FieldReadingsPage />, {
      tenantPermissions: [P.tenantMeterCapture],
      disabledCapabilities: [CAPABILITY.engineHours],
    });
    expect(await screen.findByText('No readings')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Record daily reading' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Propose baseline' })).toBeNull();
  });

  it('keeps those actions while engine-hour controls are on', async () => {
    renderWithProviders(<FieldReadingsPage />, { tenantPermissions: [P.tenantMeterCapture] });
    expect(await screen.findByRole('button', { name: 'Record daily reading' })).toBeVisible();
    expect(screen.getByRole('button', { name: 'Propose baseline' })).toBeVisible();
  });

  it('drops the engine-hour tiles and never mentions them as hidden', () => {
    const on = buildTiles(SUMMARY, () => true).map((t) => t.key);
    expect(on).toEqual(expect.arrayContaining(['engine_hours', 'unexplained_hours']));
    const keys = buildTiles(off('ENGINE_HOURS'), () => true).map((t) => t.key);
    expect(keys).not.toContain('engine_hours');
    expect(keys).not.toContain('unexplained_hours');
    expect(keys).not.toContain('missing_daily_reports');
    expect(keys).toContain('cash_pending');
    expect(tileOfDisabledCapability('engine_hours', new Set(['ENGINE_HOURS']))).toBe(true);
    expect(tileOfDisabledCapability('cash', new Set(['ENGINE_HOURS']))).toBe(false);
  });

  it('falls notification links back: machine ledger to the machine, approvals to no link', () => {
    const disabled = new Set(['ENGINE_HOURS']);
    const ledger = { entity: 'machine', id: 'm1', path: '/tenant/engine-hours/machines/m1' };
    expect(notificationTargetPath(ledger)).toBe('/tenant/engine-hours/machines/m1');
    expect(notificationTargetPath(ledger, undefined, disabled)).toBe('/tenant/machines/m1');
    const baseline = { kind: 'METER_BASELINE', record_id: 'b1' };
    expect(notificationTargetPath(null, baseline)).toBe('/tenant/meter-baselines/b1');
    expect(notificationTargetPath(null, baseline, disabled)).toBeNull();
  });
});

describe('CASH_CUSTODY switched off', () => {
  it('keeps the cash basics tabs and hides the custody control tabs', async () => {
    renderWithProviders(<CashCustodyPage />, {
      tenantPermissions: [P.tenantFinanceRead],
      disabledCapabilities: [CAPABILITY.cashCustody],
    });
    const tabs = (await screen.findAllByRole('tab')).map((t) => t.textContent);
    expect(tabs).toEqual(['All custodians', 'Custody', 'Floats', 'Remittances', 'Reconciliation']);
  });

  it('shows every cash tab while the controls are on', async () => {
    renderWithProviders(<CashCustodyPage />, { tenantPermissions: [P.tenantFinanceRead] });
    const tabs = (await screen.findAllByRole('tab')).map((t) => t.textContent);
    expect(tabs).toEqual(
      expect.arrayContaining(['Transfers', 'Variances', 'Retentions', 'Adjustments']),
    );
  });

  it('shows the "not enabled" state on a control record’s page', () => {
    renderWithProviders(
      <RequireCapability capability={CAPABILITY.cashCustody} feature="This cash custody control">
        <p>transfer</p>
      </RequireCapability>,
      { tenantPermissions: [P.tenantFinanceRead], disabledCapabilities: [CAPABILITY.cashCustody] },
    );
    expect(
      screen.getByText('This cash custody control is not enabled for your company'),
    ).toBeInTheDocument();
  });

  it('hides transfers and keep-cash requests in Field work cash', async () => {
    renderWithProviders(<FieldCashPage />, {
      tenantPermissions: [P.tenantCollectionRecord],
      disabledCapabilities: [CAPABILITY.cashCustody],
    });
    const tabs = (await screen.findAllByRole('tab')).map((t) => t.textContent);
    expect(tabs).toEqual(['My collections', 'My remittances', 'Floats']);
  });

  it('lists floats without acknowledgement', async () => {
    renderWithProviders(<FloatsTab timeZone="UTC" />, {
      tenantPermissions: [P.tenantFinanceRead, P.tenantCollectionRecord],
      disabledCapabilities: [CAPABILITY.cashCustody],
    });
    expect(await screen.findByText('No floats')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Awaiting acknowledgement' })).toBeNull();
    expect(svc.emptyPage).toHaveBeenCalledWith(
      expect.objectContaining({
        filters: expect.not.objectContaining({ awaiting_acknowledgement: 'true' }) as unknown,
      }),
      expect.anything(),
    );
  });

  it('confirms remittances without an amount received', () => {
    const v = { decision: 'CONFIRM' as const, amount_received: '90', note: '' };
    expect(toRemittanceDecisionPayload(v)).toEqual({
      verified: true,
      note: null,
      amount_received: '90',
    });
    expect(toRemittanceDecisionPayload(v, false)).toEqual({ verified: true, note: null });
  });

  it('drops the control sub-figures of the cash, discrepancy and approval tiles', () => {
    expect(rowKeys(SUMMARY, 'cash_pending')).toEqual(
      expect.arrayContaining(['transfers-TZS', 'floats-TZS', 'partial', 'overdue']),
    );
    const s = off('CASH_CUSTODY');
    expect(rowKeys(s, 'cash_pending')).toEqual(['remittances-TZS']);
    const pending = buildTiles(s, () => true).find((t) => t.key === 'cash_pending');
    expect(pending?.title).toBe('Remittances awaiting confirmation');
    expect(pending?.value).toBe(3);
    expect(rowKeys(s, 'discrepancies')).toEqual(['sync']);
    expect(rowKeys(s, 'outstanding_approvals')).toEqual(['requests', 'payments', 'remittances']);
  });

  it('opens Cash custody instead of a switched-off control record', () => {
    const data = { kind: 'CASH_TRANSFER', record_id: 't1' };
    expect(notificationTargetPath(null, data, new Set(['CASH_CUSTODY']))).toBe(
      '/tenant/finance/cash',
    );
    expect(
      notificationTargetPath(
        null,
        { kind: 'CASH_REMITTANCE', record_id: 'r1' },
        new Set(['CASH_CUSTODY']),
      ),
    ).toBe('/tenant/finance/cash/remittances/r1');
  });

  it('shows the reconciliation without transfer, adjustment, write-off or acknowledgement figures', () => {
    renderWithProviders(<FormulaCard day={makeDay()} currency="TZS" />, {
      tenantPermissions: [P.tenantFinanceRead],
      disabledCapabilities: [CAPABILITY.cashCustody],
    });
    expect(screen.getByText('Cash collections')).toBeInTheDocument();
    expect(screen.getByText('Remittances awaiting confirmation')).toBeInTheDocument();
    for (const hidden of [
      'Transfers received',
      'Transfers sent',
      'Approved adjustments',
      'Written off',
      'Sent, not yet acknowledged (still held)',
      'Floats awaiting acknowledgement',
      'Adjustments awaiting decision',
    ]) {
      expect(screen.queryByText(hidden)).toBeNull();
    }
  });

  it('shows remittance details without the amount received or shortfall', () => {
    const labels = (on: boolean) => remittanceItems(makeHandover(), 'UTC', on).map((i) => i.label);
    expect(labels(true)).toEqual(expect.arrayContaining(['Received', 'Short of full balance']));
    expect(labels(false)).not.toContain('Received');
    expect(labels(false)).not.toContain('Expected balance');
    expect(labels(false)).not.toContain('Short of full balance');
    expect(labels(false)).toContain('Declared');
  });
});
